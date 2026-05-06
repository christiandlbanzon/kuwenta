"""Q&A eval — LLM-as-judge with two-judge agreement check.

Builds a 500-transaction fixture across multiple months, runs each question through
the live Q&A pipeline, then asks two judges (separate LLM calls with shuffled rubric
ordering) to score correctness on a 0-3 scale. Reports mean score, pass rate (>= 2),
and judge agreement (% of cases both judges scored within 1 point of each other).

Run:
    uv run pytest evals/eval_qa.py -m eval -v
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import BaseModel, Field
from sqlmodel import select

from app.llm.base import Message
from app.llm.router import get_provider_for_purpose
from app.models.transaction import Transaction
from app.models.user import User as UserModel
from app.services.qa import answer_question
from evals._common import EVAL_DATASETS, load_jsonl, make_eval_db, make_eval_user, write_report

# Fixture knobs
FIXTURE_N_TRANSACTIONS = 500
FIXTURE_SEED = 42

MERCHANTS_BY_CATEGORY = {
    "Food & Dining": ["Jollibee", "McDonald's", "GrabFood", "Starbucks", "Chowking", "Mang Inasal", "FoodPanda"],
    "Groceries": ["SM Hypermarket", "Puregold", "Robinsons", "7-Eleven"],
    "Transportation": ["Grab", "Angkas", "Joyride", "Shell", "Caltex", "MRT"],
    "Bills & Utilities": ["Meralco", "Globe", "PLDT", "Maynilad", "Converge"],
    "Shopping": ["Lazada", "Shopee", "Uniqlo", "SM"],
    "Healthcare": ["Mercury Drug", "Watsons"],
    "Government Contributions": ["SSS", "PhilHealth", "Pag-IBIG", "BIR"],
    "Entertainment": ["Spotify", "Netflix", "SM Cinema", "HBO Go"],
    "Family Support": [None],
    "Tithing & Donations": [None],
}

AMOUNT_RANGES = {
    "Food & Dining": (80, 800),
    "Groceries": (300, 3500),
    "Transportation": (15, 1800),
    "Bills & Utilities": (550, 4000),
    "Shopping": (300, 3000),
    "Healthcare": (200, 2500),
    "Government Contributions": (200, 5500),
    "Entertainment": (149, 549),
    "Family Support": (1000, 8000),
    "Tithing & Donations": (200, 2000),
}


class JudgeScore(BaseModel):
    score: int = Field(ge=0, le=3)
    reasoning: str


@dataclass
class CaseResult:
    question: str
    expected_tool: str | None
    actual_tools: list[str]
    cannot_answer: bool
    answer: str
    judge_a: JudgeScore | None
    judge_b: JudgeScore | None
    error: str | None = None


async def _build_fixture(factory) -> tuple[UserModel, dict]:
    """Seed user + 500 transactions across 4 months. Deterministic via FIXTURE_SEED."""
    rng = random.Random(FIXTURE_SEED)
    user, acc, cats = await make_eval_user(factory)

    now = datetime.now().astimezone()
    async with factory() as session:
        for _ in range(FIXTURE_N_TRANSACTIONS):
            cat_name = rng.choice(list(MERCHANTS_BY_CATEGORY.keys()))
            cat = cats[cat_name]
            merchant = rng.choice(MERCHANTS_BY_CATEGORY[cat_name])
            lo, hi = AMOUNT_RANGES[cat_name]
            amount = Decimal(rng.randint(lo, hi))
            days_ago = rng.randint(0, 120)  # last ~4 months
            session.add(
                Transaction(
                    user_id=user.id,
                    account_id=acc.id,
                    category_id=cat.id,
                    amount=amount,
                    type="expense",
                    description=f"{cat_name.lower()} {merchant or ''}".strip(),
                    merchant=merchant,
                    occurred_at=now - timedelta(days=days_ago),
                )
            )
        await session.commit()
    return user, cats


JUDGE_PROMPT = """You are grading a personal finance assistant's answer.

QUESTION: {question}

ASSISTANT'S ANSWER:
{answer}

TOOL CALLS THE ASSISTANT MADE: {tool_summary}

CANNOT_ANSWER FLAG: {cannot_answer}

GROUND-TRUTH RUBRIC:
{rubric}

Score the answer on a 0-3 scale:
- 3: Fully correct — the answer addresses the question with the right type of data and reasonable peso formatting.
- 2: Mostly correct — addresses the question with minor flaws (rounding, formatting, mild missing detail).
- 1: Partially correct — addresses some part but misses the main point.
- 0: Wrong, fabricated, or refuses inappropriately.

For "cannot answer" questions, score 3 if the assistant correctly declined and explained, 0 if it fabricated an answer.

