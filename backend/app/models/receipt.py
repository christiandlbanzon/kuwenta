from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from app.models._common import tz_now_column, utcnow


class Receipt(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", index=True)
    transaction_id: UUID | None = Field(default=None, foreign_key="transaction.id")
    image_path: str
    extracted_data: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    uploaded_at: datetime = Field(default_factory=utcnow, sa_column=tz_now_column())
