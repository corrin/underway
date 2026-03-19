"""Application settings loaded from environment variables."""

from functools import cached_property

from pydantic_settings import BaseSettings

REQUIRED_SETTINGS = [
    "database_password",
    "jwt_secret_key",
    "base_url",
    "google_client_id",
    "google_client_secret",
    "todoist_client_id",
    "todoist_client_secret",
]


class Settings(BaseSettings):
    """Application configuration. Values loaded from .env file or environment."""

    database_host: str = "localhost"
    database_port: int = 3306
    database_user: str = "underway"
    database_password: str
    database_name: str = "underway_dev"
    jwt_secret_key: str
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = ""
    o365_client_id: str = ""
    o365_client_secret: str = ""
    o365_redirect_uri: str = ""
    todoist_client_id: str = ""
    todoist_client_secret: str = ""
    todoist_redirect_uri: str = ""
    base_url: str
    debug: bool = False
    testing: bool = False

    google_scopes: str = "https://www.googleapis.com/auth/calendar"
    o365_scopes: str = "https://graph.microsoft.com/Calendars.ReadWrite"

    playwright_chrome_profile: str = ""

    # E2E test credentials — only used by Playwright tests, not by the app.
    google_test_email: str = ""
    google_test_password: str = ""
    o365_test_email: str = ""
    o365_test_password: str = ""
    todoist_test_email: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @cached_property
    def database_url(self) -> str:
        """Build the async database URL from individual fields."""
        return (
            f"mysql+aiomysql://{self.database_user}:{self.database_password}"
            f"@{self.database_host}:{self.database_port}/{self.database_name}"
        )

    def validate_required(self) -> None:
        """Raise if any required settings are missing."""
        missing = [name for name in REQUIRED_SETTINGS if not getattr(self, name)]
        if missing:
            msg = f"Missing required settings: {', '.join(missing)}"
            raise RuntimeError(msg)


def get_settings() -> Settings:
    """Return application settings (cached by pydantic-settings)."""
    return Settings()
