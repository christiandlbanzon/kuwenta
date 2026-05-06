from datetime import datetime
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from app.models.account import Account
from app.models.category import Category
from app.models.transaction import Transaction
from app.schemas.transactions import TransactionCreate, TransactionUpdate
from app.services.categorization import record_user_correction


async def list_transactions(
    session: AsyncSession,
    user_id: UUID,
    *,
    limit: int = 50,
    offset: int = 0,
    since: datetime | None = None,
    until: datetime | None = None,
    category_id: UUID | None = None,
) -> list[Transaction]:
    stmt = select(Transaction).where(Transaction.user_id == user_id)
    if since is not None:
        stmt = stmt.where(Transaction.occurred_at >= since)
    if until is not None:
        stmt = stmt.where(Transaction.occurred_at <= until)
    if category_id is not None:
        stmt = stmt.where(Transaction.category_id == category_id)
    stmt = stmt.order_by(Transaction.occurred_at.desc()).limit(limit).offset(offset)  # type: ignore[attr-defined]
    result = await session.exec(stmt)
    return list(result.all())


async def get_transaction(
    session: AsyncSession, user_id: UUID, txn_id: UUID
) -> Transaction | None:
    result = await session.exec(
        select(Transaction).where(Transaction.user_id == user_id, Transaction.id == txn_id)
    )
    return result.first()


async def _validate_account_owned(session: AsyncSession, user_id: UUID, account_id: UUID) -> None:
    res = await session.exec(
        select(Account.id).where(Account.user_id == user_id, Account.id == account_id)
    )
    if res.first() is None:
        raise ValueError("Account not found or not owned by user")


async def _validate_category_owned(
    session: AsyncSession, user_id: UUID, category_id: UUID
) -> None:
    res = await session.exec(
        select(Category.id).where(Category.user_id == user_id, Category.id == category_id)
    )
    if res.first() is None:
        raise ValueError("Category not found or not owned by user")


async def create_transaction(
    session: AsyncSession,
    user_id: UUID,
    payload: TransactionCreate,
    *,
    raw_input: str | None = None,
    ai_confidence: float | None = None,
) -> Transaction:
    await _validate_account_owned(session, user_id, payload.account_id)
    if payload.category_id is not None:
        await _validate_category_owned(session, user_id, payload.category_id)
    txn = Transaction(
        user_id=user_id,
        raw_input=raw_input,
        ai_confidence=ai_confidence,
        **payload.model_dump(),
    )
    session.add(txn)
    await session.commit()
    await session.refresh(txn)
    return txn


async def update_transaction(
    session: AsyncSession,
    user_id: UUID,
    txn_id: UUID,
    payload: TransactionUpdate,
) -> Transaction | None:
    """Updates a transaction and — if the user changed the category — records a few-shot
    example so future categorization for similar text matches the user's preference."""
    txn = await get_transaction(session, user_id, txn_id)
    if not txn:
        return None
    data = payload.model_dump(exclude_unset=True)
    if "account_id" in data:
        await _validate_account_owned(session, user_id, data["account_id"])
    if "category_id" in data and data["category_id"] is not None:
        await _validate_category_owned(session, user_id, data["category_id"])

    category_changed = (
        "category_id" in data and data["category_id"] is not None and data["category_id"] != txn.category_id
    )
    new_category_id = data.get("category_id") if category_changed else None

    for field, value in data.items():
        setattr(txn, field, value)
    session.add(txn)
    await session.commit()
    await session.refresh(txn)

    if category_changed and new_category_id is not None:
        cat_res = await session.exec(select(Category).where(Category.id == new_category_id))
        cat = cat_res.first()
        if cat:
            record_user_correction(
                user_id,
                description=txn.description,
                merchant=txn.merchant,
                amount=txn.amount,
                category_name=cat.name,
            )
    return txn


async def delete_transaction(
    session: AsyncSession, user_id: UUID, txn_id: UUID
) -> bool:
    txn = await get_transaction(session, user_id, txn_id)
    if not txn:
        return False
    await session.delete(txn)
    await session.commit()
    return True
