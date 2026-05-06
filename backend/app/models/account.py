from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import Column, Numeric
from sqlmodel import Field, SQLModel

from app.models._common import tz_now_column, utcnow

# Allowed values (validated by Pydantic schemas at API boundaries; DB column is plain str)
AccountType = Literal["cash", "bank", "ewallet", "credit_card"]


class Account(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", index=True)
    name: str
    type: str  # one of AccountType
    institution: str | None = None
    current_balance: Decimal = Field(
        default=Decimal("0"), sa_column=Column(Numeric(14, 2), nullable=False)
    )
    created_at: datetime = Field(default_factory=utcnow, sa_column=tz_now_column())
