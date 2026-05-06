"""Insights eval — does the LLM identify the right anomaly and stay grounded?

Builds a synthetic dataset where we KNOW the truth: 3 prior months of normal spending
in food (~₱5,000/mo), then a current month with a deliberate ₱20,000 anomaly. Runs
the anomaly detection + explanation pipeline and uses an LLM-as-judge with two checks:
  1. Did the explanation reference the right category (Food & Dining)?
  2. Did the explanation use only numbers from the contributing transactions
     (hallucination check — if it cites a peso figure not in the input, fail)?

Run:
    uv run pytest evals/eval_insights.py -m eval -v
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import BaseModel, Field
from sqlmodel import select

from app.llm.base import Message
from app.llm.router import get_provider_for_purpose
from app.models.transaction import Transaction
from app.models.user import User as UserModel
from app.services.anomaly import detect_and_persist
from evals._common import make_eval_db, make_eval_user, write_report


def _months_ago(today: date, n: int) -> date:
    year = today.year
    month = today.month - n
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, 15)


class GroundingCheck(BaseModel):
    references_correct_category: bool
    only_uses_supplied_numbers: bool = Field(
        description="True iff every peso figure in the explanation matches a number in the contributing transactions or baseline stats. False if any figure is invented."
    )
    reasoning: str


HALLUCINATION_JUDGE_PROMPT = """You are checking an anomaly explanation for hallucinations.

EXPLANATION:
{explanation}

GROUND TRUTH:
- Category: Food & Dining
- Current month total: ₱{current_total}
- 3-month baseline mean: ₱{baseline_mean}
- 3-month baseline stddev: ₱{baseline_stddev}
- Contributing transactions:
{transactions}

Check:
1. Does the explanation reference Food & Dining (the category that was actually flagged)?
2. Does every peso figure in the explanation appear in the ground truth above? Allowable: rounded versions of the same figure (₱20,000 vs ₱20,000.00) and percentages derived from the figures.

Return JSON: {{"references_correct_category": bool, "only_uses_supplied_numbers": bool, "reasoning": "..."}}"""


@pytest.mark.eval
async def test_insights_anomaly_grounding() -> None:
    factory = await make_eval_db()
    user, acc, cats = await make_eval_user(factory)
    food = cats["Food & Dining"]
    transport = cats["Transportation"]

    today = date.today()
    async with factory() as session:
        # Add 3 prior months of "normal" spending: ~₱5,000/mo on food, ~₱2,000/mo transport
        for n in (1, 2, 3):
            month_date = _months_ago(today, n)
            for amt in (1500, 1500, 2000):  # totals to ~₱5,000
                session.add(
                    Transaction(
                        user_id=user.id,
                        account_id=acc.id,
                        category_id=food.id,
                        amount=Decimal(amt),
                        type="expense",
                        description=f"normal food month {n}",
                        merchant="Jollibee",
                        occurred_at=datetime.combine(month_date, datetime.min.time()).astimezone(),
                    )
                )
            session.add(
                Transaction(
                    user_id=user.id,
                    account_id=acc.id,
                    category_id=transport.id,
                    amount=Decimal("2000"),
                    type="expense",
                    description=f"normal transport month {n}",
                    merchant="Grab",
                    occurred_at=datetime.combine(month_date, datetime.min.time()).astimezone(),
                )
            )
        # Current month: ANOMALY in food — ₱20,000 (4x baseline)
        for i, amt in enumerate([5000, 5000, 5000, 5000]):
            session.add(
                Transaction(
                    user_id=user.id,
                    account_id=acc.id,
                    category_id=food.id,
                    amount=Decimal(amt),
                    type="expense",
                    description=f"anomalous food spike #{i+1}",
                    merchant="GrabFood",
                    occurred_at=datetime.now().astimezone() - timedelta(days=i),
                )
            )
        # Normal current-month transport
        session.add(
            Transaction(
                user_id=user.id,
                account_id=acc.id,
                category_id=transport.id,
                amount=Decimal("2000"),
                type="expense",
                description="normal current transport",
                merchant="Grab",
                occurred_at=datetime.now().astimezone(),
            )
        )
        await session.commit()

    async with factory() as session:
        user = (
            await session.exec(select(UserModel).where(UserModel.email == "eval@kuwenta.dev"))
        ).first()
        assert user is not None
        insights = await detect_and_persist(session, user)

    assert insights, "Anomaly detection did not flag the deliberate Food & Dining anomaly"
    food_insights = [
        i for i in insights if i.insight_metadata.get("category_name") == "Food & Dining"
    ]
    assert food_insights, "No anomaly insight for Food & Dining"
    insight = food_insights[0]

    # Grounding check via LLM judge
    contributing_block = "\n".join(
        f"- ₱{amt}" for amt in (5000, 5000, 5000, 5000)
    )
    provider = get_provider_for_purpose("qa")
    prompt = HALLUCINATION_JUDGE_PROMPT.format(
        explanation=insight.content,
        current_total=insight.insight_metadata.get("current_total"),
        baseline_mean=insight.insight_metadata.get("baseline_mean"),
        baseline_stddev=insight.insight_metadata.get("baseline_stddev"),
        transactions=contributing_block,
    )
    sresult = await provider.complete_structured(
        [Message(role="user", content=prompt)],
        schema=GroundingCheck,
        temperature=0.0,
    )
    check: GroundingCheck = sresult.parsed  # type: ignore[assignment]

    md = [
        "# Insights eval — anomaly grounding\n",
        f"**Anomaly was correctly flagged:** ✓",
        f"**Insight title:** {insight.title}",
        f"**Z-score:** {insight.insight_metadata.get('z_score')}",
        "",
        "## Generated explanation",
        "",
        insight.content,
        "",
        "## Grounding check (LLM judge)",
        f"- References correct category: {'✓' if check.references_correct_category else '✗'}",
        f"- Only uses supplied numbers (no hallucinations): {'✓' if check.only_uses_supplied_numbers else '✗'}",
        f"- Reasoning: {check.reasoning}",
    ]
    report_path = write_report("insights", "\n".join(md))
    print(f"\n[eval_insights] correct_cat={check.references_correct_category}, "
          f"grounded={check.only_uses_supplied_numbers}")
    print(f"[eval_insights] report: {report_path}")

    assert check.references_correct_category, (
        f"Insight did not reference Food & Dining: {check.reasoning}"
    )
    assert check.only_uses_supplied_numbers, (
        f"Insight hallucinated numbers: {check.reasoning}"
    )
