"""OAuth callback routes for Google and O365 calendar integration."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from typing import Annotated

from underway.auth.dependencies import get_current_user_from_request, get_db_session
from underway.config import Settings, get_settings
from underway.models.oauth_state import OAuthState
from underway.providers.calendar.google import build_google_oauth_url, handle_google_oauth_callback
from underway.providers.calendar.o365 import build_o365_oauth_url, handle_o365_oauth_callback

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/oauth", tags=["oauth"])

AppSettings = Annotated[Settings, Depends(get_settings)]


@router.post("/google/initiate")
async def initiate_google_oauth(request: Request, settings: AppSettings) -> dict[str, str]:
    """Return the Google OAuth URL for the frontend to redirect to."""
    user = await get_current_user_from_request(request)
    session = get_db_session(request)

    url, state, code_verifier = build_google_oauth_url(settings)
    await OAuthState.create(
        session,
        state=state,
        user_id=user.id,
        provider="google",
        code_verifier=code_verifier,
    )

    return {"authorization_url": url, "state": state}


@router.get("/google/callback")
async def google_oauth_callback(request: Request, settings: AppSettings) -> RedirectResponse:
    """Handle the Google OAuth callback redirect."""
    code = request.query_params.get("code")
    state = request.query_params.get("state")

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state parameter.")

    session = get_db_session(request)
    stored = await OAuthState.consume(session, state)
    if not stored:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state.")

    try:
        email = await handle_google_oauth_callback(
            code=code,
            session=session,
            user_id=stored.user_id,
            settings=settings,
            code_verifier=stored.code_verifier,
        )
        logger.info("Google OAuth completed for %s", email)
    except Exception:
        logger.exception("Google OAuth callback failed")
        return RedirectResponse(url="/settings?oauth=error")

    return RedirectResponse(url="/settings?oauth=success&provider=google")


@router.post("/o365/initiate")
async def initiate_o365_oauth(request: Request, settings: AppSettings) -> dict[str, str]:
    """Return the O365 OAuth URL for the frontend to redirect to."""
    user = await get_current_user_from_request(request)
    session = get_db_session(request)

    url, state = build_o365_oauth_url(settings)
    await OAuthState.create(
        session,
        state=state,
        user_id=user.id,
        provider="o365",
    )

    return {"authorization_url": url, "state": state}


@router.get("/o365/callback")
async def o365_oauth_callback(request: Request, settings: AppSettings) -> RedirectResponse:
    """Handle the O365 OAuth callback redirect."""
    code = request.query_params.get("code")
    state = request.query_params.get("state")

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state parameter.")

    session = get_db_session(request)
    stored = await OAuthState.consume(session, state)
    if not stored:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state.")

    try:
        email = await handle_o365_oauth_callback(
            code=code,
            state=state,
            settings=settings,
            session=session,
            user_id=stored.user_id,
        )
        logger.info("O365 OAuth completed for %s", email)
    except Exception:
        logger.exception("O365 OAuth callback failed")
        return RedirectResponse(url="/settings?oauth=error")

    return RedirectResponse(url="/settings?oauth=success&provider=o365")
