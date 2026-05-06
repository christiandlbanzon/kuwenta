"""Pytest fixtures.

Each test gets a fresh in-memory SQLite DB (no persistence between tests, no Alembic
required for unit tests). Auth-protected endpoints are tested via real signup → token
→ Authorization header flow, not by mocking get_current_user — keeps the test surface
honest about what FastAPI actually sees.
"""

import os
from collections.abc import AsyncIterator
from typing import Any

# Disable APScheduler in tests — these need to be set BEFORE app.main is imported.
os.environ.setdefault("KUWENTA_DISABLE_SCHEDULER", "1")

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import SQLModel

# Import all models so SQLModel.metadata is fully populated before create_all.
from app import models  # noqa: F401
from app.core import deps as deps_module
from app.main import create_app


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[Any]:
    # StaticPool + check_same_thread=False so all sessions share one connection —
    # required for :memory: SQLite where each connection has its own database.
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine: Any) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def session(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    async with session_factory() as s:
        yield s


@pytest_asyncio.fixture
async def client(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncClient]:
    """HTTP client with the app's get_session dependency overridden to use the test DB."""

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as s:
            yield s

    app = create_app()
    app.dependency_overrides[deps_module.get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient) -> dict[str, str]:
    """Sign up a default user and return Authorization headers."""
    resp = await client.post(
        "/auth/signup",
        json={
            "email": "test@kuwenta.dev",
            "password": "test-password-123",
            "display_name": "Test User",
        },
    )
    assert resp.status_code == 201, resp.text
    login = await client.post(
        "/auth/login",
        json={"email": "test@kuwenta.dev", "password": "test-password-123"},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
