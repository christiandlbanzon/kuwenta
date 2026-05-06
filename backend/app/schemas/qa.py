from typing import Any

from pydantic import BaseModel, Field


class QARequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)


class ToolInvocation(BaseModel):
    tool: str
    args: dict[str, Any]


class PlannerDecision(BaseModel):
    """Schema the planner LLM is constrained to return."""

    invocations: list[ToolInvocation] = Field(default_factory=list, max_length=4)
    cannot_answer: bool = False
    reason: str = ""


class ToolCallTrace(BaseModel):
    tool: str
    args: dict[str, Any]
    result: dict[str, Any] | None = None
    error: str | None = None


class QAResponse(BaseModel):
    answer: str
    tool_calls: list[ToolCallTrace]
    cannot_answer: bool = False
