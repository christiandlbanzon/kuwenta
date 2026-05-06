from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import Column, Numeric
from sqlmodel import Field, SQLModel

BudgetPeriod = Literal["monthly", "weekly"]


class Budget(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", index=True)
    category_id: UUID = Field(foreign_key="category.id")
    amount: Decimal = Field(sa_column=Column(Numeric(14, 2), nullable=False))
    period: str = "monthly"  # one of BudgetPeriod
    start_date: date
    is_active: bool = True
