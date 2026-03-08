"""Tests for Google ID token verification."""

from unittest.mock import MagicMock, patch

import pytest

from aligned.auth.google import verify_google_id_token

CLIENT_ID = "test-client-id.apps.googleusercontent.com"


class TestVerifyGoogleIdToken:
    @patch("aligned.auth.google.id_token.verify_oauth2_token")
    @patch("aligned.auth.google.google_requests.Request")
    def test_returns_email_on_success(self, mock_request: MagicMock, mock_verify: MagicMock) -> None:
        mock_verify.return_value = {"email": "user@example.com", "sub": "12345"}
        email = verify_google_id_token("valid-token", CLIENT_ID)
        assert email == "user@example.com"
        mock_verify.assert_called_once_with("valid-token", mock_request(), CLIENT_ID)

    @patch("aligned.auth.google.id_token.verify_oauth2_token")
    @patch("aligned.auth.google.google_requests.Request")
    def test_raises_on_invalid_token(self, mock_request: MagicMock, mock_verify: MagicMock) -> None:
        mock_verify.side_effect = ValueError("Invalid token")
        with pytest.raises(ValueError, match="Invalid token"):
            verify_google_id_token("bad-token", CLIENT_ID)

    @patch("aligned.auth.google.id_token.verify_oauth2_token")
    @patch("aligned.auth.google.google_requests.Request")
    def test_raises_when_email_missing(self, mock_request: MagicMock, mock_verify: MagicMock) -> None:
        mock_verify.return_value = {"sub": "12345"}
        with pytest.raises(ValueError, match="missing email"):
            verify_google_id_token("token-no-email", CLIENT_ID)
