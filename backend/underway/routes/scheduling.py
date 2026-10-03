"""Authenticated intentions import/export, queue publication and actual activity."""

from typing import Any

from fastapi import APIRouter, HTTPException

from underway.routes.settings import CurrentUser, DbSession
from underway.scheduling.schemas import ActivityReport, Intentions
from underway.scheduling.service import ScheduleService
from underway.scheduling.store import LocalIntentionsStore

router = APIRouter(prefix="/api", tags=["scheduling"])


@router.get("/intentions")
async def get_intentions(current_user: CurrentUser, session: DbSession) -> Intentions:
    return await LocalIntentionsStore(session).get(current_user.id)


@router.put("/intentions")
async def put_intentions(body: Intentions, current_user: CurrentUser, session: DbSession) -> dict[str, Any]:
    try:
        document = await LocalIntentionsStore(session).put(current_user.id, body)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    schedule = await ScheduleService(session, current_user.id).rebuild()
    document = await LocalIntentionsStore(session).get(current_user.id)
    return {"intentions": document.model_dump(mode="json"), "schedule": schedule}


@router.get("/schedule")
async def get_schedule(current_user: CurrentUser, session: DbSession) -> dict[str, Any]:
    return await ScheduleService(session, current_user.id).current()


@router.post("/schedule/rebuild")
async def rebuild_schedule(current_user: CurrentUser, session: DbSession) -> dict[str, Any]:
    return await ScheduleService(session, current_user.id).rebuild()


@router.post("/activity")
async def report_activity(body: ActivityReport, current_user: CurrentUser, session: DbSession) -> dict[str, Any]:
    try:
        return await ScheduleService(session, current_user.id).report(body)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.put("/activity/{report_id}")
async def correct_activity(
    report_id: str, body: ActivityReport, current_user: CurrentUser, session: DbSession
) -> dict[str, Any]:
    if report_id != body.id:
        raise HTTPException(422, "The URL and report ID must match.")
    else:
        try:
            return await ScheduleService(session, current_user.id).report(body, replace=True)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
