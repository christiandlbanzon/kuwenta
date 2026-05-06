from typing import Literal
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel

CategoryType = Literal["expense", "income"]


class Category(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", index=True)
    name: str
    type: str  # one of CategoryType
    parent_id: UUID | None = Field(default=None, foreign_key="category.id")
    icon: str | None = None
    color: str | None = None
    is_default: bool = False
