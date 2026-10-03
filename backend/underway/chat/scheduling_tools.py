"""Chat access to the same validated scheduling services used by the API."""

from datetime import datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from underway.models.external_account import ExternalAccount
from underway.scheduling.schemas import ActivityReport, Intentions
from underway.scheduling.service import ScheduleService
from underway.scheduling.store import LocalIntentionsStore

DESCRIPTIONS = {
    "get_intentions": "Read the activity tree, targets, cadence rules and available accounts before editing.",
    "set_intentions": (
        "Save the full intentions document using its current revision and regenerate the queue. "
        "Preserve unrelated nodes and settings."
    ),
    "get_schedule": "Read suggestions, actual activity reports with correction IDs, and weekly time rollups.",
    "rebuild_schedule": "Refresh sources and regenerate the next seven days of suggestions.",
    "report_activity": (
        "Record actual activity at the reported tree node. Never infer duration or completion from a scheduled block. "
        "Include fulfilled cadence IDs only for qualifying occurrences. Reuse the same report ID on retries."
    ),
    "correct_activity": "Explicitly correct an existing actual activity report, using its existing ID.",
}

SCHEDULING_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": (
                Intentions.model_json_schema()
                if name == "set_intentions"
                else ActivityReport.model_json_schema()
                if name in ("report_activity", "correct_activity")
                else {"type": "object", "properties": {}, "additionalProperties": False}
            ),
        },
    }
    for name, description in DESCRIPTIONS.items()
]


async def execute_scheduling_tool(
    name: str, arguments: dict[str, Any], user_id: UUID, session: AsyncSession
) -> dict[str, Any]:
    store = LocalIntentionsStore(session)
    service = ScheduleService(session, user_id)
    if name == "get_intentions":
        intentions = await store.get(user_id)
        return {
            "intentions": intentions.model_dump(mode="json"),
            "today": datetime.now(ZoneInfo(intentions.timezone)).date().isoformat(),
            "accounts": [
                {
                    "provider": account.provider,
                    "account": account.external_email,
                    "tasks": account.use_for_tasks,
                    "calendar": account.use_for_calendar,
                    "needs_reauth": account.needs_reauth,
                }
                for account in await ExternalAccount.get_accounts_for_user(session, user_id)
            ],
        }
    elif name == "set_intentions":
        intentions = await store.put(user_id, Intentions.model_validate(arguments))
        result = await service.rebuild()
        return {"intentions": (await store.get(user_id)).model_dump(mode="json"), "schedule": result}
    elif name == "get_schedule":
        return await service.current()
    elif name == "rebuild_schedule":
        return await service.rebuild()
    else:
        return await service.report(ActivityReport.model_validate(arguments), replace=name == "correct_activity")
