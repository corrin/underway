"""Base viewset mixin for injecting async DB session from request.state."""

from __future__ import annotations

from fastrest.generics import GenericAPIView
from fastrest.permissions import IsAuthenticated
from fastrest.request import Request


class SessionMixin(GenericAPIView):
    """Mixin that reads the DB session from request.state (set by middleware).

    Also pins ``permission_classes`` to ``IsAuthenticated``. fastrest's base view
    sets ``permission_classes = [AllowAny]`` as a class attribute, and
    ``_resolve_classes`` returns the first non-empty attribute it finds — so the
    app-level ``DEFAULT_PERMISSION_CLASSES`` is never consulted. Setting it per
    instance here ensures every viewset actually enforces authentication instead
    of silently running as AllowAny. (Assigned in ``__init__`` rather than as a
    class attribute because the base declares it as an instance variable, so a
    ``ClassVar`` override would not type-check.)
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.permission_classes = [IsAuthenticated]

    async def initial(self, request: Request, **kwargs: str) -> None:
        await super().initial(request, **kwargs)
        self.set_session(request._request.state.db_session)
