"""ExternalAccount viewset — read-only, filtered to current user."""

from __future__ import annotations

from typing import Any

from fastrest.viewsets import ReadOnlyModelViewSet

from aligned.models.external_account import ExternalAccount
from aligned.serializers.external_account import ExternalAccountSerializer
from aligned.viewsets.base import SessionMixin


class ExternalAccountViewSet(SessionMixin, ReadOnlyModelViewSet):
    queryset = ExternalAccount
    serializer_class = ExternalAccountSerializer
    lookup_field_type = str

    async def get_queryset(self) -> Any:
        """Filter to only the current user's accounts."""
        from sqlalchemy import select

        user = self.request.user
        return select(ExternalAccount).where(ExternalAccount.user_id == user.id)
