"""LLM-powered categorization with a per-user few-shot example store.

Few-shot examples come from two places:
1. Static seed examples shipped with the app (`app/llm/data/categorization_seed.jsonl`).
2. Per-user overrides — when a user changes the category on a transaction, we record
   (description, merchant, amount, chosen_category) as a future few-shot example.

The store lives at `data/few_shot/<user_id>.jsonl`. The seed file is bundled in the repo;
per-user overrides are user data.
"""

import json
from decimal import Decimal
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from app.config import get_settings
from app.llm.base import Message
from app.llm.prompts import load_prompt
from app.llm.router import get_provider_for_purpose
from app.llm.tracer import trace
from app.models.category import Category
from app.models.user import User

SEED_PATH = Path(__file__).parent.parent / "llm" / "data" / "categorization_seed.jsonl"
USER_FEW_SHOT_DIR = Path("./data/few_shot")
MAX_FEW_SHOT_EXAMPLES = 10


class CategorizationResult(BaseModel):
    category_name: str
    confidence: float = Field(ge=0.0, le=1.0)
    merchant: str | None = None


class CategorizationOutput(BaseModel):
    """What we return to callers — resolved to a category_id."""

    category_id: UUID | None
    category_name: str
    confidence: float
    merchant: str | None


def _load_seed_examples() -> list[dict[str, object]]:
    if not SEED_PATH.exists():
        return []
    out: list[dict[str, object]] = []
    for line in SEED_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.append(json.loads(line))
    return out


def _user_few_shot_path(user_id: UUID) -> Path:
    return USER_FEW_SHOT_DIR / f"{user_id}.jsonl"


def _load_user_examples(user_id: UUID) -> list[dict[str, object]]:
    path = _user_few_shot_path(user_id)
    if not path.exists():
        return []
    out: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def record_user_correction(
    user_id: UUID, *, description: str, merchant: str | None, amount: Decimal, category_name: str
) -> None:
    """Append a user override to their few-shot store. Append-only; older examples
    are pruned at read time to MAX_FEW_SHOT_EXAMPLES (most recent wins)."""
    USER_FEW_SHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = _user_few_shot_path(user_id)
    record = {
        "description": description,
        "merchant": merchant,
        "amount": str(amount),
        "category_name": category_name,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def _format_few_shot(examples: list[dict[str, object]]) -> str:
    if not examples:
        return "(none yet)"
    # Keep the most recent examples
    recent = examples[-MAX_FEW_SHOT_EXAMPLES:]
    return "\n".join(
        f"- \"{ex['description']}\" (merchant: {ex.get('merchant') or 'n/a'}, "
        f"₱{ex['amount']}) -> {ex['category_name']}"
        for ex in recent
    )


async def categorize(
    session: AsyncSession,
    user: User,
    *,
    description: str,
    merchant: str | None,
    amount: Decimal,
    txn_type: Literal["expense", "income", "transfer"] = "expense",
) -> CategorizationOutput:
    categories = (
        await session.exec(
            select(Category).where(Category.user_id == user.id, Category.type == txn_type)
        )
    ).all()
    if not categories:
        return CategorizationOutput(
            category_id=None, category_name="Others", confidence=0.0, merchant=merchant
        )

    cat_by_name = {c.name: c for c in categories}
    categories_block = "\n".join(f"- {c.name}" for c in categories)

    examples = _load_seed_examples() + _load_user_examples(user.id)
    few_shot_block = _format_few_shot(examples)

    template = load_prompt("categorization")
    prompt = template.format(
        categories_block=categories_block,
        few_shot_block=few_shot_block,
        description=description,
        merchant=merchant or "unknown",
        amount=amount,
        type=txn_type,
    )

    provider = get_provider_for_purpose("categorization")
    async with trace(
        session,
        user_id=user.id,
        purpose="categorization",
        provider=provider.name,
        model=provider.default_model,
    ) as t:
        sresult = await provider.complete_structured(
            [Message(role="user", content=prompt)],
            schema=CategorizationResult,
        )
        t.tokens(sresult.input_tokens, sresult.output_tokens)

    result: CategorizationResult = sresult.parsed  # type: ignore[assignment]
    matched = cat_by_name.get(result.category_name)
    return CategorizationOutput(
        category_id=matched.id if matched else None,
        category_name=result.category_name,
        confidence=result.confidence,
        merchant=result.merchant or merchant,
    )
