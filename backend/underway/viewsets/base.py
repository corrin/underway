"""Base viewset mixin for injecting async DB session from request.state."""

from __future__ import annotations

from fastrest.generics import GenericAPIView
from fastrest.request import Request


class SessionMixin(GenericAPIView):
    """Mixin that reads the DB session from request.state (set by middleware)."""

    async def initial(self, request: Request, **kwargs: str) -> None:
        await super().initial(request, **kwargs)
        self.set_session(request._request.state.db_session)
