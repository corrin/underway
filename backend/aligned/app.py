"""FastAPI application factory."""

from fastapi import FastAPI

from aligned.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    if settings is None:
        settings = get_settings()

    app = FastAPI(
        title="Aligned",
        description="Intelligent task and calendar management",
        version="0.1.0",
    )

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
