from uuid import uuid4

from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from app.models.category import Category
from app.models.user import User
from app.services.seed import DEFAULT_CATEGORIES, seed_default_categories


async def test_seed_creates_all_default_categories(session: AsyncSession) -> None:
    user = User(
        email="seed@kuwenta.dev",
        hashed_password="x",
        display_name="Seed",
    )
    session.add(user)
    await session.flush()

    await seed_default_categories(session, user.id)
    await session.commit()

    cats = (await session.exec(select(Category).where(Category.user_id == user.id))).all()
    assert len(cats) == len(DEFAULT_CATEGORIES)
    assert all(c.is_default for c in cats)
    expense = [c for c in cats if c.type == "expense"]
    income = [c for c in cats if c.type == "income"]
    assert len(expense) > 0 and len(income) > 0


async def test_seed_is_user_scoped(session: AsyncSession) -> None:
    u1 = User(email="a@k.dev", hashed_password="x", display_name="A")
    u2 = User(email="b@k.dev", hashed_password="x", display_name="B")
    session.add_all([u1, u2])
    await session.flush()
    await seed_default_categories(session, u1.id)
    await seed_default_categories(session, u2.id)
    await session.commit()

    u1_cats = (await session.exec(select(Category).where(Category.user_id == u1.id))).all()
    u2_cats = (await session.exec(select(Category).where(Category.user_id == u2.id))).all()
    assert len(u1_cats) == len(DEFAULT_CATEGORIES)
    assert len(u2_cats) == len(DEFAULT_CATEGORIES)
    # Ensure category IDs do not overlap (different rows per user)
    assert {c.id for c in u1_cats}.isdisjoint({c.id for c in u2_cats})
