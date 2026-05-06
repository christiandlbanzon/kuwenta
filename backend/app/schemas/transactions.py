from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

TransactionType = Literal["expense", "income", "transfer"]
TransactionSource = Literal["manual", "receipt_ocr", "csv_import", "email_parse"]


class TransactionCreate(BaseModel):
    account_id: UUID
    category_id: UUID | None = None
    amount: Decimal = Field(gt=Decimal("0"))
    type: TransactionType = "expense"
    description: str = Field(min_length=1, max_length=500)
    merchant: str | None = Field(default=None, max_length=200)
    notes: str | None = None
    occurred_at: datetime
    source: TransactionSource = "manual"


class TransactionUpdate(BaseModel):
    """Used for user overrides — also feeds the few-shot store on category change."""

    account_id: UUID | None = None
    category_id: UUID | None = None
    amount: Decimal | None = Field(default=None, gt=Decimal("0"))
    type: TransactionType | None = None
    description: str | None = None
    merchant: str | None = None
    notes: str | None = None
    occurred_at: datetime | None = None


class TransactionPublic(BaseModel):
    id: UUID
    account_id: UUID
    category_id: UUID | None
    amount: Decimal
    type: TransactionType
    description: str
    merchant: str | None
    notes: str | None
    occurred_at: datetime
    created_at: datetime
    source: TransactionSource
    raw_input: str | None
    ai_confidence: float | None


class QuickAddRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    # If omitted, server picks the user's first account (typically GCash for PH users).
    default_account_id: UUID | None = None


class QuickAddDraft(BaseModel):
    """The parsed-but-unsaved transaction returned for user confirmation."""

    amount: Decimal
    type: TransactionType
    account_id: UUID
    category_id: UUID | None
    description: str
    merchant: str | None
    occurred_at: datetime
    ai_confidence: float | None
    raw_input: str
