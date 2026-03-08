"""FastAPI dependencies for authentication."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from aligned.auth.jwt import JWTUser, verify_access_token
from aligned.config import Settings, get_settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

_bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> JWTUser:
    """Decode JWT from Authorization header and return a JWTUser."""
    import uuid

    import jwt

    try:
        payload = verify_access_token(credentials.credentials, settings.jwt_secret_key)
        return JWTUser(id=uuid.UUID(payload["sub"]), email=payload["email"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc


async def get_db_session(request: Request) -> AsyncSession:
    """Get the DB session injected by middleware."""

    session: AsyncSession = request.state.db_session
    return session
