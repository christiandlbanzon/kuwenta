from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from app.models._common import utcnow

InsightType = Literal["monthly_summary", "anomaly", "recurring_detected"]


class Insight(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", index=True)
    type: str  # one of InsightType
    title: str
    content: str
    insight_metadata: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    period_start: date
    period_end: date
    created_at: datetime = Field(default_factory=utcnow)
