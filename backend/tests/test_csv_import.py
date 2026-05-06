"""CSV import — parse + categorize (mocked LLM) + commit."""

from datetime import datetime
from decimal import Decimal

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from app.llm.base import StructuredResult
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.imports import CSVImportRow
from app.services import csv_import as cs
from app.services.csv_import import _BatchCategorization, _RowPrediction, parse_csv
from app.services.seed import seed_default_categories


SAMPLE_CSV = b"""occurred_at,amount,description,type,merchant
2026-04-15,180.00,jollibee lunch,expense,Jollibee
2026-04-15,3200.00,meralco bill,expense,Meralco
2026-04-16,250.00,grab to ortigas,expense,Grab
2026-04-16,5000.00,padala mama,expense,
not-a-date,100,broken row,expense,
"""


async def _setup(session: AsyncSession) -> tuple[User, Account, dict]:
    user = User(email="csv@k.dev", hashed_password="x", display_name="CSV")
    session.add(user)
    await session.flush()
    cats = await seed_default_categories(session, user.id)
    by_name = {c.name: c for c in cats}
    acc = Account(user_id=user.id, name="GCash", type="ewallet")
    session.add(acc)
    await session.commit()
    await session.refresh(acc)
    return user, acc, by_name


def test_parse_csv_handles_valid_and_broken_rows() -> None:
    rows, total = parse_csv(SAMPLE_CSV)
    assert total == 5
    parseable = [r for r in rows if r.error is None]
    assert len(parseable) == 4
    assert parseable[0].description == "jollibee lunch"
    assert parseable[0].amount == Decimal("180.00")
    # Last row has parse error
    assert rows[-1].error is not None


def test_parse_csv_handles_amount_with_peso_and_commas() -> None:
    csv = """occurred_at,amount,description,type,merchant
2026-04-15,"1,250.50",grab,expense,Grab
2026-04-15,₱180,jollibee,expense,
""".encode("utf-8")
    rows, _ = parse_csv(csv)
    parseable = [r for r in rows if r.error is None]
    assert parseable[0].amount == Decimal("1250.50")
    assert parseable[1].amount == Decimal("180")


async def test_preview_categorizes_via_mocked_llm(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    user, acc, _cats = await _setup(session)

    class FakeProvider:
        name = "fake"
        default_model = "fake-model"

        async def complete_structured(self, messages, schema, **kwargs):  # type: ignore[no-untyped-def]
            # Return predictions for all 4 parseable rows
            batch = _BatchCategorization(
                predictions=[
                    _RowPrediction(row_number=1, category_name="Food & Dining", confidence=0.95, merchant="Jollibee"),
                    _RowPrediction(row_number=2, category_name="Bills & Utilities", confidence=0.97, merchant="Meralco"),
                    _RowPrediction(row_number=3, category_name="Transportation", confidence=0.90, merchant="Grab"),
                    _RowPrediction(row_number=4, category_name="Family Support", confidence=0.65, merchant=None),
                ]
            )
            return StructuredResult(parsed=batch, input_tokens=200, output_tokens=80)

        async def complete(self, *a, **kw):  # pragma: no cover
            raise NotImplementedError

        async def complete_with_vision(self, *a, **kw):  # pragma: no cover
            raise NotImplementedError

    monkeypatch.setattr(cs, "get_provider_for_purpose", lambda _p: FakeProvider())

    preview = await cs.preview_import(
        session, user, account_id=acc.id, csv_bytes=SAMPLE_CSV
    )
    assert preview.total_rows == 5
    assert preview.parseable_rows == 4
    # row 4 has confidence 0.65 -> needs_review
    flagged_rows = [r for r in preview.rows if r.needs_review or r.error]
    assert len(flagged_rows) >= 2  # the broken row + the low-confidence row

    # Categorization mapped to real category IDs
    food_row = next(r for r in preview.rows if r.row_number == 1)
    assert food_row.category_id is not None
    assert food_row.category_name == "Food & Dining"


async def test_commit_persists_only_non_error_rows(session: AsyncSession) -> None:
    user, acc, cats = await _setup(session)
    food = cats["Food & Dining"]

    rows = [
        CSVImportRow(
            row_number=1,
            occurred_at=datetime.now().astimezone(),
            amount=Decimal("180"),
            type="expense",
            description="jollibee",
            category_id=food.id,
        ),
        CSVImportRow(
            row_number=2,
            occurred_at=datetime.now().astimezone(),
            amount=Decimal("0"),
            type="expense",
            description="(unparseable)",
            error="bad row",
        ),
    ]
    result = await cs.commit_import(session, user, account_id=acc.id, rows=rows)
    assert result.created == 1
    assert result.skipped == 1

    txns = (
        await session.exec(select(Transaction).where(Transaction.user_id == user.id))
    ).all()
    assert len(txns) == 1
    assert txns[0].source == "csv_import"


async def test_commit_rejects_other_users_account(session: AsyncSession) -> None:
    user_a, _, _ = await _setup(session)
    user_b = User(email="b@k.dev", hashed_password="x", display_name="B")
    session.add(user_b)
    await session.flush()
    acc_b = Account(user_id=user_b.id, name="B", type="cash")
    session.add(acc_b)
    await session.commit()
    await session.refresh(acc_b)

    with pytest.raises(ValueError, match="not owned"):
        await cs.commit_import(
            session,
            user_a,
            account_id=acc_b.id,
            rows=[
                CSVImportRow(
                    row_number=1,
                    occurred_at=datetime.now().astimezone(),
                    amount=Decimal("100"),
                    type="expense",
                    description="x",
                )
            ],
        )
