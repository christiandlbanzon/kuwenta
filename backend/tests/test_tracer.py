from uuid import uuid4

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from app.llm.tracer import trace
from app.models.llm_call import LLMCall


async def test_tracer_records_success(session: AsyncSession) -> None:
    user_id = uuid4()
    async with trace(
        session, user_id=user_id, purpose="categorization", provider="gemini", model="m"
    ) as t:
        t.tokens(123, 45)

    rows = (await session.exec(select(LLMCall))).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.success is True
    assert row.input_tokens == 123
    assert row.output_tokens == 45
    assert row.purpose == "categorization"
    assert row.user_id == user_id
    assert row.error is None
    assert row.latency_ms >= 0


async def test_tracer_records_error_and_reraises(session: AsyncSession) -> None:
    with pytest.raises(RuntimeError, match="boom"):
        async with trace(
            session, user_id=None, purpose="qa", provider="gemini", model="m"
        ):
            raise RuntimeError("boom")

    rows = (await session.exec(select(LLMCall))).all()
    assert len(rows) == 1
    assert rows[0].success is False
    assert "boom" in (rows[0].error or "")
