from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

InsightType = Literal["monthly_summary", "anomaly", "recurring_detected"]


class InsightPublic(BaseModel):
    id: UUID
    type: InsightType
    title: str
    content: str  # markdown
    insight_metadata: dict[str, Any] = Field(default_factory=dict)
    period_start: date
    period_end: date
    created_at: datetime


class GenerateMonthlySummaryRequest(BaseModel):
    """Optional override for ad-hoc generation (otherwise scheduler picks last month)."""

    year: int | None = None
    month: int | None = None


class AnomalyFlag(BaseModel):
    """One detected anomaly, before LLM explanation."""

    category_id: UUID
    category_name: str
    period_start: date
    period_end: date
    current_total: Decimal
    baseline_mean: Decimal
    baseline_stddev: Decimal
    z_score: float  # how many stddevs above the mean
    contributing_transaction_ids: list[UUID]
