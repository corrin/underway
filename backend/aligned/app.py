"""FastAPI application factory."""

from collections.abc import AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastrest.permissions import IsAuthenticated
from fastrest.settings import configure
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from aligned.auth.jwt import create_token_auth
from aligned.config import Settings, get_settings

_session_factory: async_sessionmaker[AsyncSession] | None = None


async def _get_session_factory(settings: Settings) -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        engine = create_async_engine(settings.database_url, echo=False)
        _session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return _session_factory


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    if settings is None:
        settings = get_settings()

    app = FastAPI(
        title="Aligned",
        description="Intelligent task and calendar management",
        version="0.1.0",
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
    async def db_session_middleware(request: Request, call_next: object) -> Response:
        """Inject an async DB session into request.state for routes and viewsets."""

        async def _call_next(request: Request) -> Response:
            result: Response = await call_next(request)  # type: ignore[operator]
            return result

        factory = await _get_session_factory(settings)
        async with factory() as session:
            request.state.db_session = session
            try:
                response = await _call_next(request)
                await session.commit()
            except Exception:
                await session.rollback()
                raise
        return response

    # Dependency for plain FastAPI routes
    async def get_db_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
        yield request.state.db_session

    app.state.get_db_session = get_db_session

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
