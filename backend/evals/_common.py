"""Eval suite shared utilities — fixture builders, judge helpers, report writers."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app import models  # noqa: F401  - populate metadata
from app.models.account import Account
from app.models.user import User
from app.services.seed import seed_default_categories

EVAL_DATASETS = Path(__file__).parent / "datasets"
EVAL_RESULTS = Path(__file__).parent / "results"
EVAL_RESULTS.mkdir(parents=True, exist_ok=True)


async def make_eval_db() -> async_sessionmaker[AsyncSession]:
    """Create an in-memory SQLite DB pre-populated with one user + default categories.

    Returns the session factory; tests/evals open sessions from it.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def make_eval_user(
    factory: async_sessionmaker[AsyncSession],
) -> tuple[User, Account, dict]:
    """Returns (user, default_account, {category_name: Category})."""
    async with factory() as s:
        user = User(email="eval@kuwenta.dev", hashed_password="x", display_name="Eval")
        s.add(user)
        await s.flush()
        cats = await seed_default_categories(s, user.id)
        acc = Account(user_id=user.id, name="GCash", type="ewallet", institution="GCash")
        s.add(acc)
        await s.commit()
        await s.refresh(user)
        await s.refresh(acc)
        return user, acc, {c.name: c for c in cats}


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_report(name: str, content: str) -> Path:
    """Write a markdown report to evals/results/<name>_<ts>.md and return the path."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = EVAL_RESULTS / f"{name}_{ts}.md"
    path.write_text(content, encoding="utf-8")
    # Also write/update a "latest" symlink-ish file for the README to reference
    latest = EVAL_RESULTS / f"{name}_latest.md"
    latest.write_text(content, encoding="utf-8")
    return path
