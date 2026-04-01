"""OAuth callback routes for Google and O365 calendar integration."""

from __future__ import annotations

import logging
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from underway.auth.dependencies import get_current_user_from_request, get_db_session
from underway.config import Settings, get_settings
from underway.providers.calendar.google import build_google_oauth_url, handle_google_oauth_callback
from underway.providers.calendar.o365 import build_o365_oauth_url, handle_o365_oauth_callback

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/oauth", tags=["oauth"])

AppSettings = Annotated[Settings, Depends(get_settings)]

# In-memory state store for OAuth flows.
# Maps state -> {'user_id': str, 'flow': Flow | None}
# The flow object is retained to preserve the PKCE code_verifier.
# In production, use Redis or DB-backed store.
_oauth_states: dict[str, dict[str, Any]] = {}


@router.post("/google/initiate")
async def initiate_google_oauth(request: Request, settings: AppSettings) -> dict[str, str]:
    """Return the Google OAuth URL for the frontend to redirect to."""
    user = await get_current_user_from_request(request)

    url, state, flow = build_google_oauth_url(settings)
    _oauth_states[state] = {"user_id": str(user.id), "flow": flow}

    return {"authorization_url": url, "state": state}


@router.get("/google/callback")
async def google_oauth_callback(request: Request, settings: AppSettings) -> RedirectResponse:
    """Handle the Google OAuth callback redirect."""
    code = request.query_params.get("code")
    state = request.query_params.get("state")

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state parameter.")

    stored = _oauth_states.pop(state, None)
    if not stored:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state.")

    session = get_db_session(request)

    try:
        email = await handle_google_oauth_callback(
            flow=stored["flow"],
            code=code,
            session=session,
            user_id=uuid.UUID(stored["user_id"]),
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

    url, state = build_o365_oauth_url(settings)
    _oauth_states[state] = str(user.id)

    return {"authorization_url": url, "state": state}


@router.get("/o365/callback")
async def o365_oauth_callback(request: Request, settings: AppSettings) -> RedirectResponse:
    """Handle the O365 OAuth callback redirect."""
    code = request.query_params.get("code")
    state = request.query_params.get("state")

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state parameter.")

    user_id_str = _oauth_states.pop(state, None)
    if not user_id_str:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state.")

    session = get_db_session(request)

    try:
        email = await handle_o365_oauth_callback(
            code=code,
            state=state,
            settings=settings,
            session=session,
            user_id=uuid.UUID(user_id_str),
        )
        logger.info("O365 OAuth completed for %s", email)
    except Exception:
        logger.exception("O365 OAuth callback failed")
        return RedirectResponse(url="/settings?oauth=error")

    return RedirectResponse(url="/settings?oauth=success&provider=o365")
