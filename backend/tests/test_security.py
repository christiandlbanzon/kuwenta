from uuid import uuid4

import pytest

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_and_verify_password() -> None:
    h = hash_password("hunter2")
    assert h != "hunter2"
    assert verify_password("hunter2", h)
    assert not verify_password("wrong", h)


def test_token_roundtrip() -> None:
    user_id = uuid4()
    token = create_access_token(user_id)
    payload = decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert "exp" in payload and "iat" in payload


def test_token_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        decode_access_token("not-a-real-token")
