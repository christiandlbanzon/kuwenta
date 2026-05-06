"""Tests for parse_quick_add — verifies LLM output is mapped to the user's actual
account and the resolved draft has correct shape. LLM is mocked."""

from datetime import datetime
from decimal import Decimal

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.llm.base import StructuredResult
from app.models.account import Account
from app.models.user import User
from app.services import parse_quickadd as pq
from app.services.parse_quickadd import ParsedQuickAdd, parse_quick_add


class FakePQProvider:
    name = "fake"
    default_model = "fake-model"

    def __init__(self, payload: ParsedQuickAdd) -> None:
        self._payload = payload

    async def complete(self, *a, **kw):  # type: ignore[no-untyped-def]
        raise NotImplementedError

    async def complete_with_vision(self, *a, **kw):  # type: ignore[no-untyped-def]
        raise NotImplementedError

    async def complete_structured(self, messages, schema, **kwargs):  # type: ignore[no-untyped-def]
        return StructuredResult(parsed=self._payload, input_tokens=10, output_tokens=5)


async def _user_with_accounts(session: AsyncSession) -> tuple[User, Account, Account]:
    u = User(email="pq@k.dev", hashed_password="x", display_name="Pq")
    session.add(u)
    await session.flush()
    gcash = Account(user_id=u.id, name="GCash", type="ewallet", institution="GCash")
    bdo = Account(user_id=u.id, name="BDO Checking", type="bank", institution="BDO")
    session.add_all([gcash, bdo])
    await session.commit()
    await session.refresh(gcash)
    await session.refresh(bdo)
    return u, gcash, bdo


async def test_parse_resolves_account_by_exact_match(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    user, gcash, bdo = await _user_with_accounts(session)
    fake = FakePQProvider(
        ParsedQuickAdd(
            amount=Decimal("180"),
            type="expense",
            account_hint="GCash",
            occurred_at=datetime.fromisoformat("2026-04-30T12:00:00+08:00"),
            description="jollibee lunch",
            merchant_guess="Jollibee",
        )
    )
    monkeypatch.setattr(
        "app.services.parse_quickadd.get_provider_for_purpose", lambda _p: fake
    )

    draft = await parse_quick_add(session, user, "180 jollibee lunch yesterday gcash")
    assert draft.account_id == gcash.id
    assert draft.amount == Decimal("180")
    assert draft.type == "expense"
    assert draft.merchant == "Jollibee"
    assert draft.raw_input == "180 jollibee lunch yesterday gcash"


async def test_parse_falls_back_to_first_account_if_hint_unknown(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    user, gcash, _bdo = await _user_with_accounts(session)
    fake = FakePQProvider(
        ParsedQuickAdd(
            amount=Decimal("99"),
            type="expense",
            account_hint="Some Random Bank",
            occurred_at=datetime.fromisoformat("2026-04-30T12:00:00+08:00"),
            description="x",
            merchant_guess=None,
        )
    )
    monkeypatch.setattr(
        "app.services.parse_quickadd.get_provider_for_purpose", lambda _p: fake
    )

    draft = await parse_quick_add(session, user, "99 something")
    # First account is GCash (created first)
    assert draft.account_id == gcash.id


async def test_parse_raises_if_user_has_no_accounts(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = User(email="empty@k.dev", hashed_password="x", display_name="E")
    session.add(user)
    await session.commit()
    with pytest.raises(ValueError, match="at least one account"):
        await parse_quick_add(session, user, "100 test")
