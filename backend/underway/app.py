"""FastAPI application factory."""

import asyncio
import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastrest.permissions import IsAuthenticated
from fastrest.routers import DefaultRouter
from fastrest.settings import configure
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from underway.auth.jwt import create_token_auth
from underway.chat.streaming import router as chat_router
from underway.config import Settings, get_settings
from underway.providers.token_refresh import token_refresh_loop
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

    # Single factory instance shared by the lifespan and the DB middleware.
    # Stored in a list so the nested functions can mutate the reference.
    _factory: list[async_sessionmaker[AsyncSession] | None] = [session_factory]

    def _get_or_create_factory() -> async_sessionmaker[AsyncSession]:
        if _factory[0] is None:
            engine = create_async_engine(settings.database_url, echo=False)
            _factory[0] = async_sessionmaker(engine, expire_on_commit=False)
        return _factory[0]

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        """Start background tasks on startup, cancel cleanly on shutdown."""
        factory = _get_or_create_factory()
        refresh_task = asyncio.create_task(token_refresh_loop(factory))
        logger.info("Token refresh background task started")
        try:
            yield
        finally:
            refresh_task.cancel()
            try:
                await refresh_task
            except asyncio.CancelledError:
                pass
            logger.info("Token refresh background task stopped")

    app = FastAPI(
        title="Underway",
        description="Intelligent task and calendar management",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = settings

    # CORS — restrict to known frontend origins
    origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # FastREST configuration: JWT auth + IsAuthenticated by default
    token_auth = create_token_auth(settings.jwt_secret_key)
    configure(
        app,
        {
            "DEFAULT_AUTHENTICATION_CLASSES": [token_auth],
            "DEFAULT_PERMISSION_CLASSES": [IsAuthenticated],
        },
    )

    @app.middleware("http")
    async def db_session_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        """Inject an async DB session into request.state for routes and viewsets."""
        factory = _get_or_create_factory()
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
