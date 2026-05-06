"""Seed default PH-specific categories on user signup."""

from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.category import Category

# (name, type) — keep this ordered; the order matters for stable category IDs in fixtures
DEFAULT_CATEGORIES: list[tuple[str, str]] = [
    ("Food & Dining", "expense"),
    ("Groceries", "expense"),
    ("Transportation", "expense"),
    ("Bills & Utilities", "expense"),
    ("Shopping", "expense"),
    ("Healthcare", "expense"),
    ("Entertainment", "expense"),
    ("Government Contributions", "expense"),  # SSS, PhilHealth, Pag-IBIG, BIR
    ("Family Support", "expense"),
    ("Tithing & Donations", "expense"),
    ("Savings", "expense"),
    ("Investments", "expense"),
    ("Education", "expense"),
    ("Personal Care", "expense"),
    ("Travel", "expense"),
    ("Others", "expense"),
    ("Salary", "income"),
    ("Freelance", "income"),
    ("Business", "income"),
    ("Refund", "income"),
    ("Gift", "income"),
    ("Other Income", "income"),
]


async def seed_default_categories(session: AsyncSession, user_id: UUID) -> list[Category]:
    """Idempotent: returns categories created on this call only."""
    created: list[Category] = []
    for name, ctype in DEFAULT_CATEGORIES:
        cat = Category(user_id=user_id, name=name, type=ctype, is_default=True)
        session.add(cat)
        created.append(cat)
    await session.flush()
    return created
