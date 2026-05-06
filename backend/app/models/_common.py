from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime
from sqlmodel import Field


def uuid_pk() -> UUID:
    return Field(default_factory=uuid4, primary_key=True)  # type: ignore[return-value]


def utcnow() -> datetime:
    return datetime.now(UTC)


def tz_now_column(*, indexed: bool = False) -> Any:
    """A `DateTime(timezone=True)` column with `utcnow()` default and optional index.

    Use as `sa_column=tz_now_column()` on SQLModel datetime fields. Necessary because
    asyncpg refuses tz-aware datetimes into TIMESTAMP WITHOUT TIME ZONE columns
    (which is what `sa.DateTime()` translates to). Postgres prod = tz-aware all the way.
    """
    return Column(
        DateTime(timezone=True),
        nullable=False,
        index=indexed,
        default=utcnow,
    )


def tz_column(*, indexed: bool = False, nullable: bool = False) -> Any:
    """A `DateTime(timezone=True)` column WITHOUT a default — for fields the caller
    sets explicitly (like `Transaction.occurred_at`)."""
    return Column(
        DateTime(timezone=True),
        nullable=nullable,
        index=indexed,
    )
