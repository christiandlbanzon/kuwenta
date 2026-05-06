"""Anomaly detection.

For each category with sufficient history (≥2 prior periods), compare the current
period's total against a rolling 3-month baseline. Flag categories where the current
period is more than `Z_THRESHOLD` stddevs above the mean.

For each flagged category, gather the contributing transactions and ask the LLM to
produce a short, grounded explanation. Persist as `Insight` rows of type='anomaly'.
"""

from __future__ import annotations

import statistics
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.llm.base import Message
from app.llm.prompts import load_prompt
from app.llm.router import get_provider_for_purpose
from app.llm.tracer import trace
from app.models.category import Category
from app.models.insight import Insight
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.insights import AnomalyFlag
from app.tools._periods import _end_of_day, _first_of_month, _last_of_month, _start_of_day

Z_THRESHOLD = 2.0


async def _category_total_in_range(
    session: AsyncSession,
    user_id: UUID,
    category_id: UUID,
    start_dt: datetime,
    end_dt: datetime,
) -> Decimal:
    row = (
        await session.exec(
            select(func.sum(Transaction.amount)).where(
                Transaction.user_id == user_id,
                Transaction.category_id == category_id,
                Transaction.type == "expense",
                Transaction.occurred_at >= start_dt,
                Transaction.occurred_at <= end_dt,
            )
        )
    ).first()
    return row or Decimal("0")


def _months_back(today: date, n: int) -> tuple[date, date]:
    """Return (first_day, last_day) of the month n months before `today`."""
    year = today.year
    month = today.month - n
    while month <= 0:
        month += 12
        year -= 1
    first = date(year, month, 1)
    return first, _last_of_month(first)


async def detect_for_user(
    session: AsyncSession,
    user: User,
    *,
    today: date | None = None,
) -> list[AnomalyFlag]:
    """Detect anomalies for the user's CURRENT MONTH against a 3-month baseline.

    Returns one AnomalyFlag per category that exceeds Z_THRESHOLD stddevs.
    """
    tz = ZoneInfo(user.timezone or "Asia/Manila")
    today = today or datetime.now(tz).date()
    cur_start, cur_end_partial = _first_of_month(today), today

    # Build 3 prior months of totals per category
    prior_months = [_months_back(today, n) for n in (1, 2, 3)]

    cats = (
        await session.exec(select(Category).where(Category.user_id == user.id))
    ).all()

    flags: list[AnomalyFlag] = []
    for cat in cats:
        # Current period (month-to-date) total
        cur_total = await _category_total_in_range(
            session,
            user.id,
            cat.id,
            _start_of_day(cur_start, tz),
            _end_of_day(cur_end_partial, tz),
        )
        # Prior 3 full months
        prior_totals: list[Decimal] = []
        for first, last in prior_months:
            t = await _category_total_in_range(
                session,
                user.id,
                cat.id,
                _start_of_day(first, tz),
                _end_of_day(last, tz),
            )
            prior_totals.append(t)

        # Need at least 2 non-zero prior months for a meaningful baseline
        nonzero = [t for t in prior_totals if t > 0]
        if len(nonzero) < 2:
            continue

        floats = [float(t) for t in prior_totals]
        mean = statistics.mean(floats)
        stddev = statistics.stdev(floats) if len(floats) > 1 else 0.0
        # When the baseline is perfectly flat (zero stddev) we'd divide by zero. Use
        # 5% of the mean as a floor so genuinely large spikes still get flagged.
        effective_stddev = stddev if stddev > 0 else max(mean * 0.05, 1.0)
        z = (float(cur_total) - mean) / effective_stddev
        if z < Z_THRESHOLD:
            continue

        # Gather contributing transaction ids (current month)
        ctx_rows = (
            await session.exec(
                select(Transaction).where(
                    Transaction.user_id == user.id,
                    Transaction.category_id == cat.id,
                    Transaction.type == "expense",
                    Transaction.occurred_at >= _start_of_day(cur_start, tz),
                    Transaction.occurred_at <= _end_of_day(cur_end_partial, tz),
                ).order_by(Transaction.amount.desc())  # type: ignore[attr-defined]
            )
        ).all()

        flags.append(
            AnomalyFlag(
                category_id=cat.id,
                category_name=cat.name,
                period_start=cur_start,
                period_end=cur_end_partial,
                current_total=cur_total,
                baseline_mean=Decimal(mean).quantize(Decimal("0.01")),
                baseline_stddev=Decimal(stddev).quantize(Decimal("0.01")),
                z_score=round(z, 2),
                contributing_transaction_ids=[t.id for t in ctx_rows[:20]],
            )
        )
    return flags


