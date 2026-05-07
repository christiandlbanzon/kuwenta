"""Admin endpoints — observability dashboards over the LLMCall table.

Scoped to the calling user. There's no superuser concept in v1; each user only sees
their own LLM call stats.
"""

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Query
from sqlmodel import select

from app.core.deps import CurrentUser, SessionDep
from app.models.llm_call import LLMCall
from app.schemas.admin import LLMStats, PerProviderStats, PerPurposeStats

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/diag")
async def diag(user: CurrentUser) -> dict[str, object]:
    """Auth-gated diagnostic — confirms env config + actually exercises the LLM.

    Surfaces the underlying error message so deploy issues can be debugged
    without log access. Never exposes the actual key values.
    """
    from app.config import get_settings
    from app.llm.base import Message
    from app.llm.router import get_provider_for_purpose

    s = get_settings()
    out: dict[str, object] = {
        "env": s.app_env,
        "providers": {
            "gemini_configured": bool(s.gemini_api_key),
            "groq_configured": bool(s.groq_api_key),
        },
        "rate_limit_per_min": s.gemini_rate_limit_per_min,
        "cors_origins": [o.strip() for o in s.cors_origins.split(",") if o.strip()],
    }

    # Live Gemini ping — exact failure mode that's blocking quick-add
    try:
        provider = get_provider_for_purpose("categorization")
        result = await provider.complete(
            [Message(role="user", content="Reply with exactly: pong")],
            temperature=0.0,
        )
        out["gemini_live_check"] = {
            "ok": True,
            "text": result.text[:50],
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
        }
    except Exception as e:
        out["gemini_live_check"] = {
            "ok": False,
            "error_type": type(e).__name__,
            "error": str(e)[:500],
        }

    return out

# Approximate Gemini 2.5 Flash paid pricing (USD per 1M tokens).
# Used purely to project costs from the free-tier LLMCall data.
COST_PER_M_INPUT = 0.075
COST_PER_M_OUTPUT = 0.30


def _percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    idx = max(0, min(len(sorted_values) - 1, int(round((p / 100) * (len(sorted_values) - 1)))))
    return sorted_values[idx]


@router.get("/llm-stats", response_model=LLMStats)
async def llm_stats(
    user: CurrentUser,
    session: SessionDep,
    days: Annotated[int, Query(ge=1, le=90)] = 7,
) -> LLMStats:
    end = datetime.now(UTC)
    start = end - timedelta(days=days)
    rows = (
        await session.exec(
            select(LLMCall).where(
                LLMCall.user_id == user.id,
                LLMCall.created_at >= start,
                LLMCall.created_at <= end,
            )
        )
    ).all()

    # --- Aggregate by (provider, model) ---
    by_pm: dict[tuple[str, str], list[LLMCall]] = defaultdict(list)
    for r in rows:
        by_pm[(r.provider, r.model)].append(r)

    provider_stats: list[PerProviderStats] = []
    for (provider, model), calls in by_pm.items():
        latencies = sorted(c.latency_ms for c in calls)
        provider_stats.append(
            PerProviderStats(
                provider=provider,
                model=model,
                total_calls=len(calls),
                success_calls=sum(1 for c in calls if c.success),
                error_calls=sum(1 for c in calls if not c.success),
                p50_latency_ms=_percentile(latencies, 50),
                p95_latency_ms=_percentile(latencies, 95),
                total_input_tokens=sum(c.input_tokens or 0 for c in calls),
                total_output_tokens=sum(c.output_tokens or 0 for c in calls),
            )
        )

    # --- Aggregate by purpose ---
    by_purpose: dict[str, list[LLMCall]] = defaultdict(list)
    for r in rows:
        by_purpose[r.purpose].append(r)

    purpose_stats: list[PerPurposeStats] = []
    for purpose, calls in by_purpose.items():
        latencies = sorted(c.latency_ms for c in calls)
        ok = sum(1 for c in calls if c.success)
        purpose_stats.append(
            PerPurposeStats(
                purpose=purpose,
                total_calls=len(calls),
                success_rate=ok / len(calls) if calls else 0.0,
                p50_latency_ms=_percentile(latencies, 50),
                total_input_tokens=sum(c.input_tokens or 0 for c in calls),
                total_output_tokens=sum(c.output_tokens or 0 for c in calls),
            )
        )

    total_in = sum(c.input_tokens or 0 for c in rows)
    total_out = sum(c.output_tokens or 0 for c in rows)
    # Project to monthly assuming current pace (linear)
    days_observed = max(1, days)
    monthly_in = total_in * (30 / days_observed)
    monthly_out = total_out * (30 / days_observed)
    projected_cost = (monthly_in / 1_000_000) * COST_PER_M_INPUT + (
        monthly_out / 1_000_000
    ) * COST_PER_M_OUTPUT

    return LLMStats(
        period_start=start,
        period_end=end,
        total_calls=len(rows),
        by_provider=sorted(provider_stats, key=lambda s: -s.total_calls),
        by_purpose=sorted(purpose_stats, key=lambda s: -s.total_calls),
        total_input_tokens=total_in,
        total_output_tokens=total_out,
        projected_monthly_cost_usd=round(projected_cost, 4),
    )
