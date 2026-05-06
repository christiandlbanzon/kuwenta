from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

BudgetPeriod = Literal["monthly", "weekly"]


class BudgetCreate(BaseModel):
    category_id: UUID
    amount: Decimal = Field(gt=Decimal("0"))
    period: BudgetPeriod = "monthly"
    start_date: date


class BudgetUpdate(BaseModel):
    amount: Decimal | None = Field(default=None, gt=Decimal("0"))
    period: BudgetPeriod | None = None
    start_date: date | None = None
    is_active: bool | None = None


class BudgetPublic(BaseModel):
    id: UUID
    category_id: UUID
    amount: Decimal
    period: BudgetPeriod
    start_date: date
    is_active: bool


class BudgetProgress(BaseModel):
    """Spending against a single budget for the current period."""

    budget_id: UUID
    category_id: UUID
    category_name: str
    period: BudgetPeriod
    period_start: date
    period_end: date
    budgeted: Decimal
    spent: Decimal
    remaining: Decimal
    percent_used: float
    projected_end_of_period: Decimal
    on_track: bool  # projected <= budgeted
