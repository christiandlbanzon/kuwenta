"""Cross-user isolation tests.

These guard the multi-user safety net: every list/get must be scoped by user_id.
Two users sign up, each creates an account + transaction, then we verify neither
can read or modify the other's data through the public API.
"""

from decimal import Decimal

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core import deps as deps_module
from app.main import create_app


@pytest_asyncio.fixture
async def two_user_clients(session_factory: async_sessionmaker) -> tuple[AsyncClient, dict, dict]:
    """Returns (client, alice_headers, bob_headers) — both signed up against the same app."""

    async def override_get_session():
        async with session_factory() as s:
            yield s

    app = create_app()
    app.dependency_overrides[deps_module.get_session] = override_get_session
    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://test")

    await client.post(
        "/auth/signup",
        json={"email": "alice@k.dev", "password": "alice-password-1", "display_name": "Alice"},
    )
    await client.post(
        "/auth/signup",
        json={"email": "bob@k.dev", "password": "bob-password-12", "display_name": "Bob"},
    )
    alice_token = (
        await client.post(
            "/auth/login",
            json={"email": "alice@k.dev", "password": "alice-password-1"},
        )
    ).json()["access_token"]
    bob_token = (
        await client.post(
            "/auth/login",
            json={"email": "bob@k.dev", "password": "bob-password-12"},
        )
    ).json()["access_token"]
    yield client, {"Authorization": f"Bearer {alice_token}"}, {"Authorization": f"Bearer {bob_token}"}
    await client.aclose()


async def test_users_see_only_their_own_accounts(
    two_user_clients: tuple[AsyncClient, dict, dict],
) -> None:
    client, alice, bob = two_user_clients
    await client.post(
        "/accounts",
        headers=alice,
        json={"name": "Alice GCash", "type": "ewallet", "institution": "GCash"},
    )
    await client.post(
        "/accounts",
        headers=bob,
        json={"name": "Bob BDO", "type": "bank", "institution": "BDO"},
    )
    a_list = (await client.get("/accounts", headers=alice)).json()
    b_list = (await client.get("/accounts", headers=bob)).json()
    assert {a["name"] for a in a_list} == {"Alice GCash"}
    assert {a["name"] for a in b_list} == {"Bob BDO"}


async def test_user_cannot_read_other_users_account_by_id(
    two_user_clients: tuple[AsyncClient, dict, dict],
) -> None:
    client, alice, bob = two_user_clients
    create_resp = await client.post(
        "/accounts",
        headers=alice,
        json={"name": "Alice GCash", "type": "ewallet"},
    )
    alice_account_id = create_resp.json()["id"]

    # Bob tries to read Alice's account by ID
    resp = await client.get(f"/accounts/{alice_account_id}", headers=bob)
    assert resp.status_code == 404


async def test_user_cannot_create_transaction_against_other_users_account(
    two_user_clients: tuple[AsyncClient, dict, dict],
) -> None:
    client, alice, bob = two_user_clients
    a = (
        await client.post(
            "/accounts",
            headers=alice,
            json={"name": "Alice GCash", "type": "ewallet"},
        )
    ).json()
    resp = await client.post(
        "/transactions",
        headers=bob,
        json={
            "account_id": a["id"],
            "amount": "100",
            "type": "expense",
            "description": "trying to use alice's account",
            "occurred_at": "2026-05-01T12:00:00+08:00",
        },
    )
    assert resp.status_code == 400  # service rejects with "not owned by user"


async def test_users_see_only_their_own_categories(
    two_user_clients: tuple[AsyncClient, dict, dict],
) -> None:
    client, alice, bob = two_user_clients
    a_cats = (await client.get("/categories", headers=alice)).json()
    b_cats = (await client.get("/categories", headers=bob)).json()
    a_ids = {c["id"] for c in a_cats}
    b_ids = {c["id"] for c in b_cats}
    # Both users have default seeded categories — same names, different IDs
    assert a_ids.isdisjoint(b_ids)
    assert {c["name"] for c in a_cats} == {c["name"] for c in b_cats}


async def test_users_see_only_their_own_transactions(
    two_user_clients: tuple[AsyncClient, dict, dict],
) -> None:
    client, alice, bob = two_user_clients
    a_acc = (
        await client.post(
            "/accounts", headers=alice, json={"name": "A", "type": "cash"}
        )
    ).json()
    b_acc = (
        await client.post(
            "/accounts", headers=bob, json={"name": "B", "type": "cash"}
        )
    ).json()
    await client.post(
        "/transactions",
        headers=alice,
        json={
            "account_id": a_acc["id"],
            "amount": "100",
            "type": "expense",
            "description": "alice expense",
            "occurred_at": "2026-05-01T12:00:00+08:00",
        },
    )
    await client.post(
        "/transactions",
        headers=bob,
        json={
            "account_id": b_acc["id"],
            "amount": "200",
            "type": "expense",
            "description": "bob expense",
            "occurred_at": "2026-05-01T12:00:00+08:00",
        },
    )
    a_txns = (await client.get("/transactions", headers=alice)).json()
    b_txns = (await client.get("/transactions", headers=bob)).json()
    assert [t["description"] for t in a_txns] == ["alice expense"]
    assert [t["description"] for t in b_txns] == ["bob expense"]


async def test_unauthenticated_requests_are_rejected(
    two_user_clients: tuple[AsyncClient, dict, dict],
) -> None:
    client, _, _ = two_user_clients
    for path in ["/accounts", "/categories", "/transactions"]:
        resp = await client.get(path)
        assert resp.status_code == 401, path
