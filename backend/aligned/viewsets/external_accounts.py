"""ExternalAccount viewset — read-only, filtered to current user."""

from __future__ import annotations

from fastrest.viewsets import ReadOnlyModelViewSet
from sqlalchemy import select

from aligned.models.external_account import ExternalAccount
from aligned.serializers.external_account import ExternalAccountSerializer
from aligned.viewsets.base import SessionMixin


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
