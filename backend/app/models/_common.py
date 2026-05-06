from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlmodel import Field


def uuid_pk() -> UUID:
    return Field(default_factory=uuid4, primary_key=True)  # type: ignore[return-value]


def utcnow() -> datetime:
    return datetime.now(UTC)
