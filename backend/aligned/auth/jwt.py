"""JWT token creation, verification, and FastREST TokenAuthentication factory."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from fastrest.authentication import TokenAuthentication

TOKEN_EXPIRY_HOURS = 24


@dataclass
class JWTUser:
    """Lightweight user identity decoded from a JWT — no DB hit required."""

    id: uuid.UUID
    email: str


def create_access_token(user_id: uuid.UUID, email: str, secret_key: str) -> str:
    """Create a signed JWT containing user id and email."""
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "exp": datetime.now(UTC) + timedelta(hours=TOKEN_EXPIRY_HOURS),
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, secret_key, algorithm="HS256")


def verify_access_token(token: str, secret_key: str) -> dict[str, Any]:
    """Decode and verify a JWT. Raises jwt.PyJWTError on failure."""
    payload: dict[str, Any] = jwt.decode(token, secret_key, algorithms=["HS256"])
    return payload


def create_token_auth(secret_key: str) -> TokenAuthentication:
    """Factory that returns a FastREST TokenAuthentication using JWT."""

    def get_user_by_token(token: str) -> JWTUser | None:
        try:
            payload = verify_access_token(token, secret_key)
            return JWTUser(id=uuid.UUID(payload["sub"]), email=payload["email"])
        except jwt.PyJWTError:
            return None

    return TokenAuthentication(get_user_by_token=get_user_by_token, keyword="Bearer")
