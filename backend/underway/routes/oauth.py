"""OAuth callback routes for Google and O365 calendar integration."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from underway.auth.dependencies import get_current_user_from_request, get_db_session
from underway.config import get_settings
from underway.providers.calendar.google import build_google_oauth_url, handle_google_oauth_callback
from underway.providers.calendar.o365 import build_o365_oauth_url, handle_o365_oauth_callback

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/oauth", tags=["oauth"])

# In-memory state store for OAuth flows. Maps state -> user_id.
# In production, use Redis or DB-backed store.
_oauth_states: dict[str, str] = {}


@router.post("/google/initiate")
async def initiate_google_oauth(request: Request) -> dict[str, str]:
    """Return the Google OAuth URL for the frontend to redirect to."""
    user = await get_current_user_from_request(request)
    settings = get_settings()

    if not settings.google_client_id:
        raise HTTPException(status_code=400, detail="Google OAuth is not configured.")

    url, state = build_google_oauth_url(settings)
    _oauth_states[state] = str(user.id)

    return {"authorization_url": url, "state": state}


@router.get("/google/callback")
async def google_oauth_callback(request: Request) -> RedirectResponse:
    """Handle the Google OAuth callback redirect."""
    code = request.query_params.get("code")
    state = request.query_params.get("state")

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state parameter.")

    user_id_str = _oauth_states.pop(state, None)
    if not user_id_str:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state.")

    import uuid

    settings = get_settings()
    session = get_db_session(request)

    try:
        email = await handle_google_oauth_callback(
            code=code,
            state=state,
            settings=settings,
            session=session,
            user_id=uuid.UUID(user_id_str),
        )
        logger.info("Google OAuth completed for %s", email)
    except Exception:
        logger.exception("Google OAuth callback failed")
        return RedirectResponse(url="/settings?oauth=error")

    return RedirectResponse(url="/settings?oauth=success&provider=google")


@router.post("/o365/initiate")
async def initiate_o365_oauth(request: Request) -> dict[str, str]:
    """Return the O365 OAuth URL for the frontend to redirect to."""
    user = await get_current_user_from_request(request)
    settings = get_settings()

    if not settings.o365_client_id:
        raise HTTPException(status_code=400, detail="O365 OAuth is not configured.")

    url, state = build_o365_oauth_url(settings)
    _oauth_states[state] = str(user.id)

    return {"authorization_url": url, "state": state}


@router.get("/o365/callback")
async def o365_oauth_callback(request: Request) -> RedirectResponse:
    """Handle the O365 OAuth callback redirect."""
    code = request.query_params.get("code")
    state = request.query_params.get("state")

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state parameter.")

    user_id_str = _oauth_states.pop(state, None)
    if not user_id_str:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state.")

    import uuid

    settings = get_settings()
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
