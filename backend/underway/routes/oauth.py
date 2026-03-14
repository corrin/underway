"""OAuth callback routes for Google, O365, and Todoist integration."""

from __future__ import annotations

import logging
import uuid
from typing import Annotated
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from underway.auth.dependencies import get_current_user_from_request, get_db_session
from underway.config import Settings, get_settings
from underway.models.external_account import ExternalAccount
from underway.providers.calendar.google import build_google_oauth_url, handle_google_oauth_callback
from underway.providers.calendar.o365 import build_o365_oauth_url, handle_o365_oauth_callback

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/oauth", tags=["oauth"])

AppSettings = Annotated[Settings, Depends(get_settings)]

# In-memory state store for OAuth flows. Maps state -> {user_id, code_verifier?}.
# In production, use Redis or DB-backed store.
_oauth_states: dict[str, dict[str, str]] = {}


@router.post("/google/initiate")
async def initiate_google_oauth(request: Request, settings: AppSettings) -> dict[str, str]:
    """Return the Google OAuth URL for the frontend to redirect to."""
    user = await get_current_user_from_request(request)

    url, state, code_verifier = build_google_oauth_url(settings)
    _oauth_states[state] = {"user_id": str(user.id), "code_verifier": code_verifier}

    return {"authorization_url": url, "state": state}


@router.get("/google/callback")
async def google_oauth_callback(request: Request, settings: AppSettings) -> RedirectResponse:
    """Handle the Google OAuth callback redirect."""
    code = request.query_params.get("code")
    state = request.query_params.get("state")

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state parameter.")

    state_data = _oauth_states.pop(state, None)
    if not state_data:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state.")

    session = get_db_session(request)

    try:
        email = await handle_google_oauth_callback(
            code=code,
            state=state,
            settings=settings,
            session=session,
            user_id=uuid.UUID(state_data["user_id"]),
            code_verifier=state_data.get("code_verifier"),
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
    _oauth_states[state] = {"user_id": str(user.id)}

    return {"authorization_url": url, "state": state}


@router.get("/o365/callback")
async def o365_oauth_callback(request: Request, settings: AppSettings) -> RedirectResponse:
    """Handle the O365 OAuth callback redirect."""
    code = request.query_params.get("code")
    state = request.query_params.get("state")

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state parameter.")

    state_data = _oauth_states.pop(state, None)
    if not state_data:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state.")

    session = get_db_session(request)

    try:
        email = await handle_o365_oauth_callback(
            code=code,
            state=state,
            settings=settings,
            session=session,
            user_id=uuid.UUID(state_data["user_id"]),
        )
        logger.info("O365 OAuth completed for %s", email)
    except Exception:
        logger.exception("O365 OAuth callback failed")
        return RedirectResponse(url="/settings?oauth=error")

    return RedirectResponse(url="/settings?oauth=success&provider=o365")


@router.post("/todoist/initiate")
async def initiate_todoist_oauth(request: Request, settings: AppSettings) -> dict[str, str]:
    """Return the Todoist OAuth URL for the frontend to redirect to."""
    user = await get_current_user_from_request(request)

    state = str(uuid.uuid4())
    _oauth_states[state] = {"user_id": str(user.id)}

    params = urlencode(
        {
            "client_id": settings.todoist_client_id,
            "scope": "data:read_write",
            "state": state,
        }
    )
    url = f"https://todoist.com/oauth/authorize?{params}"

    return {"authorization_url": url, "state": state}


@router.get("/todoist/callback")
async def todoist_oauth_callback(request: Request, settings: AppSettings) -> RedirectResponse:
    """Handle the Todoist OAuth callback redirect."""
    code = request.query_params.get("code")
    state = request.query_params.get("state")

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state parameter.")

    state_data = _oauth_states.pop(state, None)
    if not state_data:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state.")

    session = get_db_session(request)

    try:
        # Exchange code for access token
        async with httpx.AsyncClient() as client:
            token_resp = await client.post(
                "https://todoist.com/oauth/access_token",
                data={
                    "client_id": settings.todoist_client_id,
                    "client_secret": settings.todoist_client_secret,
                    "code": code,
                },
            )
            token_resp.raise_for_status()
            token_data = token_resp.json()
            access_token = token_data["access_token"]

            # Get user email
            user_resp = await client.get(
                "https://api.todoist.com/api/v1/user",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            user_resp.raise_for_status()
            email = user_resp.json()["email"]

        user_id = uuid.UUID(state_data["user_id"])

        # Create or update account
        existing = await ExternalAccount.get_by_email_provider_and_user(
            session,
            external_email=email,
            provider="todoist",
            user_id=user_id,
        )
        if existing:
            existing.token = access_token
            existing.needs_reauth = False
        else:
            writable_tasks = await ExternalAccount.get_writable_account(session, user_id, "tasks")
            account = ExternalAccount(
                user_id=user_id,
                external_email=email,
                provider="todoist",
                token=access_token,
                use_for_tasks=True,
                write_tasks=writable_tasks is None,
            )
            session.add(account)

        logger.info("Todoist OAuth completed for %s", email)
    except Exception:
        logger.exception("Todoist OAuth callback failed")
        return RedirectResponse(url="/settings?oauth=error")

    return RedirectResponse(url="/settings?oauth=success&provider=todoist")
