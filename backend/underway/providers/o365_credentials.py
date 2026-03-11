"""O365 access token credential for Microsoft Graph API."""

from __future__ import annotations

import time

from azure.core.credentials import AccessToken, TokenCredential


class AccessTokenCredential(TokenCredential):
    """Wraps a raw access token for use with the Microsoft Graph SDK."""

    def __init__(self, token: str) -> None:
        self._token = token

    def get_token(
        self,
        *scopes: str,
        claims: str | None = None,
        tenant_id: str | None = None,
        enable_cae: bool = False,
        **kwargs: object,
    ) -> AccessToken:
        """Return an AccessToken compatible with the Azure SDK."""
        return AccessToken(self._token, int(time.time()) + 3600)
