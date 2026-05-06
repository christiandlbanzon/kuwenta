"""Budgets CRUD + progress.

`progress_for_user` returns one BudgetProgress per active budget, computing:
- spent: sum of expense transactions in the current period
- projected_end_of_period: spent / days_elapsed * days_in_period (linear projection)
- on_track: projected <= budgeted

For monthly budgets the period is the current calendar month; for weekly it's the
current ISO week (Mon–Sun).
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from app.models.budget import Budget
from app.models.category import Category
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.budgets import BudgetCreate, BudgetProgress, BudgetUpdate
from app.tools._periods import _end_of_day, _first_of_month, _last_of_month, _start_of_day


def _current_period_dates(period: str, today: date) -> tuple[date, date]:
    if period == "monthly":
        return _first_of_month(today), _last_of_month(today)
    if period == "weekly":
        # ISO week: Monday-start
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
        return start, end
    raise ValueError(f"Unknown budget period: {period}")


async def list_budgets(session: AsyncSession, user_id: UUID) -> list[Budget]:
    res = await session.exec(select(Budget).where(Budget.user_id == user_id))
    return list(res.all())


async def get_budget(
    session: AsyncSession, user_id: UUID, budget_id: UUID
) -> Budget | None:
    res = await session.exec(
        select(Budget).where(Budget.user_id == user_id, Budget.id == budget_id)
    )
    return res.first()


async def create_budget(
    session: AsyncSession, user_id: UUID, payload: BudgetCreate
) -> Budget:
    # Validate category ownership
    cat = (
        await session.exec(
            select(Category.id).where(
                Category.user_id == user_id, Category.id == payload.category_id
            )
        )
    ).first()
    if cat is None:
        raise ValueError("Category not found or not owned by user")
    b = Budget(user_id=user_id, is_active=True, **payload.model_dump())
    session.add(b)
    await session.commit()
    await session.refresh(b)
    return b


async def update_budget(
    session: AsyncSession, user_id: UUID, budget_id: UUID, payload: BudgetUpdate
) -> Budget | None:
    b = await get_budget(session, user_id, budget_id)
    if not b:
        return None
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(b, k, v)
    session.add(b)
    await session.commit()
    await session.refresh(b)
    return b


async def delete_budget(session: AsyncSession, user_id: UUID, budget_id: UUID) -> bool:
    b = await get_budget(session, user_id, budget_id)
    if not b:
        return False
    await session.delete(b)
    await session.commit()
    return True


async def progress_for_user(
    session: AsyncSession, user: User, *, today: date | None = None
) -> list[BudgetProgress]:
    tz = ZoneInfo(user.timezone or "Asia/Manila")
    today = today or datetime.now(tz).date()

    rows = (
        await session.exec(
            select(Budget, Category)
            .join(Category, Budget.category_id == Category.id)
            .where(Budget.user_id == user.id, Budget.is_active.is_(True))  # type: ignore[attr-defined]
        )
    ).all()

    out: list[BudgetProgress] = []
    for budget, category in rows:
        p_start, p_end = _current_period_dates(budget.period, today)
        spent_row = (
            await session.exec(
                select(func.sum(Transaction.amount)).where(
                    Transaction.user_id == user.id,
                    Transaction.category_id == budget.category_id,
                    Transaction.type == "expense",
                    Transaction.occurred_at >= _start_of_day(p_start, tz),
                    Transaction.occurred_at <= _end_of_day(p_end, tz),
                )
            )
        ).first()
        spent = spent_row or Decimal("0")
        days_in_period = (p_end - p_start).days + 1
        days_elapsed = max(1, (today - p_start).days + 1)
        projected = spent if today >= p_end else (spent / days_elapsed * days_in_period)
        percent = float(spent / budget.amount * 100) if budget.amount else 0.0
        out.append(
            BudgetProgress(
                budget_id=budget.id,
                category_id=budget.category_id,
                category_name=category.name,
                period=budget.period,
                period_start=p_start,
                period_end=p_end,
                budgeted=budget.amount,
                spent=spent,
                remaining=budget.amount - spent,
                percent_used=percent,
                projected_end_of_period=Decimal(projected).quantize(Decimal("0.01")),
                on_track=Decimal(projected) <= budget.amount,
            )
        )
    return out
