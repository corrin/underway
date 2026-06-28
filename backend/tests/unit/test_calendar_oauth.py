"""Tests for calendar OAuth URL generation."""

from underway.config import Settings


class TestGoogleOAuthUrl:
    def test_build_url_returns_tuple(self) -> None:
        from underway.providers.calendar.google import build_google_oauth_url

        settings = Settings(
            google_client_id="test-client-id",
            google_client_secret="test-secret",
            google_redirect_uri="http://localhost:8000/api/oauth/google/callback",
        )
        url, state, code_verifier = build_google_oauth_url(settings)
        assert "accounts.google.com" in url
        assert "test-client-id" in url
        assert state  # non-empty
        assert code_verifier  # PKCE verifier generated

    def test_url_includes_calendar_scope(self) -> None:
        from underway.providers.calendar.google import build_google_oauth_url

        settings = Settings(
            google_client_id="test-id",
            google_client_secret="test-secret",
            google_redirect_uri="http://localhost:8000/api/oauth/google/callback",
        )
        url, _, _cv = build_google_oauth_url(settings)
        assert "calendar" in url


class TestO365OAuthUrl:
    def test_build_url_returns_tuple(self) -> None:
        from underway.providers.calendar.o365 import build_o365_oauth_url

        settings = Settings(
            o365_client_id="test-o365-id",
            o365_client_secret="test-secret",
            o365_redirect_uri="http://localhost:8000/api/oauth/o365/callback",
        )
        url, state = build_o365_oauth_url(settings)
        assert "login.microsoftonline.com" in url
        assert "test-o365-id" in url
        assert state

    def test_url_includes_calendar_scope(self) -> None:
        from underway.providers.calendar.o365 import build_o365_oauth_url

        settings = Settings(
            o365_client_id="test-id",
            o365_client_secret="test-secret",
            o365_redirect_uri="http://localhost:8000/callback",
        )
        url, _ = build_o365_oauth_url(settings)
        assert "Calendars" in url

    def test_url_is_properly_percent_encoded(self) -> None:
        """Scope contains spaces and the redirect URI contains :// — both must
        be percent-encoded so the browser sends a syntactically valid URL."""
        from underway.providers.calendar.o365 import build_o365_oauth_url

        settings = Settings(
            o365_client_id="test-id",
            o365_client_secret="test-secret",
            o365_redirect_uri="https://underway-lakeland.ngrok.io/api/oauth/o365/callback",
        )
        url, _ = build_o365_oauth_url(settings)
        # No raw spaces in the query string
        assert " " not in url.split("?", 1)[1]
        # Scope spaces encoded as + or %20
        assert ("scope=https%3A" in url) or ("scope=https%3a" in url)
        # Redirect URI is percent-encoded
        assert "redirect_uri=https%3A%2F%2F" in url
