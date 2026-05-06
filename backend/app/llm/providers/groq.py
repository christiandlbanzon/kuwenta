"""Groq provider — fallback path. Implementation deferred until needed.

Stub raises NotImplementedError so attempts to use it surface clearly at runtime
rather than silently failing or being mistaken for Gemini.
"""

from typing import Any

from pydantic import BaseModel

from app.llm.base import CompletionResult, Message, StructuredResult


class GroqProvider:
    name: str = "groq"
    default_model: str = "llama-3.3-70b-versatile"

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> CompletionResult:
        raise NotImplementedError("GroqProvider not yet implemented")

    async def complete_with_vision(
        self,
        messages: list[Message],
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
        *,
        model: str | None = None,
        temperature: float = 0.2,
    ) -> CompletionResult:
        raise NotImplementedError("Groq does not support vision; route to Gemini instead")

    async def complete_structured(
        self,
        messages: list[Message],
        schema: type[BaseModel],
        *,
        model: str | None = None,
        temperature: float = 0.2,
    ) -> StructuredResult:
        raise NotImplementedError("GroqProvider not yet implemented")
