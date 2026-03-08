"""Auth routes: Google login, current user, logout."""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from aligned.auth.dependencies import get_current_user, get_db_session
from aligned.auth.google import verify_google_id_token
from aligned.auth.jwt import JWTUser, create_access_token
from aligned.config import Settings, get_settings
from aligned.models.user import User

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/auth", tags=["auth"])


class GoogleLoginRequest(BaseModel):
    id_token: str


class GoogleLoginResponse(BaseModel):
    token: str
    user: UserResponse


class UserResponse(BaseModel):
    id: str
    email: str
    llm_model: str | None
    ai_instructions: str | None
    schedule_slot_duration: int | None

    model_config = {"from_attributes": True}


# Re-declare after UserResponse is defined
GoogleLoginResponse.model_rebuild()


@router.post("/google", response_model=GoogleLoginResponse)
async def google_login(
    body: GoogleLoginRequest,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Verify Google ID token, find/create user, return JWT."""
    try:
        email = await asyncio.to_thread(verify_google_id_token, body.id_token, settings.google_client_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google ID token",
        ) from exc

    result = await session.execute(select(User).where(User.app_login == email))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(app_login=email)
        user.id = uuid.uuid4()
        session.add(user)
        await session.flush()

    token = create_access_token(user.id, user.app_login, settings.jwt_secret_key)
    return {
        "token": token,
        "user": {
            "id": str(user.id),
            "email": user.app_login,
            "llm_model": user.llm_model,
            "ai_instructions": user.ai_instructions,
            "schedule_slot_duration": user.schedule_slot_duration,
        },
    }


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: JWTUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Return the current user's profile."""
    result = await session.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return {
        "id": str(user.id),
        "email": user.app_login,
        "llm_model": user.llm_model,
        "ai_instructions": user.ai_instructions,
        "schedule_slot_duration": user.schedule_slot_duration,
    }


@router.post("/logout")
async def logout() -> dict[str, str]:
    """Logout is a no-op for stateless JWT — client discards the token."""
    return {"detail": "Logged out"}


class TestLoginRequest(BaseModel):
    email: str


# Separate router — only included in the app when settings.testing is True
test_router = APIRouter(prefix="/api/auth", tags=["auth-test"])


@test_router.post("/test-login", response_model=GoogleLoginResponse)
async def test_login(
    body: TestLoginRequest,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Bypass Google OAuth for E2E tests. This route only exists when TESTING=true."""
    result = await session.execute(select(User).where(User.app_login == body.email))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(app_login=body.email)
        user.id = uuid.uuid4()
        session.add(user)
        await session.flush()

    token = create_access_token(user.id, user.app_login, settings.jwt_secret_key)
    return {
        "token": token,
        "user": {
            "id": str(user.id),
            "email": user.app_login,
            "llm_model": user.llm_model,
            "ai_instructions": user.ai_instructions,
            "schedule_slot_duration": user.schedule_slot_duration,
        },
    }
