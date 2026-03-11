"""FastAPI dependencies for authentication."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from aligned.auth.jwt import JWTUser, verify_access_token
from aligned.config import Settings, get_settings

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer()

BearerCredentials = Annotated[HTTPAuthorizationCredentials, Depends(_bearer_scheme)]
CurrentSettings = Annotated[Settings, Depends(get_settings)]


async def get_current_user(
    credentials: BearerCredentials,
    settings: CurrentSettings,
) -> JWTUser:
    """Decode JWT from Authorization header and return a JWTUser.

    Use as a FastAPI dependency: ``Depends(get_current_user)``.
    For manual use inside a route, call ``get_current_user_from_request(request)`` instead.
    """
    import uuid

    import jwt

    try:
        payload = verify_access_token(credentials.credentials, settings.jwt_secret_key)
        return JWTUser(id=uuid.UUID(payload["sub"]), email=payload["email"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        logger.exception("JWT verification failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc


async def get_current_user_from_request(request: Request) -> JWTUser:
    """Extract and verify JWT from a Request object (non-DI usage)."""
    import uuid

    import jwt

    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = auth[7:]
    settings = getattr(request.app.state, "settings", None) or get_settings()
    try:
        payload = verify_access_token(token, settings.jwt_secret_key)
        return JWTUser(id=uuid.UUID(payload["sub"]), email=payload["email"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        logger.exception("JWT verification failed for request")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc


def get_db_session(request: Request) -> AsyncSession:
    """Get the DB session injected by middleware."""
    session: AsyncSession = request.state.db_session
    return session
