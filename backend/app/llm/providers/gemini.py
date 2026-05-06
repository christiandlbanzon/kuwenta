"""Gemini provider using the `google-genai` SDK (the new, async-capable client)."""

import asyncio
import logging
import random
from typing import Any, Awaitable, Callable, TypeVar, cast

from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel

from app.config import get_settings
from app.llm.base import CompletionResult, Message, StructuredResult, ToolCall
from app.llm.rate_limit import TokenBucket

log = logging.getLogger("kuwenta.gemini")
T = TypeVar("T")


async def _with_retry(
    fn: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = 2,
    base_delay: float = 1.5,
) -> T:
    """Retry transient errors (429, 5xx, network) with exponential backoff + jitter."""
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await fn()
        except genai_errors.APIError as e:
            last_exc = e
            status = getattr(e, "code", None)
            transient = status == 429 or (isinstance(status, int) and 500 <= status < 600)
            if not transient or attempt >= max_attempts:
                raise
            delay = base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
            log.warning(
                "Gemini transient error %s; retrying in %.1fs (attempt %d/%d)",
                status, delay, attempt, max_attempts,
            )
            await asyncio.sleep(delay)
    assert last_exc is not None
    raise last_exc


class GeminiProvider:
    name: str = "gemini"
    default_model: str = "gemini-2.5-flash"

    def __init__(self, api_key: str | None = None, *, rate_per_min: int | None = None) -> None:
        settings = get_settings()
        api_key = api_key or settings.gemini_api_key
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY not set. Add it to .env or pass api_key= to GeminiProvider()."
            )
        self._client = genai.Client(api_key=api_key)
        self._bucket = TokenBucket(rate_per_min or settings.gemini_rate_limit_per_min)

    @staticmethod
    def _split_messages(messages: list[Message]) -> tuple[str | None, list[types.Content]]:
        system_parts = [m.content for m in messages if m.role == "system"]
        system = "\n\n".join(system_parts) if system_parts else None
        contents: list[types.Content] = []
        for m in messages:
            if m.role == "system":
                continue
            role = "user" if m.role in ("user", "tool") else "model"
            contents.append(types.Content(role=role, parts=[types.Part.from_text(text=m.content)]))
        return system, contents

    @staticmethod
    def _extract_tool_calls(response: Any) -> list[ToolCall]:
        calls: list[ToolCall] = []
        for cand in response.candidates or []:
            content = getattr(cand, "content", None)
            if not content:
                continue
            for part in content.parts or []:
                fc = getattr(part, "function_call", None)
                if fc and fc.name:
                    calls.append(
                        ToolCall(
                            name=fc.name,
                            arguments=dict(fc.args or {}),
                            call_id=getattr(fc, "id", None) or fc.name,
                        )
                    )
        return calls

    @staticmethod
    def _usage(response: Any) -> tuple[int | None, int | None]:
        usage = getattr(response, "usage_metadata", None)
        return (
            getattr(usage, "prompt_token_count", None),
            getattr(usage, "candidates_token_count", None),
        )

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> CompletionResult:
        await self._bucket.acquire()
        system, contents = self._split_messages(messages)
        config_kwargs: dict[str, Any] = {"temperature": temperature}
        if max_tokens:
            config_kwargs["max_output_tokens"] = max_tokens
        if system:
            config_kwargs["system_instruction"] = system
        if tools:
            config_kwargs["tools"] = [types.Tool(function_declarations=tools)]
        config = types.GenerateContentConfig(**config_kwargs)

        resp = await _with_retry(
            lambda: self._client.aio.models.generate_content(
                model=model or self.default_model, contents=contents, config=config
            )
        )
        in_tok, out_tok = self._usage(resp)
        return CompletionResult(
            text=getattr(resp, "text", "") or "",
            tool_calls=self._extract_tool_calls(resp),
            input_tokens=in_tok,
            output_tokens=out_tok,
            raw=resp,
        )

    async def complete_with_vision(
        self,
        messages: list[Message],
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
        *,
        model: str | None = None,
        temperature: float = 0.2,
    ) -> CompletionResult:
        await self._bucket.acquire()
        system, contents = self._split_messages(messages)
        image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        if contents and contents[-1].role == "user":
            contents[-1].parts.append(image_part)
        else:
            contents.append(types.Content(role="user", parts=[image_part]))
        config_kwargs: dict[str, Any] = {"temperature": temperature}
        if system:
            config_kwargs["system_instruction"] = system
        config = types.GenerateContentConfig(**config_kwargs)
        resp = await _with_retry(
            lambda: self._client.aio.models.generate_content(
                model=model or self.default_model, contents=contents, config=config
            )
        )
        in_tok, out_tok = self._usage(resp)
        return CompletionResult(
            text=getattr(resp, "text", "") or "",
            input_tokens=in_tok,
            output_tokens=out_tok,
            raw=resp,
        )

    async def complete_structured(
        self,
        messages: list[Message],
        schema: type[BaseModel],
        *,
        model: str | None = None,
        temperature: float = 0.2,
    ) -> StructuredResult:
        await self._bucket.acquire()
        system, contents = self._split_messages(messages)
        config_kwargs: dict[str, Any] = {
            "temperature": temperature,
            "response_mime_type": "application/json",
            "response_schema": schema,
        }
        if system:
            config_kwargs["system_instruction"] = system
        config = types.GenerateContentConfig(**config_kwargs)
        resp = await _with_retry(
            lambda: self._client.aio.models.generate_content(
                model=model or self.default_model, contents=contents, config=config
            )
        )
        parsed_obj = getattr(resp, "parsed", None)
        if parsed_obj is None:
            parsed_obj = schema.model_validate_json(getattr(resp, "text", "") or "{}")
        in_tok, out_tok = self._usage(resp)
        return StructuredResult(
            parsed=cast(BaseModel, parsed_obj),
            input_tokens=in_tok,
            output_tokens=out_tok,
            raw=resp,
        )
