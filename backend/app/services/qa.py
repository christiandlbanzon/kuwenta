"""Q&A service — orchestrates planner -> tool execution -> summarizer.

Flow:
    1. Build the tool catalog (JSON schemas + descriptions) and render qa_planner with
       the user's question.
    2. Planner LLM returns a PlannerDecision (invocations + cannot_answer flag).
    3. For each invocation, validate (whitelist + Pydantic args schema) and execute the
       tool scoped to user_id.
    4. Render qa_summarizer with the original question + tool results.
    5. Return summarized answer + tool call trace for transparency.

Each LLM call is wrapped in `trace(...)` so it shows up in the LLMCall table.
"""

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlmodel.ext.asyncio.session import AsyncSession

from app.llm.base import Message
from app.llm.prompts import load_prompt
from app.llm.router import get_provider_for_purpose
from app.llm.tracer import trace
from app.models.user import User
from app.schemas.qa import PlannerDecision, QAResponse, ToolCallTrace
from app.tools.finance_tools import (
    ToolValidationError,
    execute_tool,
    tool_schemas_for_planner,
)


def _format_tool_catalog() -> str:
    schemas = tool_schemas_for_planner()
    lines: list[str] = []
    for s in schemas:
        lines.append(f"### {s['name']}")
        if s["description"]:
            lines.append(s["description"])
        lines.append("```json")
        lines.append(json.dumps(s["parameters"], indent=2))
        lines.append("```")
    return "\n".join(lines)


async def answer_question(
    session: AsyncSession, user: User, question: str
) -> QAResponse:
    timezone = user.timezone or "Asia/Manila"
    today_iso = datetime.now(ZoneInfo(timezone)).date().isoformat()

    # --- 1. Planner ---
    planner_template = load_prompt("qa_planner")
    planner_prompt = planner_template.format(
        today_iso=today_iso,
        tool_catalog=_format_tool_catalog(),
        question=question,
    )
    planner_provider = get_provider_for_purpose("qa")
    async with trace(
        session,
        user_id=user.id,
        purpose="qa_planner",
        provider=planner_provider.name,
        model=planner_provider.default_model,
    ) as t:
        plan_sr = await planner_provider.complete_structured(
            [Message(role="user", content=planner_prompt)],
            schema=PlannerDecision,
        )
        t.tokens(plan_sr.input_tokens, plan_sr.output_tokens)
    plan: PlannerDecision = plan_sr.parsed  # type: ignore[assignment]

    # --- 2. Execute tools ---
    traces: list[ToolCallTrace] = []
    if not plan.cannot_answer:
        for inv in plan.invocations:
            t = ToolCallTrace(tool=inv.tool, args=inv.args)
            try:
                t.result = await execute_tool(
                    inv.tool,
                    inv.args,
                    user_id=user.id,
                    session=session,
                    timezone=timezone,
                )
            except ToolValidationError as e:
                t.error = f"validation_error: {e}"
            except Exception as e:  # pragma: no cover — surface unexpected errors
                t.error = f"{type(e).__name__}: {e}"
            traces.append(t)

    # --- 3. Summarizer ---
    summarizer_template = load_prompt("qa_summarizer")
    if plan.cannot_answer:
        # No tool results — let summarizer explain the limitation
        results_payload = {"cannot_answer": True, "reason": plan.reason}
    else:
        results_payload = {"calls": [t.model_dump() for t in traces]}

    summarizer_prompt = summarizer_template.format(
        today_iso=today_iso,
        question=question,
        tool_results=json.dumps(results_payload, default=str, indent=2),
    )
    sum_provider = get_provider_for_purpose("qa")
    async with trace(
        session,
        user_id=user.id,
        purpose="qa_summarizer",
        provider=sum_provider.name,
        model=sum_provider.default_model,
    ) as t2:
        completion = await sum_provider.complete(
            [Message(role="user", content=summarizer_prompt)],
            temperature=0.3,
        )
        t2.tokens(completion.input_tokens, completion.output_tokens)
    return QAResponse(
        answer=completion.text.strip() or "(no answer)",
        tool_calls=traces,
        cannot_answer=plan.cannot_answer,
    )
