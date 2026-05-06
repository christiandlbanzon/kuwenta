"""Anomaly detection — without LLM calls (we test the statistical layer)."""

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.llm.base import CompletionResult
from app.models.account import Account
from app.models.category import Category
from app.models.transaction import Transaction
from app.models.user import User
from app.services import anomaly as anomaly_svc
from app.services.anomaly import detect_and_persist, detect_for_user
from app.services.seed import seed_default_categories


async def _setup(session: AsyncSession) -> tuple[User, Account, dict[str, Category]]:
    user = User(email="anom@k.dev", hashed_password="x", display_name="Anom")
    session.add(user)
    await session.flush()
    cats = await seed_default_categories(session, user.id)
    by_name = {c.name: c for c in cats}
    acc = Account(user_id=user.id, name="GCash", type="ewallet")
    session.add(acc)
    await session.commit()
    await session.refresh(acc)
    return user, acc, by_name


def _months_ago(today: date, n: int) -> date:
    year = today.year
    month = today.month - n
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, 15)


async def _seed_baseline(
    session: AsyncSession, user: User, acc: Account, cat: Category, *, monthly: int
) -> None:
    today = date.today()
    for n in (1, 2, 3):
        d = _months_ago(today, n)
        session.add(
            Transaction(
                user_id=user.id,
                account_id=acc.id,
                category_id=cat.id,
                amount=Decimal(monthly),
                type="expense",
                description=f"baseline month {n}",
                occurred_at=datetime.combine(d, datetime.min.time()).astimezone(),
            )
        )
    await session.commit()


async def test_detect_no_anomaly_when_normal(session: AsyncSession) -> None:
    user, acc, cats = await _setup(session)
    food = cats["Food & Dining"]
    await _seed_baseline(session, user, acc, food, monthly=5000)
    # Current month: same baseline
    session.add(
        Transaction(
            user_id=user.id,
            account_id=acc.id,
            category_id=food.id,
            amount=Decimal("5000"),
            type="expense",
            description="normal current",
            occurred_at=datetime.now().astimezone(),
        )
    )
    await session.commit()

    flags = await detect_for_user(session, user)
    assert flags == []


async def test_detect_flags_4x_spike(session: AsyncSession) -> None:
    user, acc, cats = await _setup(session)
    food = cats["Food & Dining"]
    await _seed_baseline(session, user, acc, food, monthly=5000)
    # Current month: 4x baseline -> z-score way above threshold
    session.add(
        Transaction(
            user_id=user.id,
            account_id=acc.id,
            category_id=food.id,
            amount=Decimal("20000"),
            type="expense",
            description="anomalous spike",
            occurred_at=datetime.now().astimezone(),
        )
    )
    await session.commit()

    flags = await detect_for_user(session, user)
    food_flags = [f for f in flags if f.category_name == "Food & Dining"]
    assert len(food_flags) == 1
    assert food_flags[0].z_score >= 2.0
    assert food_flags[0].current_total == Decimal("20000")


async def test_detect_skips_categories_with_thin_history(session: AsyncSession) -> None:
    user, acc, cats = await _setup(session)
    healthcare = cats["Healthcare"]
    # Only 1 prior month with non-zero — insufficient for stddev
    today = date.today()
    d = _months_ago(today, 1)
    session.add(
        Transaction(
            user_id=user.id,
            account_id=acc.id,
            category_id=healthcare.id,
            amount=Decimal("500"),
            type="expense",
            description="single month",
            occurred_at=datetime.combine(d, datetime.min.time()).astimezone(),
        )
    )
    session.add(
        Transaction(
            user_id=user.id,
            account_id=acc.id,
            category_id=healthcare.id,
            amount=Decimal("10000"),
            type="expense",
            description="big spike now",
            occurred_at=datetime.now().astimezone(),
        )
    )
    await session.commit()

    flags = await detect_for_user(session, user)
    # Healthcare should NOT be flagged — only one prior month of data
    assert not any(f.category_name == "Healthcare" for f in flags)


async def test_detect_and_persist_creates_insights(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    user, acc, cats = await _setup(session)
    food = cats["Food & Dining"]
    await _seed_baseline(session, user, acc, food, monthly=5000)
    session.add(
        Transaction(
            user_id=user.id,
            account_id=acc.id,
            category_id=food.id,
            amount=Decimal("25000"),
            type="expense",
            description="huge anomaly",
            merchant="GrabFood",
            occurred_at=datetime.now().astimezone(),
        )
    )
    await session.commit()

    # Mock the LLM explanation
    class FakeProvider:
        name = "fake"
        default_model = "fake-model"

        async def complete(self, *a, **kw):
            return CompletionResult(text="Your Food & Dining spending was unusually high this month.", input_tokens=50, output_tokens=20)

        async def complete_with_vision(self, *a, **kw):
            raise NotImplementedError

        async def complete_structured(self, *a, **kw):
            raise NotImplementedError

    monkeypatch.setattr(anomaly_svc, "get_provider_for_purpose", lambda _p: FakeProvider())

    saved = await detect_and_persist(session, user)
    assert len(saved) >= 1
    insight = saved[0]
    assert insight.type == "anomaly"
    assert "Food & Dining" in insight.title
    assert insight.insight_metadata["category_name"] == "Food & Dining"
    assert insight.content


async def test_detect_and_persist_is_idempotent(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Running detection twice on the same day shouldn't duplicate insights."""
    user, acc, cats = await _setup(session)
    food = cats["Food & Dining"]
    await _seed_baseline(session, user, acc, food, monthly=5000)
    session.add(
        Transaction(
            user_id=user.id, account_id=acc.id, category_id=food.id,
            amount=Decimal("25000"), type="expense",
            description="anomaly", occurred_at=datetime.now().astimezone(),
        )
    )
    await session.commit()

    class FakeProvider:
        name = "fake"
        default_model = "fake-model"
        async def complete(self, *a, **kw):
            return CompletionResult(text="explanation", input_tokens=10, output_tokens=5)
        async def complete_with_vision(self, *a, **kw): raise NotImplementedError
        async def complete_structured(self, *a, **kw): raise NotImplementedError

    monkeypatch.setattr(anomaly_svc, "get_provider_for_purpose", lambda _p: FakeProvider())

    first = await detect_and_persist(session, user)
    second = await detect_and_persist(session, user)
    assert len(first) == 1
    assert len(second) == 0  # already flagged today
