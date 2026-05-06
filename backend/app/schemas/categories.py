from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

CategoryType = Literal["expense", "income"]


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    type: CategoryType
    parent_id: UUID | None = None
    icon: str | None = None
    color: str | None = None


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    icon: str | None = None
    color: str | None = None


class CategoryPublic(BaseModel):
    id: UUID
    name: str
    type: CategoryType
    parent_id: UUID | None
    icon: str | None
    color: str | None
    is_default: bool
