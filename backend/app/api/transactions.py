from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.core.deps import CurrentUser, SessionDep
from app.schemas.transactions import (
    QuickAddDraft,
    QuickAddRequest,
    TransactionCreate,
    TransactionPublic,
    TransactionUpdate,
)
from app.services import transactions as svc
from app.services.categorization import categorize
from app.services.parse_quickadd import parse_quick_add

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("", response_model=list[TransactionPublic])
async def list_transactions(
    user: CurrentUser,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    since: datetime | None = None,
    until: datetime | None = None,
    category_id: UUID | None = None,
) -> list[TransactionPublic]:
    txns = await svc.list_transactions(
        session, user.id, limit=limit, offset=offset, since=since, until=until, category_id=category_id
    )
    return [TransactionPublic.model_validate(t, from_attributes=True) for t in txns]


@router.post("", response_model=TransactionPublic, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    payload: TransactionCreate, user: CurrentUser, session: SessionDep
) -> TransactionPublic:
    try:
        txn = await svc.create_transaction(session, user.id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return TransactionPublic.model_validate(txn, from_attributes=True)


@router.post("/quick-add/parse", response_model=QuickAddDraft)
async def quick_add_parse(
    payload: QuickAddRequest, user: CurrentUser, session: SessionDep
) -> QuickAddDraft:
    """Parse free text into a draft + auto-categorize. The draft is returned for the
    user to confirm; nothing is persisted until they POST /transactions."""
    try:
        draft = await parse_quick_add(
            session, user, payload.text, default_account_id=payload.default_account_id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    cat = await categorize(
        session,
        user,
        description=draft.description,
        merchant=draft.merchant,
        amount=draft.amount,
        txn_type=draft.type,
    )
    draft.category_id = cat.category_id
    draft.ai_confidence = cat.confidence
    if cat.merchant and not draft.merchant:
        draft.merchant = cat.merchant
    return draft


@router.patch("/{txn_id}", response_model=TransactionPublic)
async def update_transaction(
    txn_id: UUID,
    payload: TransactionUpdate,
    user: CurrentUser,
    session: SessionDep,
) -> TransactionPublic:
    try:
        txn = await svc.update_transaction(session, user.id, txn_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return TransactionPublic.model_validate(txn, from_attributes=True)


@router.delete("/{txn_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(
    txn_id: UUID, user: CurrentUser, session: SessionDep
) -> None:
    ok = await svc.delete_transaction(session, user.id, txn_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Transaction not found")
