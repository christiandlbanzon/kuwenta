"""Parse free-text quick-add into a structured transaction draft via LLM.

Pipeline:
  1. Load user's accounts (for account_hint matching).
  2. Render parse_quickadd prompt with account list and today's date in Asia/Manila.
  3. Call LLM `complete_structured` to get a `ParsedQuickAdd`.
  4. Resolve account_hint -> account_id (best fuzzy match), fall back to default_account_id
     if the hint doesn't match any account.

The result is a draft — the caller (api/transactions.py) returns it for user confirmation
before persisting.
"""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from app.llm.base import Message
from app.llm.prompts import load_prompt
from app.llm.router import get_provider_for_purpose
from app.llm.tracer import trace
from app.models.account import Account
from app.models.user import User
from app.schemas.transactions import QuickAddDraft

MANILA = ZoneInfo("Asia/Manila")


class ParsedQuickAdd(BaseModel):
    """Schema the LLM is constrained to return."""

    amount: Decimal = Field(ge=Decimal("0"))
    type: Literal["expense", "income", "transfer"]
    account_hint: str
    occurred_at: datetime
    description: str
    merchant_guess: str | None = None


def _resolve_account(
    accounts: list[Account], hint: str, fallback_id: UUID | None
) -> UUID:
    """Pick the account whose name best matches the LLM's hint.

    Strategy: exact (case-insensitive) match → substring match → fallback → first account.
    Kept deliberately simple — the LLM has already been guided to use the exact name.
    """
    if not accounts:
        raise ValueError("User has no accounts configured")
    hint_lower = hint.strip().lower()
    for acc in accounts:
        if acc.name.lower() == hint_lower:
            return acc.id
    for acc in accounts:
        if hint_lower in acc.name.lower() or acc.name.lower() in hint_lower:
            return acc.id
    if fallback_id is not None and any(a.id == fallback_id for a in accounts):
        return fallback_id
    return accounts[0].id


async def parse_quick_add(
    session: AsyncSession,
    user: User,
    text: str,
    *,
    default_account_id: UUID | None = None,
) -> QuickAddDraft:
    accounts = (
        await session.exec(select(Account).where(Account.user_id == user.id))
    ).all()
    if not accounts:
        raise ValueError("Add at least one account before quick-adding transactions.")

    accounts_block = "\n".join(
        f"- {a.name} (type: {a.type}{f', {a.institution}' if a.institution else ''})"
        for a in accounts
    )
    today_iso = datetime.now(MANILA).date().isoformat()
    template = load_prompt("parse_quickadd")
    prompt = template.format(
        accounts_block=accounts_block,
        today_iso=today_iso,
        text=text,
    )

    provider = get_provider_for_purpose("parse_quickadd")
    async with trace(
        session,
        user_id=user.id,
        purpose="parse_quickadd",
        provider=provider.name,
        model=provider.default_model,
    ) as t:
        sresult = await provider.complete_structured(
            [Message(role="user", content=prompt)],
            schema=ParsedQuickAdd,
        )
        t.tokens(sresult.input_tokens, sresult.output_tokens)

    parsed: ParsedQuickAdd = sresult.parsed  # type: ignore[assignment]
    account_id = _resolve_account(list(accounts), parsed.account_hint, default_account_id)

    return QuickAddDraft(
        amount=parsed.amount,
        type=parsed.type,
        account_id=account_id,
        category_id=None,  # categorization runs separately
        description=parsed.description,
        merchant=parsed.merchant_guess,
        occurred_at=parsed.occurred_at,
        ai_confidence=None,
        raw_input=text,
    )
