"""CSV import — preview (parse + batch categorize) and commit (bulk save).

Expected CSV format (header is required):
    occurred_at,amount,description,type,merchant
    2026-04-15,180.00,jollibee lunch,expense,Jollibee
    2026-04-15,3200.00,meralco bill,expense,Meralco

- `occurred_at` accepts ISO-8601 dates or datetimes. Date-only is interpreted as
  local-noon Asia/Manila (matches our quick-add convention).
- `type` defaults to "expense" if missing.
- `merchant` is optional.

Categorization runs in batches of `BATCH_SIZE` rows per LLM call (one structured
output containing N predictions) to keep within Gemini's free-tier rate limit.
Confidence < 0.7 marks the row as `needs_review`.
"""

from __future__ import annotations

import csv
import io
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
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
from app.models.category import Category
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.imports import CSVImportPreview, CSVImportResult, CSVImportRow

MANILA = ZoneInfo("Asia/Manila")
BATCH_SIZE = 20


class _RowPrediction(BaseModel):
    row_number: int
    category_name: str
    confidence: float = Field(ge=0.0, le=1.0)
    merchant: str | None = None


class _BatchCategorization(BaseModel):
    """Schema the LLM returns for one batch of rows."""

    predictions: list[_RowPrediction] = Field(default_factory=list)


def _parse_datetime(raw: str) -> datetime:
    raw = raw.strip()
    # Try ISO datetime first
    try:
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=MANILA)
        return dt
    except ValueError:
        pass
    # Date-only: interpret as local noon
    d = date.fromisoformat(raw)
    return datetime(d.year, d.month, d.day, 12, 0, 0, tzinfo=MANILA)


def parse_csv(content: bytes) -> tuple[list[CSVImportRow], int]:
    """Parse raw CSV bytes into rows. Returns (rows, total_count). Rows that fail to
    parse are still returned with an `error` set so the user can see them."""
    text = content.decode("utf-8-sig")  # strip BOM if present
    reader = csv.DictReader(io.StringIO(text))
    rows: list[CSVImportRow] = []
    for i, raw in enumerate(reader, start=1):
        try:
            occurred_at = _parse_datetime(raw["occurred_at"])
            amount = Decimal(str(raw["amount"]).replace(",", "").replace("₱", "").strip())
            if amount <= 0:
                raise ValueError("amount must be positive")
            txn_type = (raw.get("type") or "expense").strip().lower()
            if txn_type not in ("expense", "income", "transfer"):
                raise ValueError(f"invalid type: {txn_type!r}")
            description = (raw.get("description") or "").strip()
            if not description:
                raise ValueError("description is required")
            merchant = (raw.get("merchant") or "").strip() or None
            rows.append(
                CSVImportRow(
                    row_number=i,
                    occurred_at=occurred_at,
                    amount=amount,
                    type=txn_type,  # type: ignore[arg-type]
                    description=description,
                    merchant=merchant,
                )
            )
        except (KeyError, ValueError, InvalidOperation) as e:
            rows.append(
                CSVImportRow(
                    row_number=i,
                    occurred_at=datetime.now(MANILA),
                    amount=Decimal("0"),
                    type="expense",
                    description="(unparseable)",
                    error=str(e),
                )
            )
    return rows, len(rows)


async def _categorize_batch(
    session: AsyncSession,
    user: User,
    batch: list[CSVImportRow],
    cat_by_name: dict[str, Category],
) -> None:
    """Run one LLM call on a batch and mutate rows in place with category + confidence."""
    if not batch:
        return
    cats_block = "\n".join(f"- {name}" for name in cat_by_name)
    rows_block = "\n".join(
        f"- row {r.row_number}: \"{r.description}\" "
        f"(merchant: {r.merchant or 'n/a'}, ₱{r.amount}, {r.type})"
        for r in batch
    )
    instructions = (
        "Categorize each transaction below into one of the user's categories.\n\n"
        f"User's categories:\n{cats_block}\n\n"
        f"Transactions:\n{rows_block}\n\n"
        "Output JSON: {\"predictions\": [{\"row_number\": int, \"category_name\": "
        "string from the list above, \"confidence\": 0..1, \"merchant\": string|null}]}\n"
        "Confidence below 0.7 will be flagged for the user to review."
    )

    provider = get_provider_for_purpose("categorization")
    async with trace(
        session,
        user_id=user.id,
        purpose="categorization_batch",
        provider=provider.name,
        model=provider.default_model,
    ) as t:
        sresult = await provider.complete_structured(
            [Message(role="user", content=instructions)],
            schema=_BatchCategorization,
        )
        t.tokens(sresult.input_tokens, sresult.output_tokens)
    result: _BatchCategorization = sresult.parsed  # type: ignore[assignment]

    by_row = {p.row_number: p for p in result.predictions}
    for row in batch:
        pred = by_row.get(row.row_number)
        if not pred:
            row.needs_review = True
            continue
        cat = cat_by_name.get(pred.category_name)
        row.category_id = cat.id if cat else None
        row.category_name = pred.category_name
        row.ai_confidence = pred.confidence
        row.needs_review = pred.confidence < 0.7 or cat is None
        if pred.merchant and not row.merchant:
            row.merchant = pred.merchant


async def preview_import(
    session: AsyncSession,
    user: User,
    *,
    account_id: UUID,
    csv_bytes: bytes,
) -> CSVImportPreview:
    # Validate account ownership
    acc = (
        await session.exec(
            select(Account).where(Account.user_id == user.id, Account.id == account_id)
        )
    ).first()
    if not acc:
        raise ValueError("Account not found or not owned by user")

    rows, total = parse_csv(csv_bytes)
    parseable = [r for r in rows if r.error is None]
    cats = (
        await session.exec(
            select(Category).where(Category.user_id == user.id)
        )
    ).all()
    cat_by_name = {c.name: c for c in cats}

    # Categorize in batches
    for i in range(0, len(parseable), BATCH_SIZE):
        await _categorize_batch(session, user, parseable[i : i + BATCH_SIZE], cat_by_name)

    flagged = sum(1 for r in rows if r.needs_review or r.error)
    return CSVImportPreview(
        account_id=account_id,
        rows=rows,
        total_rows=total,
        parseable_rows=len(parseable),
        flagged_rows=flagged,
    )


async def commit_import(
    session: AsyncSession,
    user: User,
    *,
    account_id: UUID,
    rows: list[CSVImportRow],
) -> CSVImportResult:
    acc = (
        await session.exec(
            select(Account).where(Account.user_id == user.id, Account.id == account_id)
        )
    ).first()
    if not acc:
        raise ValueError("Account not found or not owned by user")

    created = 0
    skipped = 0
    for r in rows:
        if r.error:
            skipped += 1
            continue
        txn = Transaction(
            user_id=user.id,
            account_id=account_id,
            category_id=r.category_id,
            amount=r.amount,
            type=r.type,
            description=r.description,
            merchant=r.merchant,
            occurred_at=r.occurred_at,
            source="csv_import",
            ai_confidence=r.ai_confidence,
        )
        session.add(txn)
        created += 1
    await session.commit()
    return CSVImportResult(created=created, skipped=skipped)
