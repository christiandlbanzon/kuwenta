from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.core.deps import CurrentUser, SessionDep
from app.schemas.accounts import AccountCreate, AccountPublic, AccountUpdate
from app.services import accounts as svc

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountPublic])
async def list_accounts(user: CurrentUser, session: SessionDep) -> list[AccountPublic]:
    accs = await svc.list_accounts(session, user.id)
    return [AccountPublic.model_validate(a, from_attributes=True) for a in accs]


@router.post("", response_model=AccountPublic, status_code=status.HTTP_201_CREATED)
async def create_account(
    payload: AccountCreate, user: CurrentUser, session: SessionDep
) -> AccountPublic:
    acc = await svc.create_account(session, user.id, payload)
    return AccountPublic.model_validate(acc, from_attributes=True)


@router.get("/{account_id}", response_model=AccountPublic)
async def get_account(
    account_id: UUID, user: CurrentUser, session: SessionDep
) -> AccountPublic:
    acc = await svc.get_account(session, user.id, account_id)
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    return AccountPublic.model_validate(acc, from_attributes=True)


@router.patch("/{account_id}", response_model=AccountPublic)
async def update_account(
    account_id: UUID, payload: AccountUpdate, user: CurrentUser, session: SessionDep
) -> AccountPublic:
    acc = await svc.update_account(session, user.id, account_id, payload)
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    return AccountPublic.model_validate(acc, from_attributes=True)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    account_id: UUID, user: CurrentUser, session: SessionDep
) -> None:
    ok = await svc.delete_account(session, user.id, account_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Account not found")
