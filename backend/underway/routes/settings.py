"""Settings routes: GET/PUT for current user's settings."""

from __future__ import annotations

from typing import Annotated, Any

import litellm
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from underway.auth.dependencies import get_current_user, get_db_session
from underway.auth.jwt import JWTUser
from underway.models.user import User

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])

VALID_SLOT_DURATIONS = {30, 60, 120}

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
CurrentUser = Annotated[JWTUser, Depends(get_current_user)]


class SettingsResponse(BaseModel):
    ai_api_key: str | None
    ai_api_base: str | None
    ai_instructions: str | None
    llm_model: str | None
    schedule_slot_duration: int | None


class SettingsUpdate(BaseModel):
    ai_api_key: str | None = None
    ai_api_base: str | None = None
    ai_instructions: str | None = None
    llm_model: str | None = None
    schedule_slot_duration: int | None = None


@router.get("", response_model=SettingsResponse)
async def get_settings(
    current_user: CurrentUser,
    session: DbSession,
) -> dict[str, str | int | None]:
    """Get the current user's settings."""
    result = await session.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return {
        "ai_api_key": user.ai_api_key,
        "ai_api_base": user.ai_api_base,
        "ai_instructions": user.ai_instructions,
        "llm_model": user.llm_model,
        "schedule_slot_duration": user.schedule_slot_duration,
    }


class ModelTestResult(BaseModel):
    model: str
    api_base: str | None
    api_key_hint: str  # first 8 + last 4 chars so user can verify correct key is stored
    completion: bool
    completion_error: str | None
    streaming: bool
    streaming_error: str | None
    tool_calling: bool
    tool_calling_error: str | None


@router.post("/test-model", response_model=ModelTestResult)
async def test_model(
    current_user: CurrentUser,
    session: DbSession,
) -> dict[str, Any]:
    """Test the current user's configured AI model for completion, streaming, and tool calling."""
    result = await session.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not user.ai_api_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No API key configured")
    if not user.llm_model:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No model configured")

    model = user.llm_model
    api_key = user.ai_api_key
    api_base = user.ai_api_base or None
    key_hint = f"{api_key[:8]}...{api_key[-4:]}" if api_key and len(api_key) > 12 else "(too short)"

    out: dict[str, Any] = {
        "model": model,
        "api_base": api_base,
        "api_key_hint": key_hint,
        "completion": False,
        "completion_error": None,
        "streaming": False,
        "streaming_error": None,
        "tool_calling": False,
        "tool_calling_error": None,
    }

    # 1. Basic completion
    try:
        resp = await litellm.acompletion(
            model=model,
            api_key=api_key,
            base_url=api_base,
            messages=[{"role": "user", "content": "Reply with exactly: OK"}],
        )
        out["completion"] = bool(resp.choices[0].message.content)
    except Exception as exc:
        out["completion_error"] = str(exc)

    # 2. Streaming
    try:
        chunks: list[str] = []
        stream = await litellm.acompletion(
            model=model,
            api_key=api_key,
            base_url=api_base,
            messages=[{"role": "user", "content": "Reply with exactly: OK"}],
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                chunks.append(delta)
        out["streaming"] = len(chunks) > 0
    except Exception as exc:
        out["streaming_error"] = str(exc)

    # 3. Tool calling
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the weather for a city.",
                "parameters": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                    "required": ["city"],
                },
            },
        }
    ]
    try:
        tool_resp = await litellm.acompletion(
            model=model,
            api_key=api_key,
            base_url=api_base,
            messages=[{"role": "user", "content": "What's the weather in Auckland?"}],
            tools=tools,
        )
        out["tool_calling"] = bool(tool_resp.choices[0].message.tool_calls)
    except Exception as exc:
        out["tool_calling_error"] = str(exc)

    return out


@router.put("", response_model=SettingsResponse)
async def update_settings(
    body: SettingsUpdate,
    current_user: CurrentUser,
    session: DbSession,
) -> dict[str, str | int | None]:
    """Update the current user's settings."""
    result = await session.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if body.schedule_slot_duration is not None and body.schedule_slot_duration not in VALID_SLOT_DURATIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"schedule_slot_duration must be one of {sorted(VALID_SLOT_DURATIONS)}",
        )

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    return {
        "ai_api_key": user.ai_api_key,
        "ai_api_base": user.ai_api_base,
        "ai_instructions": user.ai_instructions,
        "llm_model": user.llm_model,
        "schedule_slot_duration": user.schedule_slot_duration,
    }
