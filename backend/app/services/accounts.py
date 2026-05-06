from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from app.models.account import Account
from app.schemas.accounts import AccountCreate, AccountUpdate


async def list_accounts(session: AsyncSession, user_id: UUID) -> list[Account]:
    result = await session.exec(
        select(Account).where(Account.user_id == user_id).order_by(Account.created_at)
    )
    return list(result.all())


async def get_account(session: AsyncSession, user_id: UUID, account_id: UUID) -> Account | None:
    result = await session.exec(
        select(Account).where(Account.user_id == user_id, Account.id == account_id)
    )
    return result.first()


async def create_account(
    session: AsyncSession, user_id: UUID, payload: AccountCreate
) -> Account:
    acc = Account(user_id=user_id, **payload.model_dump())
    session.add(acc)
    await session.commit()
    await session.refresh(acc)
    return acc


async def update_account(
    session: AsyncSession, user_id: UUID, account_id: UUID, payload: AccountUpdate
) -> Account | None:
    acc = await get_account(session, user_id, account_id)
    if not acc:
        return None
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(acc, field, value)
    session.add(acc)
    await session.commit()
    await session.refresh(acc)
    return acc


async def delete_account(session: AsyncSession, user_id: UUID, account_id: UUID) -> bool:
    acc = await get_account(session, user_id, account_id)
    if not acc:
        return False
    await session.delete(acc)
    await session.commit()
    return True
