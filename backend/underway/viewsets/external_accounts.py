"""ExternalAccount viewset — read-only list/detail, plus a task-enablement action."""

from __future__ import annotations

import uuid

from fastapi import HTTPException
from fastrest.decorators import action
from fastrest.request import Request
from fastrest.viewsets import ReadOnlyModelViewSet
from sqlalchemy import select

from underway.models.external_account import ExternalAccount
from underway.serializers.external_account import ExternalAccountSerializer
from underway.viewsets.base import SessionMixin


class ExternalAccountViewSet(SessionMixin, ReadOnlyModelViewSet):
    queryset = ExternalAccount
    serializer_class = ExternalAccountSerializer
    lookup_field_type = str

    async def get_queryset(self) -> list[ExternalAccount]:
        """Filter to only the current user's accounts."""
        user = self.request.user
        stmt = select(ExternalAccount).where(ExternalAccount.user_id == user.id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    @action(methods=["post"], detail=True, url_path="use-for-tasks")
    async def use_for_tasks(self, request: Request, pk: str = "", **kwargs: str) -> dict[str, str]:
        """POST /api/external-accounts/{pk}/use-for-tasks — enable an account as a task source."""
        user = request.user
        session = self._session

        try:
            parsed_id = uuid.UUID(pk)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid account id.") from exc

        result = await session.execute(
            select(ExternalAccount).where(
                ExternalAccount.id == parsed_id,
                ExternalAccount.user_id == user.id,
            )
        )
        account = result.scalar_one_or_none()
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found.")
        else:
            account.use_for_tasks = True
            await ExternalAccount.set_as_primary(
                session,
                external_email=account.external_email,
                provider=account.provider,
                user_id=user.id,
                account_type="tasks",
            )
            await session.flush()

        return {"status": "ok"}
