from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel

from app.models._common import tz_now_column, utcnow


class LLMCall(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID | None = Field(default=None, foreign_key="user.id", index=True)
    purpose: str  # categorization, qa, ocr, insights, parse_quickadd
    provider: str  # gemini, groq, ollama
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int
    success: bool
    error: str | None = None
    created_at: datetime = Field(default_factory=utcnow, sa_column=tz_now_column(indexed=True))
