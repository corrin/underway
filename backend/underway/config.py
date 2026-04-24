"""Application settings loaded from environment variables."""

from pydantic_settings import BaseSettings

REQUIRED_SETTINGS = [
    "database_url",
    "jwt_secret_key",
    "google_client_id",
    "google_client_secret",
]


class Settings(BaseSettings):
    """Application configuration. Values loaded from .env file or environment."""

    database_url: str = "mysql+aiomysql://underway:underway-dev-pass@localhost:3306/underway_dev"
    jwt_secret_key: str = "change-me-in-production"
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = ""
    o365_client_id: str = ""
    o365_client_secret: str = ""
    o365_redirect_uri: str = ""
    base_url: str = "http://localhost:8000"
    debug: bool = False
    testing: bool = False

    google_scopes: str = "https://www.googleapis.com/auth/calendar"
    o365_scopes: str = "https://graph.microsoft.com/Calendars.ReadWrite"

    playwright_chrome_profile: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    def validate_required(self) -> None:
        """Raise if any required settings are missing."""
        missing = [name for name in REQUIRED_SETTINGS if not getattr(self, name)]
        if missing:
            msg = f"Missing required settings: {', '.join(missing)}"
            raise RuntimeError(msg)


def get_settings() -> Settings:
    """Return application settings (cached by pydantic-settings)."""
    return Settings()
