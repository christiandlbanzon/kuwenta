"""Q&A service tests with the LLM mocked.

Verifies:
  - Planner output → tool execution → summarizer output flow
  - Unknown tool names from a (hypothetical) misbehaving planner are caught at validate
  - cannot_answer=True bypasses tool execution
  - Summarizer output is not fabricated — real answer text is returned
"""

from datetime import datetime
from decimal import Decimal

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.llm.base import CompletionResult, StructuredResult
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.qa import PlannerDecision, ToolInvocation
from app.services.qa import answer_question
from app.services.seed import seed_default_categories


class _ScriptedProvider:
    """Returns a pre-set planner decision, then a pre-set summarizer text.

    `complete_structured` is called once (for the planner) and `complete` once (for the
    summarizer). Both calls share this provider since the router maps both qa_planner
    and qa_summarizer purposes to the same provider in our config.
    """

    name = "fake"
    default_model = "fake-model"

    def __init__(self, plan: PlannerDecision, summary: str) -> None:
        self._plan = plan
        self._summary = summary

    async def complete_with_vision(self, *a, **kw):  # pragma: no cover
        raise NotImplementedError

    async def complete_structured(self, messages, schema, **kwargs):  # type: ignore[no-untyped-def]
        return StructuredResult(parsed=self._plan, input_tokens=20, output_tokens=10)

    async def complete(self, messages, **kwargs):  # type: ignore[no-untyped-def]
        return CompletionResult(text=self._summary)


async def _setup(session: AsyncSession) -> tuple[User, Account]:
    user = User(email="qa@k.dev", hashed_password="x", display_name="QA")
    session.add(user)
    await session.flush()
    cats = await seed_default_categories(session, user.id)
    by_name = {c.name: c for c in cats}
    acc = Account(user_id=user.id, name="GCash", type="ewallet")
    session.add(acc)
    await session.flush()
    # Add 3 food expenses this month
    now = datetime.now().astimezone()
    for amt in (180, 350, 220):
        session.add(
            Transaction(
                user_id=user.id,
                account_id=acc.id,
                category_id=by_name["Food & Dining"].id,
                amount=Decimal(amt),
                type="expense",
                description=f"food {amt}",
                occurred_at=now,
            )
        )
    await session.commit()
    return user, acc


async def test_qa_executes_planned_tool_and_returns_summary(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    user, _ = await _setup(session)
    plan = PlannerDecision(
        invocations=[
            ToolInvocation(
                tool="sum_by_category",
                args={
                    "period": {"kind": "this_month"},
                    "category_name": "Food & Dining",
                },
            )
        ]
    )
    fake = _ScriptedProvider(plan, "You spent ₱750 on Food & Dining this month.")
    monkeypatch.setattr("app.services.qa.get_provider_for_purpose", lambda _p: fake)

    resp = await answer_question(session, user, "How much did I spend on food this month?")
    assert resp.answer.startswith("You spent ₱750")
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].tool == "sum_by_category"
    assert resp.tool_calls[0].error is None
    # Tool result should reflect the actual sum
    totals = resp.tool_calls[0].result["totals"]
    assert any(Decimal(t["total"]) == Decimal("750") for t in totals)


async def test_qa_handles_cannot_answer(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    user, _ = await _setup(session)
    plan = PlannerDecision(
        invocations=[],
        cannot_answer=True,
        reason="I can't predict retirement timing.",
    )
    fake = _ScriptedProvider(
        plan, "I can't forecast retirement, but I can compare your last 6 months."
    )
    monkeypatch.setattr("app.services.qa.get_provider_for_purpose", lambda _p: fake)

    resp = await answer_question(session, user, "When can I retire?")
    assert resp.cannot_answer is True
    assert resp.tool_calls == []
    assert "retirement" in resp.answer.lower() or "forecast" in resp.answer.lower()


async def test_qa_records_validation_error_for_invalid_planner_output(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the planner names a nonexistent tool, the dispatcher records an error in
    the trace but does not crash — the summarizer still runs."""
    user, _ = await _setup(session)
    plan = PlannerDecision(
        invocations=[ToolInvocation(tool="nonexistent_tool", args={})]
    )
    fake = _ScriptedProvider(plan, "Sorry, I couldn't compute that.")
    monkeypatch.setattr("app.services.qa.get_provider_for_purpose", lambda _p: fake)

    resp = await answer_question(session, user, "Something")
    assert resp.tool_calls[0].error is not None
    assert "validation_error" in resp.tool_calls[0].error
    assert resp.answer  # summarizer still produced text
