"""OCR service test — vision provider mocked, image saved to a tmp dir."""

from pathlib import Path

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from app.config import get_settings
from app.llm.base import CompletionResult
from app.models.account import Account
from app.models.receipt import Receipt
from app.models.user import User
from app.services import ocr as ocr_svc
from app.services.ocr import extract_receipt
from app.services.seed import seed_default_categories


GEMINI_VISION_RESPONSE = """```json
{
  "merchant": "Jollibee",
  "line_items": [
    {"name": "Chickenjoy 1pc", "quantity": 1, "amount": 99},
    {"name": "Coke Float", "quantity": 1, "amount": 65}
  ],
  "subtotal": 164,
  "tax": 16,
  "total": 180,
  "occurred_at": "2026-04-15T12:30:00+08:00",
  "payment_method": "gcash",
  "category_guess": "Food & Dining"
}
```"""


@pytest.fixture
def isolated_storage(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point the storage dir at a tmp path so tests don't pollute the repo."""
    settings = get_settings()
    monkeypatch.setattr(settings, "receipt_storage_dir", str(tmp_path))
    return tmp_path


@pytest.fixture
def fake_vision(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeProvider:
        name = "fake"
        default_model = "fake-model"

        async def complete_with_vision(self, messages, image_bytes, mime_type="image/jpeg", **kw):  # type: ignore[no-untyped-def]
            return CompletionResult(text=GEMINI_VISION_RESPONSE)

        async def complete(self, *a, **kw):  # pragma: no cover
            raise NotImplementedError

        async def complete_structured(self, *a, **kw):  # pragma: no cover
            raise NotImplementedError

    monkeypatch.setattr(ocr_svc, "get_provider_for_purpose", lambda _p: FakeProvider())


async def _setup(session: AsyncSession) -> User:
    user = User(email="ocr@k.dev", hashed_password="x", display_name="OCR")
    session.add(user)
    await session.flush()
    await seed_default_categories(session, user.id)
    # User has GCash account → payment_method "gcash" should resolve to it
    session.add(Account(user_id=user.id, name="GCash Wallet", type="ewallet", institution="GCash"))
    await session.commit()
    return user


async def test_extract_receipt_parses_extraction_and_resolves_hints(
    session: AsyncSession, fake_vision: None, isolated_storage: Path
) -> None:
    user = await _setup(session)
    image_bytes = b"\x89PNG\r\n\x1a\nfake-image-bytes"

    result = await extract_receipt(session, user, image_bytes, mime_type="image/png")

    assert result.extracted.merchant == "Jollibee"
    assert result.extracted.total == 180
    assert result.extracted.payment_method == "gcash"
    assert result.extracted.category_guess == "Food & Dining"

    # Suggested category resolved to a real id
    assert result.suggested_category_id is not None
    # Suggested account resolved to GCash by institution match
    assert result.suggested_account_id is not None

    # Image was saved to disk
    assert Path(result.image_path).exists()
    assert Path(result.image_path).read_bytes() == image_bytes

    # Receipt row persisted
    rows = (await session.exec(select(Receipt).where(Receipt.user_id == user.id))).all()
    assert len(rows) == 1
    assert rows[0].extracted_data["merchant"] == "Jollibee"


async def test_extract_receipt_handles_plain_json_no_fence(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch, isolated_storage: Path
) -> None:
    """If the model returns bare JSON without ```json fences, parsing still works."""

    class FakeProvider:
        name = "fake"
        default_model = "fake-model"

        async def complete_with_vision(self, *a, **kw):  # type: ignore[no-untyped-def]
            return CompletionResult(text='{"merchant": "Mercury Drug", "total": 350}')

        async def complete(self, *a, **kw):  # pragma: no cover
            raise NotImplementedError

        async def complete_structured(self, *a, **kw):  # pragma: no cover
            raise NotImplementedError

    monkeypatch.setattr(ocr_svc, "get_provider_for_purpose", lambda _p: FakeProvider())

    user = await _setup(session)
    result = await extract_receipt(session, user, b"x" * 10, mime_type="image/jpeg")
    assert result.extracted.merchant == "Mercury Drug"
    assert result.extracted.total == 350
