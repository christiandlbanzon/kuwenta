from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from app.models.category import Category
from app.schemas.categories import CategoryCreate, CategoryUpdate


async def list_categories(session: AsyncSession, user_id: UUID) -> list[Category]:
    result = await session.exec(
        select(Category).where(Category.user_id == user_id).order_by(Category.type, Category.name)
    )
    return list(result.all())


async def get_category(
    session: AsyncSession, user_id: UUID, category_id: UUID
) -> Category | None:
    result = await session.exec(
        select(Category).where(Category.user_id == user_id, Category.id == category_id)
    )
    return result.first()


async def create_category(
    session: AsyncSession, user_id: UUID, payload: CategoryCreate
) -> Category:
    cat = Category(user_id=user_id, is_default=False, **payload.model_dump())
    session.add(cat)
    await session.commit()
    await session.refresh(cat)
    return cat


async def update_category(
    session: AsyncSession, user_id: UUID, category_id: UUID, payload: CategoryUpdate
) -> Category | None:
    cat = await get_category(session, user_id, category_id)
    if not cat:
        return None
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(cat, field, value)
    session.add(cat)
    await session.commit()
    await session.refresh(cat)
    return cat


async def delete_category(
    session: AsyncSession, user_id: UUID, category_id: UUID
) -> bool:
    cat = await get_category(session, user_id, category_id)
    if not cat:
        return False
    await session.delete(cat)
    await session.commit()
    return True
