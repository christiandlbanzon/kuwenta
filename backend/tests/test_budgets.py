"""Budget CRUD + progress."""

from datetime import datetime
from decimal import Decimal

from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.account import Account
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.budgets import BudgetCreate
from app.services.budgets import create_budget, list_budgets, progress_for_user
from app.services.seed import seed_default_categories


async def _setup(session: AsyncSession) -> tuple[User, Account, dict]:
    user = User(email="bg@k.dev", hashed_password="x", display_name="BG")
    session.add(user)
    await session.flush()
    cats = await seed_default_categories(session, user.id)
    by_name = {c.name: c for c in cats}
    acc = Account(user_id=user.id, name="GCash", type="ewallet")
    session.add(acc)
    await session.commit()
    await session.refresh(acc)
    return user, acc, by_name


async def test_create_and_list_budget(session: AsyncSession) -> None:
    user, _, cats = await _setup(session)
    food = cats["Food & Dining"]
    today = datetime.now().date()
    b = await create_budget(
        session,
        user.id,
        BudgetCreate(category_id=food.id, amount=Decimal("5000"), start_date=today),
    )
    assert b.is_active
    assert b.amount == Decimal("5000")

    rows = await list_budgets(session, user.id)
    assert len(rows) == 1


async def test_create_budget_rejects_other_users_category(session: AsyncSession) -> None:
    import pytest

    user_a, _, _ = await _setup(session)
    user_b = User(email="other@k.dev", hashed_password="x", display_name="O")
    session.add(user_b)
    await session.flush()
    cats_b = await seed_default_categories(session, user_b.id)
    await session.commit()

    food_b = next(c for c in cats_b if c.name == "Food & Dining")
    with pytest.raises(ValueError, match="Category not found"):
        await create_budget(
            session,
            user_a.id,
            BudgetCreate(
                category_id=food_b.id,
                amount=Decimal("5000"),
                start_date=datetime.now().date(),
            ),
        )


async def test_progress_computes_spent_and_projection(session: AsyncSession) -> None:
    user, acc, cats = await _setup(session)
    food = cats["Food & Dining"]
    today = datetime.now().date()
    await create_budget(
        session,
        user.id,
        BudgetCreate(category_id=food.id, amount=Decimal("5000"), start_date=today.replace(day=1)),
    )
    # Spend ₱1500 this month
    session.add(
        Transaction(
            user_id=user.id,
            account_id=acc.id,
            category_id=food.id,
            amount=Decimal("1500"),
            type="expense",
            description="food",
            occurred_at=datetime.now().astimezone(),
        )
    )
    await session.commit()

    rows = await progress_for_user(session, user)
    assert len(rows) == 1
    p = rows[0]
    assert p.budgeted == Decimal("5000")
    assert p.spent == Decimal("1500")
    assert p.remaining == Decimal("3500")
    assert p.percent_used > 0
    assert p.category_name == "Food & Dining"
