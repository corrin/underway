"""Calendar API routes — events, create, delete, account flags."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request

from underway.auth.dependencies import get_current_user_from_request, get_db_session
from underway.models.external_account import ExternalAccount
from underway.providers.calendar.factory import get_calendar_provider
from underway.providers.calendar.models import CalendarEventCreate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.get("/events")
async def list_events(request: Request) -> dict[str, object]:
    """GET /api/calendar/events?start=...&end=... — list events from writable calendar."""
    user = await get_current_user_from_request(request)
    session = get_db_session(request)

    start_str = request.query_params.get("start")
    end_str = request.query_params.get("end")

    now = datetime.now(UTC)
    # fromisoformat handles "Z" suffix natively in Python 3.11+ (we require 3.12)
    start = datetime.fromisoformat(start_str) if start_str else now
    end = datetime.fromisoformat(end_str) if end_str else now + timedelta(days=7)

    account = await ExternalAccount.get_writable_account(session, user.id, "calendar")
    if not account:
        return {"events": [], "message": "No calendar connected."}

    provider = get_calendar_provider(account.provider)
    if not provider:
        return {"events": [], "message": f"Unsupported provider: {account.provider}"}

    events = await provider.get_events(session, user.id, account.external_email, start, end)
    return {"events": [e.model_dump(mode="json") for e in events]}


@router.post("/create-event")
async def create_event(request: Request) -> dict[str, object]:
    """POST /api/calendar/create-event — create a calendar event."""
    user = await get_current_user_from_request(request)
    session = get_db_session(request)
    body = await request.json()

    account = await ExternalAccount.get_writable_account(session, user.id, "calendar")
    if not account:
        raise HTTPException(status_code=400, detail="No calendar connected.")

    provider = get_calendar_provider(account.provider)
    if not provider:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {account.provider}")

    try:
        event_data = CalendarEventCreate(**body)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    event = await provider.create_event(session, user.id, account.external_email, event_data)
    return {"event": event.model_dump(mode="json")}


@router.delete("/delete-event")
async def delete_event(request: Request) -> dict[str, object]:
    """DELETE /api/calendar/delete-event?event_id=... — delete a calendar event."""
    user = await get_current_user_from_request(request)
    session = get_db_session(request)

    event_id = request.query_params.get("event_id")
    if not event_id:
        raise HTTPException(status_code=400, detail="event_id query parameter is required.")

    account = await ExternalAccount.get_writable_account(session, user.id, "calendar")
    if not account:
        raise HTTPException(status_code=400, detail="No calendar connected.")

    provider = get_calendar_provider(account.provider)
    if not provider:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {account.provider}")

    deleted = await provider.delete_event(session, user.id, account.external_email, event_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Event not found or could not be deleted.")

    return {"status": "ok"}


@router.delete("/disconnect-account")
async def disconnect_account(request: Request) -> dict[str, str]:
    """DELETE /api/calendar/disconnect-account?account_id=... — disconnect an external account."""
    user = await get_current_user_from_request(request)
    session = get_db_session(request)

    account_id = request.query_params.get("account_id")
    if not account_id:
        raise HTTPException(status_code=400, detail="account_id query parameter is required.")

    import uuid

    try:
        parsed_id = uuid.UUID(account_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid account_id.") from exc

    from sqlalchemy import select

    result = await session.execute(
        select(ExternalAccount).where(
            ExternalAccount.id == parsed_id,
            ExternalAccount.user_id == user.id,
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found.")

    await session.delete(account)

    return {"status": "ok", "message": f"{account.external_email} disconnected."}


@router.patch("/account-flags")
async def update_account_flags(request: Request) -> dict[str, str]:
    """PATCH /api/calendar/account-flags — toggle read/write/tasks flags on an account."""
    user = await get_current_user_from_request(request)
    session = get_db_session(request)
    body = await request.json()

    account_id = body.get("account_id")
    if not account_id:
        raise HTTPException(status_code=400, detail="account_id is required.")

    import uuid

    try:
        parsed_id = uuid.UUID(account_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid account_id.") from exc

    from sqlalchemy import select

    result = await session.execute(
        select(ExternalAccount).where(
            ExternalAccount.id == parsed_id,
            ExternalAccount.user_id == user.id,
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found.")

    allowed_flags = {"use_for_calendar", "write_calendar", "use_for_tasks", "write_tasks"}
    flags = body.get("flags", {})

    for key, value in flags.items():
        if key not in allowed_flags:
            raise HTTPException(status_code=400, detail=f"Invalid flag: {key}")
        setattr(account, key, bool(value))

    # Enforce rules: write requires read
    if account.write_calendar and not account.use_for_calendar:
        account.write_calendar = False
    if account.write_tasks and not account.use_for_tasks:
        account.write_tasks = False

    # Enforce rules: todoist cannot have calendar
    if account.provider == "todoist":
        account.use_for_calendar = False
        account.write_calendar = False

    await session.flush()

    return {"status": "ok", "message": "Account flags updated."}
