"""Google ID token verification."""

from __future__ import annotations

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token


def verify_google_id_token(token: str, client_id: str) -> str:
    """Verify a Google ID token and return the user's email.

    This is a blocking I/O call — use asyncio.to_thread() in async contexts.

    Raises ValueError if the token is invalid.
    """
    idinfo: dict[str, object] = id_token.verify_oauth2_token(
        token,
        google_requests.Request(),
        client_id,
    )
    email = idinfo.get("email")
    if not isinstance(email, str):
        raise ValueError("Google ID token missing email claim")
    return email
