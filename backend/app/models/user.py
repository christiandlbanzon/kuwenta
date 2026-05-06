from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel

from app.models._common import tz_now_column, utcnow


class User(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    display_name: str
    currency: str = "PHP"
    timezone: str = "Asia/Manila"
    created_at: datetime = Field(default_factory=utcnow, sa_column=tz_now_column())
