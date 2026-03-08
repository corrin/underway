"""Settings routes: GET/PUT for current user's settings."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from aligned.auth.dependencies import get_current_user, get_db_session
from aligned.models.user import User

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from aligned.auth.jwt import JWTUser

router = APIRouter(prefix="/api/settings", tags=["settings"])

VALID_SLOT_DURATIONS = {30, 60, 120}


class SettingsResponse(BaseModel):
    ai_api_key: str | None
    ai_instructions: str | None
    llm_model: str | None
    schedule_slot_duration: int | None


class SettingsUpdate(BaseModel):
    ai_api_key: str | None = None
    ai_instructions: str | None = None
    llm_model: str | None = None
    schedule_slot_duration: int | None = None


@router.get("", response_model=SettingsResponse)
async def get_settings(
    current_user: JWTUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Get the current user's settings."""
    result = await session.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return {
        "ai_api_key": user.ai_api_key,
        "ai_instructions": user.ai_instructions,
        "llm_model": user.llm_model,
        "schedule_slot_duration": user.schedule_slot_duration,
    }


@router.put("", response_model=SettingsResponse)
async def update_settings(
    body: SettingsUpdate,
    current_user: JWTUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Update the current user's settings."""
    result = await session.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if body.schedule_slot_duration is not None and body.schedule_slot_duration not in VALID_SLOT_DURATIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"schedule_slot_duration must be one of {sorted(VALID_SLOT_DURATIONS)}",
        )

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    return {
        "ai_api_key": user.ai_api_key,
        "ai_instructions": user.ai_instructions,
        "llm_model": user.llm_model,
        "schedule_slot_duration": user.schedule_slot_duration,
    }
