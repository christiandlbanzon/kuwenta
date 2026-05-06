"""Tests for the finance tool registry and executors.

Validates:
  - Tool dispatcher rejects unknown tools and invalid args
  - Each executor runs a parameterized query scoped to user_id
  - Cross-user data is never leaked through tool calls
"""

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.account import Account
from app.models.budget import Budget
from app.models.category import Category
from app.models.transaction import Transaction
from app.models.user import User
from app.services.seed import seed_default_categories
from app.tools.finance_tools import (
    TOOL_SCHEMAS,
    Period,
    ToolValidationError,
    execute_tool,
    tool_schemas_for_planner,
)


async def _setup(session: AsyncSession) -> tuple[User, Account, dict[str, Category]]:
    user = User(email="ft@k.dev", hashed_password="x", display_name="FT")
    session.add(user)
    await session.flush()
    cats = await seed_default_categories(session, user.id)
    by_name = {c.name: c for c in cats}
    acc = Account(user_id=user.id, name="GCash", type="ewallet", institution="GCash")
    session.add(acc)
    await session.commit()
    await session.refresh(acc)
    return user, acc, by_name


def _txn(
    user_id, account_id, category_id, amount: str, *, type: str = "expense", days_ago: int = 0,
    description: str = "x", merchant: str | None = None,
) -> Transaction:
    when = datetime.now().astimezone() - timedelta(days=days_ago)
    return Transaction(
        user_id=user_id,
        account_id=account_id,
        category_id=category_id,
        amount=Decimal(amount),
        type=type,  # type: ignore[arg-type]
        description=description,
        merchant=merchant,
        occurred_at=when,
    )


# --- Catalog / dispatcher -----------------------------------------------------


def test_tool_catalog_lists_all_tools() -> None:
    schemas = tool_schemas_for_planner()
    names = {s["name"] for s in schemas}
    assert names == set(TOOL_SCHEMAS.keys())
    for s in schemas:
        assert "parameters" in s and s["parameters"].get("type") == "object"


async def test_dispatcher_rejects_unknown_tool(session: AsyncSession) -> None:
    user, _, _ = await _setup(session)
    with pytest.raises(ToolValidationError):
        await execute_tool("not_a_tool", {}, user_id=user.id, session=session)


async def test_dispatcher_rejects_invalid_args(session: AsyncSession) -> None:
    user, _, _ = await _setup(session)
    with pytest.raises(ToolValidationError):
        # missing required `period`
        await execute_tool("sum_by_category", {}, user_id=user.id, session=session)


# --- sum_by_category ----------------------------------------------------------


async def test_sum_by_category_groups_correctly(session: AsyncSession) -> None:
    user, acc, cats = await _setup(session)
    food = cats["Food & Dining"]
    grocs = cats["Groceries"]
    session.add_all(
        [
            _txn(user.id, acc.id, food.id, "180", description="jollibee"),
            _txn(user.id, acc.id, food.id, "350", description="grabfood"),
            _txn(user.id, acc.id, grocs.id, "2300", description="sm grocery"),
        ]
    )
    await session.commit()

    result = await execute_tool(
        "sum_by_category",
        {"period": {"kind": "this_month"}},
        user_id=user.id,
        session=session,
    )
    totals = {row["category"]: Decimal(row["total"]) for row in result["totals"]}
    assert totals["Food & Dining"] == Decimal("530")
    assert totals["Groceries"] == Decimal("2300")


async def test_sum_by_category_filters_to_named_category(session: AsyncSession) -> None:
    user, acc, cats = await _setup(session)
    food = cats["Food & Dining"]
    grocs = cats["Groceries"]
    session.add_all(
        [
            _txn(user.id, acc.id, food.id, "180"),
            _txn(user.id, acc.id, grocs.id, "2300"),
        ]
    )
    await session.commit()

    result = await execute_tool(
        "sum_by_category",
        {"period": {"kind": "this_month"}, "category_name": "Food & Dining"},
        user_id=user.id,
        session=session,
    )
    assert len(result["totals"]) == 1
    assert result["totals"][0]["category"] == "Food & Dining"


async def test_sum_by_category_is_user_scoped(session: AsyncSession) -> None:
    """Critical: tool execution must NEVER see another user's transactions."""
    user_a, acc_a, cats_a = await _setup(session)

    # Build a second user with their own data
    user_b = User(email="b@k.dev", hashed_password="x", display_name="B")
    session.add(user_b)
    await session.flush()
    cats_b_list = await seed_default_categories(session, user_b.id)
    cats_b = {c.name: c for c in cats_b_list}
    acc_b = Account(user_id=user_b.id, name="BDO", type="bank")
    session.add(acc_b)
    await session.flush()

    # User B has a huge food expense
    session.add(_txn(user_b.id, acc_b.id, cats_b["Food & Dining"].id, "999999"))
    # User A has a small one
    session.add(_txn(user_a.id, acc_a.id, cats_a["Food & Dining"].id, "100"))
    await session.commit()

    a_result = await execute_tool(
        "sum_by_category",
        {"period": {"kind": "this_month"}, "category_name": "Food & Dining"},
        user_id=user_a.id,
        session=session,
    )
    assert Decimal(a_result["totals"][0]["total"]) == Decimal("100")
    assert "999999" not in str(a_result)


