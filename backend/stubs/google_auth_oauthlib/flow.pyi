from typing import Any

from google.oauth2.credentials import Credentials


class Flow:
    code_verifier: str | None

    @property
    def credentials(self) -> Credentials: ...

    @classmethod
    def from_client_config(
        cls,
        client_config: dict[str, Any],
        scopes: list[str],
        redirect_uri: str | None = None,
        state: str | None = None,
        **kwargs: Any,
    ) -> "Flow": ...

    def authorization_url(self, **kwargs: Any) -> tuple[str, str]: ...
    def fetch_token(self, **kwargs: Any) -> dict[str, Any]: ...
