"""Replaceable intentions persistence, with optimistic edit protection."""

from typing import Protocol, cast
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from underway.models.intentions import IntentionsRecord
from underway.scheduling.schemas import Intentions


class IntentionsStore(Protocol):
    async def get(self, user_id: UUID) -> Intentions: ...

    async def put(self, user_id: UUID, document: Intentions) -> Intentions: ...


class LocalIntentionsStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user_id: UUID) -> Intentions:
        record = await self.session.get(IntentionsRecord, user_id)
        if record is None:
            return Intentions()
        else:
            return Intentions.model_validate({**record.document, "revision": record.revision})

    async def put(self, user_id: UUID, document: Intentions) -> Intentions:
        record = await self.session.scalar(select(IntentionsRecord).where(IntentionsRecord.user_id == user_id))
        saved = document.model_copy(update={"revision": document.revision + 1})
        if record is None:
            if document.revision != 0:
                raise ValueError("Intentions have changed; read them again before saving.")
            else:
                self.session.add(
                    IntentionsRecord(user_id=user_id, document=saved.model_dump(mode="json"), revision=saved.revision)
                )
        else:
            result = await self.session.execute(
                update(IntentionsRecord)
                .where(IntentionsRecord.user_id == user_id, IntentionsRecord.revision == document.revision)
                .values(document=saved.model_dump(mode="json"), revision=saved.revision)
            )
            if cast(CursorResult[tuple[()]], result).rowcount != 1:
                raise ValueError("Intentions have changed; read them again before saving.")
            else:
                pass
        await self.session.flush()
        return saved