# --- top_categories -----------------------------------------------------------


async def test_top_categories_limits_n(session: AsyncSession) -> None:
    user, acc, cats = await _setup(session)
    session.add_all(
        [
            _txn(user.id, acc.id, cats["Food & Dining"].id, "500"),
            _txn(user.id, acc.id, cats["Groceries"].id, "2300"),
            _txn(user.id, acc.id, cats["Transportation"].id, "300"),
            _txn(user.id, acc.id, cats["Healthcare"].id, "150"),
        ]
    )
    await session.commit()

    result = await execute_tool(
        "top_categories",
        {"period": {"kind": "this_month"}, "n": 2},
        user_id=user.id,
        session=session,
    )
    assert len(result["totals"]) == 2
    # Sorted descending by total
    assert result["totals"][0]["category"] == "Groceries"
    assert result["totals"][1]["category"] == "Food & Dining"


# --- transactions_filter ------------------------------------------------------


async def test_transactions_filter_min_amount(session: AsyncSession) -> None:
    user, acc, cats = await _setup(session)
    food = cats["Food & Dining"]
    session.add_all(
        [
            _txn(user.id, acc.id, food.id, "180"),
            _txn(user.id, acc.id, food.id, "1500"),
            _txn(user.id, acc.id, food.id, "50"),
        ]
    )
    await session.commit()

    result = await execute_tool(
        "transactions_filter",
        {"period": {"kind": "this_month"}, "min_amount": "1000"},
        user_id=user.id,
        session=session,
    )
    assert len(result["transactions"]) == 1
    assert Decimal(result["transactions"][0]["amount"]) == Decimal("1500")


# --- compare_periods ----------------------------------------------------------


async def test_compare_periods_returns_difference(session: AsyncSession) -> None:
    user, acc, cats = await _setup(session)
    food = cats["Food & Dining"]
    today = datetime.now().astimezone()
    # 5 transactions this month, 2 last month-ish (we'll fake by setting occurred_at)
    a = Transaction(
        user_id=user.id, account_id=acc.id, category_id=food.id,
        amount=Decimal("500"), type="expense", description="recent",
        occurred_at=today,
    )
    b = Transaction(
        user_id=user.id, account_id=acc.id, category_id=food.id,
        amount=Decimal("200"), type="expense", description="old",
        occurred_at=today - timedelta(days=45),
    )
    session.add_all([a, b])
    await session.commit()

    # Compare last 30 days vs 31-60 days ago
    result = await execute_tool(
        "compare_periods",
        {
            "category_name": "Food & Dining",
            "period_a": {"kind": "last_30_days"},
            "period_b": {
                "kind": "custom",
                "start": (today - timedelta(days=60)).date().isoformat(),
                "end": (today - timedelta(days=31)).date().isoformat(),
            },
        },
        user_id=user.id,
        session=session,
    )
    assert Decimal(result["period_a_total"]) == Decimal("500")
    assert Decimal(result["period_b_total"]) == Decimal("200")
    assert Decimal(result["difference"]) == Decimal("300")


# --- account_balances ---------------------------------------------------------


async def test_account_balances_user_scoped(session: AsyncSession) -> None:
    user, _, _ = await _setup(session)
    # Put an account on a different user
    other = User(email="other@k.dev", hashed_password="x", display_name="O")
    session.add(other)
    await session.flush()
    session.add(
        Account(
            user_id=other.id, name="Secret", type="bank", current_balance=Decimal("1000000")
        )
    )
    await session.commit()

    result = await execute_tool(
        "account_balances", {}, user_id=user.id, session=session
    )
    names = {a["name"] for a in result["accounts"]}
    assert "Secret" not in names
    assert names == {"GCash"}


# --- budget_status ------------------------------------------------------------


async def test_budget_status_with_active_budget(session: AsyncSession) -> None:
    user, acc, cats = await _setup(session)
    food = cats["Food & Dining"]
    # Spend ₱1500 this month
    session.add(_txn(user.id, acc.id, food.id, "1500"))
    # Set a ₱5000 monthly budget
    session.add(
        Budget(
            user_id=user.id,
            category_id=food.id,
            amount=Decimal("5000"),
            period="monthly",
            start_date=datetime.now().date().replace(day=1),
            is_active=True,
        )
    )
    await session.commit()

    result = await execute_tool(
        "budget_status",
        {"category_name": "Food & Dining", "period": {"kind": "this_month"}},
        user_id=user.id,
        session=session,
    )
    assert Decimal(result["spent"]) == Decimal("1500")
    assert Decimal(result["budgeted"]) == Decimal("5000")
    assert Decimal(result["remaining"]) == Decimal("3500")


async def test_budget_status_without_budget(session: AsyncSession) -> None:
    user, _, _ = await _setup(session)
    result = await execute_tool(
        "budget_status",
        {"category_name": "Food & Dining", "period": {"kind": "this_month"}},
        user_id=user.id,
        session=session,
    )
    assert "note" in result
