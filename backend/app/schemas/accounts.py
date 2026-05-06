from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

AccountType = Literal["cash", "bank", "ewallet", "credit_card"]


class AccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    type: AccountType
    institution: str | None = Field(default=None, max_length=100)
    current_balance: Decimal = Decimal("0")


class AccountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    institution: str | None = None
    current_balance: Decimal | None = None


class AccountPublic(BaseModel):
    id: UUID
    name: str
    type: AccountType
    institution: str | None
    current_balance: Decimal
    created_at: datetime
