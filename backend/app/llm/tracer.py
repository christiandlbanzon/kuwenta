"""SQLite-backed LLM call tracer.

Usage:
    async with trace(session, user_id=user.id, purpose="categorization",
                     provider="gemini", model="gemini-2.0-flash") as t:
        result = await provider.complete(messages)
        t.tokens(result.input_tokens, result.output_tokens)

The context manager records latency, success/error, and writes one LLMCall row per call.
Errors raised inside the block are recorded and re-raised — the caller sees them normally.
"""

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.llm_call import LLMCall


class TraceCtx:
    def __init__(self) -> None:
        self.input_tokens: int | None = None
        self.output_tokens: int | None = None

    def tokens(self, input_tokens: int | None, output_tokens: int | None) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


@asynccontextmanager
async def trace(
    session: AsyncSession,
    *,
    user_id: UUID | None,
    purpose: str,
    provider: str,
    model: str,
) -> AsyncIterator[TraceCtx]:
    ctx = TraceCtx()
    start = time.monotonic()
    success = True
    error: str | None = None
    try:
        yield ctx
    except Exception as e:
        success = False
        error = f"{type(e).__name__}: {e}"[:500]
        raise
    finally:
        latency_ms = int((time.monotonic() - start) * 1000)
        record = LLMCall(
            user_id=user_id,
            purpose=purpose,
            provider=provider,
            model=model,
            input_tokens=ctx.input_tokens,
            output_tokens=ctx.output_tokens,
            latency_ms=latency_ms,
            success=success,
            error=error,
        )
        session.add(record)
        try:
            await session.commit()
        except Exception:
            await session.rollback()
