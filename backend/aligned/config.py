"""Application settings loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration. Values loaded from .env file or environment."""

    database_url: str = "mysql+aiomysql://aligned:aligned-dev-pass@localhost:3306/aligned_dev"
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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


def get_settings() -> Settings:
    """Return application settings (cached by pydantic-settings)."""
    return Settings()
