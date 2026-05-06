from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

PaymentMethod = Literal[
    "cash", "gcash", "credit_card", "debit_card", "maya", "paymaya", "bank_transfer", "other"
]


class ReceiptLineItem(BaseModel):
    name: str
    quantity: float | None = None
    amount: Decimal


class ReceiptExtraction(BaseModel):
    """LLM-constrained schema for vision OCR output."""

    merchant: str | None = None
    line_items: list[ReceiptLineItem] = Field(default_factory=list)
    subtotal: Decimal | None = None
    tax: Decimal | None = None
    total: Decimal | None = None
    occurred_at: datetime | None = None
    payment_method: PaymentMethod | None = None
    category_guess: str | None = None


class ReceiptUploadResponse(BaseModel):
    """Returned to the frontend after a receipt upload — a draft for confirmation."""

    receipt_id: UUID
    image_path: str
    extracted: ReceiptExtraction
    suggested_category_id: UUID | None
    suggested_account_id: UUID | None  # picked from payment_method hint
