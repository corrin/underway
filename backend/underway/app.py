"""FastAPI application factory."""

import logging
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastrest.permissions import IsAuthenticated
from fastrest.routers import DefaultRouter
from fastrest.settings import configure
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from underway.auth.jwt import create_token_auth
from underway.chat.streaming import router as chat_router
from underway.config import Settings, get_settings
from underway.routes.auth import router as auth_router
from underway.routes.auth import test_router as auth_test_router
from underway.routes.calendar import router as calendar_router
from underway.routes.oauth import router as oauth_router
from underway.routes.settings import router as settings_router
from underway.routes.todoist_auth import router as todoist_auth_router
from underway.viewsets.chat import ConversationViewSet
from underway.viewsets.external_accounts import ExternalAccountViewSet
from underway.viewsets.tasks import TaskViewSet

logger = logging.getLogger(__name__)

def create_app(
    settings: Settings | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application."""
    if settings is None:
        settings = get_settings()

    if not settings.testing:
        settings.validate_required()

    app = FastAPI(
        title="Underway",
        description="Intelligent task and calendar management",
        version="0.1.0",
    )
    app.state.settings = settings

    # FastREST configuration: JWT auth + IsAuthenticated by default
    token_auth = create_token_auth(settings.jwt_secret_key)
    configure(
        app,
        {
            "DEFAULT_AUTHENTICATION_CLASSES": [token_auth],
            "DEFAULT_PERMISSION_CLASSES": [IsAuthenticated],
        },
    )

    # Per-app factory: use injected one (tests) or lazily create from settings.
    # Stored in a closure list so the inner async function can rebind it.
    _factory: list[async_sessionmaker[AsyncSession] | None] = [session_factory]

    @app.middleware("http")
    async def db_session_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        """Inject an async DB session into request.state for routes and viewsets."""
        if _factory[0] is None:
            engine = create_async_engine(settings.database_url, echo=False)
            _factory[0] = async_sessionmaker(engine, expire_on_commit=False)
        factory = _factory[0]
        request.state.session_factory = factory
        async with factory() as session:
            request.state.db_session = session
            try:
                response = await call_next(request)
                await session.commit()
            except Exception:
                logger.exception("Request failed; rolling back DB session")
                await session.rollback()
                raise
        return response

    # Plain FastAPI routes
    app.include_router(auth_router)
    app.include_router(calendar_router)
    app.include_router(chat_router)
    app.include_router(oauth_router)
    app.include_router(settings_router)
    app.include_router(todoist_auth_router)

    # Test-only routes — completely absent in production
    if settings.testing:
        app.include_router(auth_test_router)

    # FastREST viewset routes
    rest_router = DefaultRouter()
    rest_router.register("conversations", ConversationViewSet, basename="conversation")
    rest_router.register("external-accounts", ExternalAccountViewSet, basename="external-account")
    rest_router.register("tasks", TaskViewSet, basename="task")
    app.include_router(rest_router.urls, prefix="/api")

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
