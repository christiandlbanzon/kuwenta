"""/admin/llm-stats endpoint — verifies aggregations and user scoping."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.llm_call import LLMCall


async def test_llm_stats_aggregates_user_calls(
    client: AsyncClient, auth_headers: dict[str, str], session: AsyncSession
) -> None:
    # The auth_headers fixture has already created the test user.
    # Find the user_id from /auth/me
    me = (await client.get("/auth/me", headers=auth_headers)).json()
    user_id = UUID(me["id"])

    # Insert some LLMCall rows directly
    now = datetime.now(UTC)
    rows = [
        LLMCall(user_id=user_id, purpose="categorization", provider="gemini",
                model="gemini-2.5-flash", input_tokens=100, output_tokens=20,
                latency_ms=500, success=True, created_at=now),
        LLMCall(user_id=user_id, purpose="categorization", provider="gemini",
                model="gemini-2.5-flash", input_tokens=120, output_tokens=15,
                latency_ms=700, success=True, created_at=now),
        LLMCall(user_id=user_id, purpose="qa_planner", provider="gemini",
                model="gemini-2.5-flash", input_tokens=300, output_tokens=80,
                latency_ms=1200, success=True, created_at=now),
        LLMCall(user_id=user_id, purpose="ocr", provider="gemini",
                model="gemini-2.5-flash", input_tokens=2000, output_tokens=200,
                latency_ms=3500, success=False, error="rate_limit", created_at=now),
    ]
    for r in rows:
        session.add(r)
    await session.commit()

    resp = await client.get("/admin/llm-stats?days=7", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_calls"] == 4
    assert body["total_input_tokens"] == 100 + 120 + 300 + 2000
    assert body["total_output_tokens"] == 20 + 15 + 80 + 200

    # by_purpose includes categorization (2 calls) and qa_planner (1) and ocr (1)
    by_purpose = {p["purpose"]: p for p in body["by_purpose"]}
    assert by_purpose["categorization"]["total_calls"] == 2
    assert by_purpose["categorization"]["success_rate"] == 1.0
    assert by_purpose["ocr"]["success_rate"] == 0.0
    # Cost projection should be a small positive number
    assert body["projected_monthly_cost_usd"] >= 0


async def test_llm_stats_only_returns_calling_users_data(
    client: AsyncClient, auth_headers: dict[str, str], session: AsyncSession
) -> None:
    """Insert a row for a different user; current user's stats must NOT include it."""
    from uuid import uuid4

    other_user_id = uuid4()
    session.add(
        LLMCall(
            user_id=other_user_id, purpose="categorization", provider="gemini",
            model="gemini-2.5-flash", input_tokens=99999, output_tokens=99999,
            latency_ms=100, success=True, created_at=datetime.now(UTC),
        )
    )
    await session.commit()

    resp = await client.get("/admin/llm-stats?days=7", headers=auth_headers)
    body = resp.json()
    # Should not include the other user's 99999 tokens
    assert body["total_input_tokens"] < 99999
    assert body["total_output_tokens"] < 99999
