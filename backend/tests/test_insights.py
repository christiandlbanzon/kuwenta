"""Monthly insights — generates summary from real DB data with mocked LLM."""

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.llm.base import CompletionResult
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.user import User
from app.services import insights as insights_svc
from app.services.insights import generate_for_period
from app.services.seed import seed_default_categories
from app.tools._periods import _first_of_month, _last_of_month


async def _setup(session: AsyncSession) -> tuple[User, Account, dict]:
    user = User(email="ins@k.dev", hashed_password="x", display_name="Ins")
    session.add(user)
    await session.flush()
    cats = await seed_default_categories(session, user.id)
    by_name = {c.name: c for c in cats}
    acc = Account(user_id=user.id, name="GCash", type="ewallet")
    session.add(acc)
    await session.commit()
    await session.refresh(acc)
    return user, acc, by_name


async def test_generate_returns_none_when_no_transactions(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    user, _, _ = await _setup(session)
    today = date.today()
    insight = await generate_for_period(
        session,
        user,
        period_start=_first_of_month(today),
        period_end=_last_of_month(today),
    )
    assert insight is None


async def test_generate_creates_insight_with_data(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    user, acc, cats = await _setup(session)
    food = cats["Food & Dining"]
    today = date.today()
    p_start = _first_of_month(today)
    p_end = _last_of_month(today)

    # Spend ₱5000 on food this month
    session.add(
        Transaction(
            user_id=user.id, account_id=acc.id, category_id=food.id,
            amount=Decimal("5000"), type="expense",
            description="food spending",
            occurred_at=datetime.combine(p_start, datetime.min.time()).astimezone(),
        )
    )
    await session.commit()

    class FakeProvider:
        name = "fake"
        default_model = "fake-model"
        captured_prompts: list[str] = []

        async def complete(self, messages, **kw):
            FakeProvider.captured_prompts.append(messages[0].content)
            return CompletionResult(
                text="## Summary\nYou spent ₱5,000 on Food & Dining this month.",
                input_tokens=200, output_tokens=50,
            )
        async def complete_with_vision(self, *a, **kw): raise NotImplementedError
        async def complete_structured(self, *a, **kw): raise NotImplementedError

    monkeypatch.setattr(insights_svc, "get_provider_for_purpose", lambda _p: FakeProvider())

    insight = await generate_for_period(
        session, user, period_start=p_start, period_end=p_end
    )
    assert insight is not None
    assert insight.type == "monthly_summary"
    assert insight.period_start == p_start
    assert "Summary" in insight.content
    # Prompt should contain the actual spending data
    assert any("5,000" in p or "5000" in p for p in FakeProvider.captured_prompts)


async def test_generate_is_idempotent(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    user, acc, cats = await _setup(session)
    food = cats["Food & Dining"]
    today = date.today()
    p_start, p_end = _first_of_month(today), _last_of_month(today)
    session.add(
        Transaction(
            user_id=user.id, account_id=acc.id, category_id=food.id,
            amount=Decimal("100"), type="expense",
            description="x",
            occurred_at=datetime.combine(p_start, datetime.min.time()).astimezone(),
        )
    )
    await session.commit()

    call_count = [0]

    class FakeProvider:
        name = "fake"
        default_model = "fake-model"
        async def complete(self, *a, **kw):
            call_count[0] += 1
            return CompletionResult(text="summary", input_tokens=10, output_tokens=5)
        async def complete_with_vision(self, *a, **kw): raise NotImplementedError
        async def complete_structured(self, *a, **kw): raise NotImplementedError

    monkeypatch.setattr(insights_svc, "get_provider_for_purpose", lambda _p: FakeProvider())

    first = await generate_for_period(session, user, period_start=p_start, period_end=p_end)
    second = await generate_for_period(session, user, period_start=p_start, period_end=p_end)
    assert first is not None
    assert second is not None
    assert first.id == second.id
    assert call_count[0] == 1  # second call should not re-invoke LLM
