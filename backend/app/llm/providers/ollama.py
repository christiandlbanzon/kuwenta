"""Ollama provider — local dev only. Implementation deferred."""

from typing import Any

from pydantic import BaseModel

from app.llm.base import CompletionResult, Message, StructuredResult


class OllamaProvider:
    name: str = "ollama"
    default_model: str = "qwen2.5"

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> CompletionResult:
        raise NotImplementedError("OllamaProvider not yet implemented")

    async def complete_with_vision(
        self,
        messages: list[Message],
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
        *,
        model: str | None = None,
        temperature: float = 0.2,
    ) -> CompletionResult:
        raise NotImplementedError("OllamaProvider not yet implemented")

    async def complete_structured(
        self,
        messages: list[Message],
        schema: type[BaseModel],
        *,
        model: str | None = None,
        temperature: float = 0.2,
    ) -> StructuredResult:
        raise NotImplementedError("OllamaProvider not yet implemented")
