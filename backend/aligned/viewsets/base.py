"""Base viewset mixin for injecting async DB session from request.state."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastrest.request import Request


class SessionMixin:
    """Mixin that reads the DB session from request.state (set by middleware)."""

    async def initial(self, request: Request, **kwargs: object) -> None:
        await super().initial(request, **kwargs)  # type: ignore[misc]
        self.set_session(request._request.state.db_session)  # type: ignore[attr-defined]
