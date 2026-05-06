from httpx import AsyncClient


async def test_signup_creates_user_and_seeds_categories(client: AsyncClient) -> None:
    resp = await client.post(
        "/auth/signup",
        json={
            "email": "alice@kuwenta.dev",
            "password": "password-12345",
            "display_name": "Alice",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["email"] == "alice@kuwenta.dev"
    assert body["currency"] == "PHP"
    assert body["timezone"] == "Asia/Manila"


async def test_signup_rejects_duplicate_email(client: AsyncClient) -> None:
    payload = {
        "email": "dup@kuwenta.dev",
        "password": "password-12345",
        "display_name": "Dup",
    }
    first = await client.post("/auth/signup", json=payload)
    assert first.status_code == 201
    second = await client.post("/auth/signup", json=payload)
    assert second.status_code == 409


async def test_login_returns_token_and_me_works(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    me = await client.get("/auth/me", headers=auth_headers)
    assert me.status_code == 200
    assert me.json()["email"] == "test@kuwenta.dev"


async def test_login_rejects_bad_password(client: AsyncClient) -> None:
    await client.post(
        "/auth/signup",
        json={
            "email": "bob@kuwenta.dev",
            "password": "correct-password-1",
            "display_name": "Bob",
        },
    )
    resp = await client.post(
        "/auth/login",
        json={"email": "bob@kuwenta.dev", "password": "wrong-password-1"},
    )
    assert resp.status_code == 401


async def test_me_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


async def test_healthz(client: AsyncClient) -> None:
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
