"""Tests for JWT token creation and verification."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import jwt
import pytest

from aligned.auth.jwt import (
    TOKEN_EXPIRY_HOURS,
    JWTUser,
    create_access_token,
    create_token_auth,
    verify_access_token,
)

SECRET = "test-secret-key-at-least-32-chars!"
USER_ID = uuid.uuid4()
EMAIL = "test@example.com"


class TestCreateAccessToken:
    def test_creates_valid_token(self) -> None:
        token = create_access_token(USER_ID, EMAIL, SECRET)
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        assert payload["sub"] == str(USER_ID)
        assert payload["email"] == EMAIL

    def test_token_has_expiry(self) -> None:
        token = create_access_token(USER_ID, EMAIL, SECRET)
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        exp = datetime.fromtimestamp(payload["exp"], tz=UTC)
        now = datetime.now(UTC)
        assert exp > now
        assert exp < now + timedelta(hours=TOKEN_EXPIRY_HOURS + 1)

    def test_token_has_issued_at(self) -> None:
        token = create_access_token(USER_ID, EMAIL, SECRET)
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        assert "iat" in payload


class TestVerifyAccessToken:
    def test_round_trip(self) -> None:
        token = create_access_token(USER_ID, EMAIL, SECRET)
        payload = verify_access_token(token, SECRET)
        assert payload["sub"] == str(USER_ID)
        assert payload["email"] == EMAIL

    def test_wrong_secret_raises(self) -> None:
        token = create_access_token(USER_ID, EMAIL, SECRET)
        with pytest.raises(jwt.InvalidSignatureError):
            verify_access_token(token, "wrong-secret")

    def test_expired_token_raises(self) -> None:
        with patch("aligned.auth.jwt.datetime") as mock_dt:
            mock_dt.now.return_value = datetime.now(UTC) - timedelta(hours=48)
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            token = create_access_token(USER_ID, EMAIL, SECRET)
        with pytest.raises(jwt.ExpiredSignatureError):
            verify_access_token(token, SECRET)

    def test_malformed_token_raises(self) -> None:
        with pytest.raises(jwt.DecodeError):
            verify_access_token("not.a.token", SECRET)


class TestCreateTokenAuth:
    def test_valid_token_returns_jwt_user(self) -> None:
        auth = create_token_auth(SECRET)
        token = create_access_token(USER_ID, EMAIL, SECRET)
        user = auth.get_user_by_token(token)
        assert isinstance(user, JWTUser)
        assert user.id == USER_ID
        assert user.email == EMAIL

    def test_invalid_token_returns_none(self) -> None:
        auth = create_token_auth(SECRET)
        user = auth.get_user_by_token("invalid-token")
        assert user is None

    def test_token_with_wrong_secret_returns_none(self) -> None:
        auth = create_token_auth(SECRET)
        token = create_access_token(USER_ID, EMAIL, "different-secret")
        user = auth.get_user_by_token(token)
        assert user is None