async def explain_anomaly(
    session: AsyncSession, user: User, flag: AnomalyFlag
) -> str:
    """Ask the LLM to write one short paragraph explaining the anomaly."""
    contributing = (
        await session.exec(
            select(Transaction).where(
                Transaction.user_id == user.id,
                Transaction.id.in_(flag.contributing_transaction_ids),  # type: ignore[attr-defined]
            )
        )
    ).all()

    contributing_block = "\n".join(
        f"- ₱{t.amount} on {t.occurred_at.date().isoformat()} — "
        f"\"{t.description}\""
        + (f" ({t.merchant})" if t.merchant else "")
        for t in contributing
    ) or "(none)"

    template = load_prompt("anomaly_explain")
    prompt = template.format(
        category_name=flag.category_name,
        period_label=f"{flag.period_start.isoformat()} to {flag.period_end.isoformat()}",
        current_total=flag.current_total,
        baseline_mean=flag.baseline_mean,
        baseline_stddev=flag.baseline_stddev,
        z_score=flag.z_score,
        contributing_block=contributing_block,
    )

    provider = get_provider_for_purpose("anomaly_explain")
    async with trace(
        session,
        user_id=user.id,
        purpose="anomaly_explain",
        provider=provider.name,
        model=provider.default_model,
    ) as t:
        completion = await provider.complete(
            [Message(role="user", content=prompt)], temperature=0.4
        )
        t.tokens(completion.input_tokens, completion.output_tokens)
    return completion.text.strip()


async def detect_and_persist(
    session: AsyncSession, user: User, *, today: date | None = None
) -> list[Insight]:
    """End-to-end: detect anomalies, generate explanations, persist Insight rows.
    Idempotent within a single day — if an anomaly insight for the same category +
    period_start already exists today, skip it."""
    tz = ZoneInfo(user.timezone or "Asia/Manila")
    today = today or datetime.now(tz).date()
    flags = await detect_for_user(session, user, today=today)

    saved: list[Insight] = []
    for flag in flags:
        # Skip if we've already flagged this category+period today
        existing = (
            await session.exec(
                select(Insight).where(
                    Insight.user_id == user.id,
                    Insight.type == "anomaly",
                    Insight.period_start == flag.period_start,
                )
            )
        ).all()
        already_for_cat = [
            i
            for i in existing
            if i.insight_metadata.get("category_id") == str(flag.category_id)
        ]
        if already_for_cat:
            continue

        explanation = await explain_anomaly(session, user, flag)
        insight = Insight(
            user_id=user.id,
            type="anomaly",
            title=f"Unusual spending: {flag.category_name}",
            content=explanation,
            insight_metadata={
                "category_id": str(flag.category_id),
                "category_name": flag.category_name,
                "z_score": flag.z_score,
                "current_total": str(flag.current_total),
                "baseline_mean": str(flag.baseline_mean),
                "baseline_stddev": str(flag.baseline_stddev),
                "transaction_ids": [str(t) for t in flag.contributing_transaction_ids],
            },
            period_start=flag.period_start,
            period_end=flag.period_end,
        )
        session.add(insight)
        saved.append(insight)
    if saved:
        await session.commit()
        for i in saved:
            await session.refresh(i)
    return saved
