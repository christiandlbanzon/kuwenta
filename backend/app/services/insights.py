"""Monthly insights generation.

Builds the data block from the user's transactions for a given month, then asks the
LLM to produce a markdown summary grounded in that data. Persisted as Insight rows
of type='monthly_summary'. Idempotent per (user, period_start).
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
from app.models.budget import Budget
from app.models.category import Category
from app.models.insight import Insight
from app.models.transaction import Transaction
from app.models.user import User
from app.tools._periods import _end_of_day, _first_of_month, _last_of_month, _start_of_day


def _previous_month(today: date) -> tuple[date, date]:
    first_this = _first_of_month(today)
    last_prev = first_this - timedelta(days=1)
    first_prev = _first_of_month(last_prev)
    return first_prev, last_prev


async def _sum_by_category_block(
    session: AsyncSession,
    user_id: UUID,
    start_dt: datetime,
    end_dt: datetime,
    *,
    txn_type: str = "expense",
    limit: int = 5,
) -> list[tuple[str, Decimal]]:
    rows = (
        await session.exec(
            select(
                Category.name.label("name"),  # type: ignore[attr-defined]
                func.sum(Transaction.amount).label("total"),
            )
            .join(Category, Transaction.category_id == Category.id)
            .where(
                Transaction.user_id == user_id,
                Transaction.type == txn_type,
                Transaction.occurred_at >= start_dt,
                Transaction.occurred_at <= end_dt,
            )
            .group_by(Category.name)
            .order_by(func.sum(Transaction.amount).desc())
            .limit(limit)
        )
    ).all()
    return [(r.name, r.total or Decimal("0")) for r in rows]


async def _sum_by_merchant(
    session: AsyncSession,
    user_id: UUID,
    start_dt: datetime,
    end_dt: datetime,
    *,
    limit: int = 5,
) -> list[tuple[str, Decimal]]:
    rows = (
        await session.exec(
            select(
                Transaction.merchant,  # type: ignore[arg-type]
                func.sum(Transaction.amount).label("total"),
            )
            .where(
                Transaction.user_id == user_id,
                Transaction.type == "expense",
                Transaction.merchant.is_not(None),  # type: ignore[attr-defined]
                Transaction.occurred_at >= start_dt,
                Transaction.occurred_at <= end_dt,
            )
            .group_by(Transaction.merchant)
            .order_by(func.sum(Transaction.amount).desc())
            .limit(limit)
        )
    ).all()
    return [(r.merchant, r.total or Decimal("0")) for r in rows]


async def _sum_total(
    session: AsyncSession,
    user_id: UUID,
    start_dt: datetime,
    end_dt: datetime,
    *,
    txn_type: str,
) -> Decimal:
    row = (
        await session.exec(
            select(func.sum(Transaction.amount)).where(
                Transaction.user_id == user_id,
                Transaction.type == txn_type,
                Transaction.occurred_at >= start_dt,
                Transaction.occurred_at <= end_dt,
            )
        )
    ).first()
    return row or Decimal("0")


async def generate_for_period(
    session: AsyncSession,
    user: User,
    *,
    period_start: date,
    period_end: date,
) -> Insight | None:
    """Generate (or re-generate) a monthly_summary insight for [period_start, period_end].
    Idempotent: if an insight for this user+period already exists, return it."""
    existing = (
        await session.exec(
            select(Insight).where(
                Insight.user_id == user.id,
                Insight.type == "monthly_summary",
                Insight.period_start == period_start,
                Insight.period_end == period_end,
            )
        )
    ).first()
    if existing:
        return existing

    tz = ZoneInfo(user.timezone or "Asia/Manila")
    start_dt = _start_of_day(period_start, tz)
    end_dt = _end_of_day(period_end, tz)

    total_spent = await _sum_total(
        session, user.id, start_dt, end_dt, txn_type="expense"
    )
    total_income = await _sum_total(
        session, user.id, start_dt, end_dt, txn_type="income"
    )
    if total_spent == 0 and total_income == 0:
        return None  # nothing to summarize

    savings_rate = (
        float((total_income - total_spent) / total_income * 100) if total_income > 0 else 0.0
    )
    top_cats = await _sum_by_category_block(session, user.id, start_dt, end_dt)
    top_merchants = await _sum_by_merchant(session, user.id, start_dt, end_dt)

    # 3-month baseline per top category
    baseline_lines: list[str] = []
    for name, _ in top_cats:
        prior_totals: list[float] = []
        for n in (1, 2, 3):
            year = period_start.year
            month = period_start.month - n
            while month <= 0:
                month += 12
                year -= 1
            pf = date(year, month, 1)
            pl = _last_of_month(pf)
            cat_id_row = (
                await session.exec(
                    select(Category.id).where(
                        Category.user_id == user.id, Category.name == name
                    )
                )
            ).first()
            if not cat_id_row:
                continue
            t = (
                await session.exec(
                    select(func.sum(Transaction.amount)).where(
                        Transaction.user_id == user.id,
                        Transaction.category_id == cat_id_row,
                        Transaction.type == "expense",
                        Transaction.occurred_at >= _start_of_day(pf, tz),
                        Transaction.occurred_at <= _end_of_day(pl, tz),
                    )
                )
            ).first()
            prior_totals.append(float(t or 0))
        if prior_totals:
            mean = statistics.mean(prior_totals)
            sd = statistics.stdev(prior_totals) if len(prior_totals) > 1 else 0.0
            baseline_lines.append(f"  - {name}: ₱{mean:,.0f} ± ₱{sd:,.0f}")

    # Active budgets summary (just lists; progress is computed elsewhere)
    budgets = (
        await session.exec(
            select(Budget, Category)
            .join(Category, Budget.category_id == Category.id)
            .where(Budget.user_id == user.id, Budget.is_active.is_(True))  # type: ignore[attr-defined]
        )
    ).all()
    budgets_block = (
        "\n".join(
            f"  - {cat.name}: ₱{b.amount:,.0f}/{b.period}" for b, cat in budgets
        )
        or "  (no active budgets)"
    )

    # Render prompt
    template = load_prompt("monthly_insights")
    month_label = period_start.strftime("%B %Y")
    prompt = template.format(
        today_iso=date.today().isoformat(),
        month_label=month_label,
        total_spent=f"{total_spent:,.0f}",
        total_income=f"{total_income:,.0f}",
        savings_rate_pct=f"{savings_rate:.1f}",
        top_categories_block="\n".join(
            f"  - {name}: ₱{amt:,.0f}" for name, amt in top_cats
        )
        or "  (none)",
        top_merchants_block="\n".join(
            f"  - {name}: ₱{amt:,.0f}" for name, amt in top_merchants
        )
        or "  (none)",
        baseline_block="\n".join(baseline_lines) or "  (insufficient history)",
        anomalies_block="  (none)",  # filled in by anomaly service separately
        budgets_block=budgets_block,
    )

    provider = get_provider_for_purpose("insights")
    async with trace(
        session,
        user_id=user.id,
        purpose="monthly_insights",
        provider=provider.name,
        model=provider.default_model,
    ) as t:
        completion = await provider.complete(
            [Message(role="user", content=prompt)], temperature=0.5
        )
        t.tokens(completion.input_tokens, completion.output_tokens)

    insight = Insight(
        user_id=user.id,
        type="monthly_summary",
        title=f"{month_label} summary",
        content=completion.text.strip(),
        insight_metadata={
            "total_spent": str(total_spent),
            "total_income": str(total_income),
            "savings_rate_pct": savings_rate,
            "top_categories": [(n, str(a)) for n, a in top_cats],
            "top_merchants": [(n, str(a)) for n, a in top_merchants],
        },
        period_start=period_start,
        period_end=period_end,
    )
    session.add(insight)
    await session.commit()
    await session.refresh(insight)
    return insight


async def generate_last_month_for_user(
    session: AsyncSession, user: User, *, today: date | None = None
) -> Insight | None:
    """Convenience for the cron job: previous calendar month relative to `today`."""
    tz = ZoneInfo(user.timezone or "Asia/Manila")
    today = today or datetime.now(tz).date()
    p_start, p_end = _previous_month(today)
    return await generate_for_period(
        session, user, period_start=p_start, period_end=p_end
    )