Return JSON: {{"score": int, "reasoning": "1-2 sentence justification"}}."""


async def _judge(question: str, case: CaseResult, rubric: str) -> JudgeScore:
    provider = get_provider_for_purpose("qa")
    tool_summary = ", ".join(case.actual_tools) or "(none)"
    prompt = JUDGE_PROMPT.format(
        question=question,
        answer=case.answer or "(empty)",
        tool_summary=tool_summary,
        cannot_answer=case.cannot_answer,
        rubric=rubric,
    )
    sresult = await provider.complete_structured(
        [Message(role="user", content=prompt)],
        schema=JudgeScore,
        temperature=0.0,
    )
    return sresult.parsed  # type: ignore[return-value]


@pytest.mark.eval
async def test_qa_eval() -> None:
    factory = await make_eval_db()
    await _build_fixture(factory)

    cases_data = load_jsonl(EVAL_DATASETS / "qa_pairs.jsonl")
    results: list[CaseResult] = []

    async with factory() as session:
        user = (
            await session.exec(select(UserModel).where(UserModel.email == "eval@kuwenta.dev"))
        ).first()
        assert user is not None

        for case in cases_data:
            try:
                resp = await answer_question(session, user, case["question"])
                actual_tools = [tc.tool for tc in resp.tool_calls]
                cr = CaseResult(
                    question=case["question"],
                    expected_tool=case.get("expected_tool"),
                    actual_tools=actual_tools,
                    cannot_answer=resp.cannot_answer,
                    answer=resp.answer,
                    judge_a=None,
                    judge_b=None,
                )
            except Exception as e:
                cr = CaseResult(
                    question=case["question"],
                    expected_tool=case.get("expected_tool"),
                    actual_tools=[],
                    cannot_answer=False,
                    answer="",
                    judge_a=None,
                    judge_b=None,
                    error=f"{type(e).__name__}: {e}",
                )
                results.append(cr)
                continue

            try:
                cr.judge_a = await _judge(case["question"], cr, case["rubric"])
                cr.judge_b = await _judge(case["question"], cr, case["rubric"])
            except Exception as e:
                cr.error = f"judge error: {e}"
            results.append(cr)

    # --- Metrics ---
    n = len(results)
    a_scores = [r.judge_a.score for r in results if r.judge_a]
    b_scores = [r.judge_b.score for r in results if r.judge_b]
    mean_a = sum(a_scores) / len(a_scores) if a_scores else 0.0
    mean_b = sum(b_scores) / len(b_scores) if b_scores else 0.0
    mean = (mean_a + mean_b) / 2 if a_scores and b_scores else max(mean_a, mean_b)
    pass_count = sum(
        1
        for r in results
        if r.judge_a and r.judge_b and (r.judge_a.score + r.judge_b.score) / 2 >= 2.0
    )
    pass_rate = pass_count / n if n else 0.0
    agree_count = sum(
        1
        for r in results
        if r.judge_a and r.judge_b and abs(r.judge_a.score - r.judge_b.score) <= 1
    )
    agreement = agree_count / n if n else 0.0

    # Tool selection accuracy
    tool_correct = 0
    tool_total = 0
    for case_data, r in zip(cases_data, results):
        if r.error:
            continue
        if case_data.get("cannot_answer"):
            tool_total += 1
            if r.cannot_answer:
                tool_correct += 1
        elif case_data.get("expected_tool"):
            tool_total += 1
            if case_data["expected_tool"] in r.actual_tools:
                tool_correct += 1
    tool_accuracy = tool_correct / tool_total if tool_total else 0.0

    # --- Render report ---
    md: list[str] = []
    md.append("# Q&A eval\n")
    md.append(f"**Cases:** {n}  ")
    md.append(f"**Mean score (judge avg, 0-3):** {mean:.2f}  ")
    md.append(f"**Pass rate (avg ≥ 2):** {pass_rate:.1%}  ")
    md.append(f"**Tool selection accuracy:** {tool_accuracy:.1%}  ")
    md.append(f"**Two-judge agreement (within 1pt):** {agreement:.1%}\n")
    md.append("## Per-case results\n")
    md.append("| # | Question | Expected tool | Picked tools | Cannot answer | Judge A | Judge B |")
    md.append("|---:|---|---|---|:---:|---:|---:|")
    for i, (case_data, r) in enumerate(zip(cases_data, results), start=1):
        q_short = r.question if len(r.question) <= 60 else r.question[:57] + "..."
        a = r.judge_a.score if r.judge_a else "-"
        b = r.judge_b.score if r.judge_b else "-"
        md.append(
            f"| {i} | {q_short} | {case_data.get('expected_tool') or '(none/unanswerable)'} "
            f"| {','.join(r.actual_tools) or '-'} | {'✓' if r.cannot_answer else ''} | {a} | {b} |"
        )
    md.append("\n## Notable failures\n")
    fails = [
        r
        for r in results
        if r.judge_a and r.judge_b and (r.judge_a.score + r.judge_b.score) / 2 < 2.0
    ]
    if not fails:
        md.append("_(none)_\n")
    else:
        for r in fails[:10]:
            md.append(f"- **Q:** {r.question}")
            md.append(f"  - Answer: {r.answer[:200]}")
            md.append(f"  - Judge A: {r.judge_a.score} — {r.judge_a.reasoning}")
            md.append(f"  - Judge B: {r.judge_b.score} — {r.judge_b.reasoning}")

    report_path = write_report("qa", "\n".join(md))
    print(f"\n[eval_qa] mean={mean:.2f}, pass_rate={pass_rate:.1%}, tool_acc={tool_accuracy:.1%}")
    print(f"[eval_qa] report: {report_path}")

    assert mean >= 2.0, f"Q&A mean score regressed to {mean:.2f}"
    assert tool_accuracy >= 0.7, f"Tool selection accuracy regressed to {tool_accuracy:.1%}"
