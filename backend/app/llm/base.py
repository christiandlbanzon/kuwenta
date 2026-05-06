from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel

Role = Literal["system", "user", "assistant", "tool"]


@dataclass
class Message:
    role: Role
    content: str
    name: str | None = None  # for tool messages


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]
    call_id: str


@dataclass
class CompletionResult:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    input_tokens: int | None = None
    output_tokens: int | None = None
    raw: Any = None


@dataclass
class StructuredResult:
    """Returned by `complete_structured` — bundles the parsed model with usage stats
    so the tracer can record tokens for structured calls."""

    parsed: BaseModel
    input_tokens: int | None = None
    output_tokens: int | None = None
    raw: Any = None


@runtime_checkable
class LLMProvider(Protocol):
    name: str
    default_model: str

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> CompletionResult: ...

    async def complete_with_vision(
        self,
        messages: list[Message],
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
        *,
        model: str | None = None,
        temperature: float = 0.2,
    ) -> CompletionResult: ...

    async def complete_structured(
        self,
        messages: list[Message],
        schema: type[BaseModel],
        *,
        model: str | None = None,
        temperature: float = 0.2,
    ) -> StructuredResult: ...
