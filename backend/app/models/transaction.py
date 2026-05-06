from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import Column, Numeric
from sqlmodel import Field, SQLModel

from app.models._common import tz_column, tz_now_column, utcnow

TransactionType = Literal["expense", "income", "transfer"]
TransactionSource = Literal["manual", "receipt_ocr", "csv_import", "email_parse"]


class Transaction(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", index=True)
    account_id: UUID = Field(foreign_key="account.id")
    category_id: UUID | None = Field(default=None, foreign_key="category.id")
    amount: Decimal = Field(sa_column=Column(Numeric(14, 2), nullable=False))
    type: str  # one of TransactionType
    description: str
    merchant: str | None = None
    notes: str | None = None
    occurred_at: datetime = Field(sa_column=tz_column(indexed=True))
    created_at: datetime = Field(default_factory=utcnow, sa_column=tz_now_column())
    source: str = "manual"  # one of TransactionSource
    raw_input: str | None = None
    ai_confidence: float | None = None
