from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

TransactionType = Literal["expense", "income", "transfer"]


class CSVImportRow(BaseModel):
    """A single parsed CSV row, post-categorization. Returned to the user for review."""

    row_number: int  # 1-indexed (header is row 0)
    occurred_at: datetime
    amount: Decimal
    type: TransactionType
    description: str
    merchant: str | None = None
    category_id: UUID | None = None
    category_name: str | None = None
    ai_confidence: float | None = None
    needs_review: bool = False
    error: str | None = None  # set if this row could not be parsed


class CSVImportPreview(BaseModel):
    account_id: UUID
    rows: list[CSVImportRow]
    total_rows: int
    parseable_rows: int
    flagged_rows: int  # confidence < 0.7 OR error present


class CSVImportCommit(BaseModel):
    """User-confirmed rows to persist. The frontend may have edited categories or
    rejected rows before sending."""

    account_id: UUID
    rows: list[CSVImportRow] = Field(min_length=1, max_length=1000)


class CSVImportResult(BaseModel):
    created: int
    skipped: int
