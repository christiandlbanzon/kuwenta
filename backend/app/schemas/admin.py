from datetime import datetime

from pydantic import BaseModel


class PerProviderStats(BaseModel):
    provider: str
    model: str
    total_calls: int
    success_calls: int
    error_calls: int
    p50_latency_ms: float
    p95_latency_ms: float
    total_input_tokens: int
    total_output_tokens: int


class PerPurposeStats(BaseModel):
    purpose: str
    total_calls: int
    success_rate: float
    p50_latency_ms: float
    total_input_tokens: int
    total_output_tokens: int


class LLMStats(BaseModel):
    """Aggregate stats from the LLMCall table for the calling user.

    Costs are projected as if running on Gemini's paid tier:
    - Gemini 2.5 Flash: $0.075 / 1M input tokens, $0.30 / 1M output tokens (approx).
    Even at production scale the projected cost is typically <$1/month for personal use.
    """

    period_start: datetime
    period_end: datetime
    total_calls: int
    by_provider: list[PerProviderStats]
    by_purpose: list[PerPurposeStats]
    total_input_tokens: int
    total_output_tokens: int
    projected_monthly_cost_usd: float
