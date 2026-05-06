"""Tests for the categorization service.

The LLM provider is mocked — we verify:
  - The right category is matched when the LLM returns a known name
  - Unknown category names map to category_id=None (we don't fabricate)
  - Few-shot user corrections are persisted and re-loaded
  - LLMCall row is written for every categorization
"""

from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from app.llm import router as llm_router
from app.models.category import Category
from app.models.llm_call import LLMCall
from app.models.user import User
from app.services import categorization as cat_svc
from app.llm.base import StructuredResult
from app.services.categorization import (
    CategorizationResult,
    _user_few_shot_path,
    categorize,
    record_user_correction,
)
from app.services.seed import seed_default_categories


class FakeProvider:
    name = "fake"
    default_model = "fake-model"

    def __init__(self, payload: CategorizationResult) -> None:
        self._payload = payload
        self.calls = 0

    async def complete(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise NotImplementedError

    async def complete_with_vision(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise NotImplementedError

    async def complete_structured(self, messages, schema, **kwargs):  # type: ignore[no-untyped-def]
        self.calls += 1
        return StructuredResult(parsed=self._payload, input_tokens=10, output_tokens=5)


@pytest.fixture
def fake_provider(monkeypatch: pytest.MonkeyPatch) -> FakeProvider:
    fake = FakeProvider(
        CategorizationResult(category_name="Food & Dining", confidence=0.92, merchant="Jollibee")
    )
    monkeypatch.setattr(llm_router, "get_provider_for_purpose", lambda _purpose: fake)
    monkeypatch.setattr(
        "app.services.categorization.get_provider_for_purpose", lambda _purpose: fake
    )
    return fake


@pytest.fixture
def isolated_few_shot_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setattr(cat_svc, "USER_FEW_SHOT_DIR", tmp_path)
    return tmp_path


async def _make_user_with_categories(session: AsyncSession) -> User:
    user = User(email="cat@k.dev", hashed_password="x", display_name="Cat")
    session.add(user)
    await session.flush()
    await seed_default_categories(session, user.id)
    await session.commit()
    return user


async def test_categorize_matches_known_category(
    session: AsyncSession, fake_provider: FakeProvider, isolated_few_shot_dir: Path
) -> None:
    user = await _make_user_with_categories(session)

    result = await categorize(
        session,
        user,
        description="jollibee lunch",
        merchant="Jollibee",
        amount=Decimal("180"),
    )
    assert result.category_name == "Food & Dining"
    assert result.category_id is not None
    assert 0.0 <= result.confidence <= 1.0
    assert fake_provider.calls == 1

    # An LLMCall row was written
    rows = (
        await session.exec(select(LLMCall).where(LLMCall.purpose == "categorization"))
    ).all()
    assert len(rows) == 1


async def test_categorize_unknown_name_returns_none_id(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch, isolated_few_shot_dir: Path
) -> None:
    fake = FakeProvider(
        CategorizationResult(category_name="Made-Up Category", confidence=0.5, merchant=None)
    )
    monkeypatch.setattr(
        "app.services.categorization.get_provider_for_purpose", lambda _purpose: fake
    )

    user = await _make_user_with_categories(session)
    result = await categorize(
        session,
        user,
        description="something weird",
        merchant=None,
        amount=Decimal("100"),
    )
    assert result.category_id is None
    assert result.category_name == "Made-Up Category"


def test_record_user_correction_writes_jsonl(
    isolated_few_shot_dir: Path,
) -> None:
    user_id = UUID("00000000-0000-0000-0000-000000000001")
    record_user_correction(
        user_id,
        description="grab to ortigas",
        merchant="Grab",
        amount=Decimal("250"),
        category_name="Transportation",
    )
    path = _user_few_shot_path(user_id)
    assert path.exists()
    contents = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(contents) == 1
    assert "Transportation" in contents[0]
    assert "grab to ortigas" in contents[0]
