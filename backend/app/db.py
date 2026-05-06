from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.config import get_settings


def _async_url(raw: str) -> str:
    """Normalize a DATABASE_URL to an async driver.

    Supports:
      - sqlite+aiosqlite://...     (already async, pass through)
      - sqlite:///path             (local — pin to aiosqlite)
      - postgresql+asyncpg://...   (already async, pass through)
      - postgresql://... or postgres://...  (managed-host format — pin to asyncpg)
    """
    if raw.startswith("sqlite+aiosqlite://"):
        return raw
    if raw.startswith("sqlite://") or raw.startswith("sqlite:///"):
        return raw.replace("sqlite://", "sqlite+aiosqlite://", 1).replace(
            "sqlite+aiosqlite:///", "sqlite+aiosqlite:///"
        )
    if raw.startswith("postgresql+asyncpg://"):
        return raw
    if raw.startswith("postgresql://"):
        return raw.replace("postgresql://", "postgresql+asyncpg://", 1)
    if raw.startswith("postgres://"):
        return raw.replace("postgres://", "postgresql+asyncpg://", 1)
    return raw


_settings = get_settings()
_url = _async_url(_settings.database_url)

# Postgres (asyncpg) doesn't accept the `sslmode` query param Neon adds — convert to ssl=true.
# asyncpg reads connect-time params via connect_args, not the URL.
_connect_args: dict[str, object] = {}
if _url.startswith("postgresql+asyncpg://") and "sslmode=require" in _url:
    _url = _url.replace("?sslmode=require", "").replace("&sslmode=require", "")
    _connect_args["ssl"] = True

engine = create_async_engine(
    _url,
    echo=False,
    future=True,
    connect_args=_connect_args,
    pool_pre_ping=True,  # silently reconnect after idle drops (managed Postgres often kills idle conns)
)

async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session_maker() as session:
        yield session
