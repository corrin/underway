"""Tests for application configuration validation."""

import pytest

from underway.config import Settings


class TestValidateRequired:
    def test_valid_settings_passes(self) -> None:
        settings = Settings(
            _env_file=None,
            database_password="x",
            jwt_secret_key="test-secret-key-at-least-32-chars!",
            base_url="http://test",
            google_client_id="test-id",
            google_client_secret="test-secret",
            todoist_client_id="test-todoist-id",
            todoist_client_secret="test-todoist-secret",
        )
        settings.validate_required()  # should not raise

    def test_missing_google_client_id_raises(self) -> None:
        settings = Settings(
            _env_file=None,
            database_password="x",
            jwt_secret_key="test-secret-key-at-least-32-chars!",
            base_url="http://test",
            google_client_id="",
            google_client_secret="test-secret",
        )
        with pytest.raises(RuntimeError, match="google_client_id"):
            settings.validate_required()

    def test_missing_multiple_raises(self) -> None:
        settings = Settings(
            _env_file=None,
            database_password="x",
            jwt_secret_key="test-secret-key-at-least-32-chars!",
            base_url="http://test",
            google_client_id="",
            google_client_secret="",
        )
        with pytest.raises(RuntimeError, match=r"google_client_id.*google_client_secret"):
            settings.validate_required()
