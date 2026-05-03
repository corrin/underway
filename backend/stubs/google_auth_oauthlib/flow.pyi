from typing import Any

from google.oauth2.credentials import Credentials


class Flow:
    # Set by authorization_url() when autogenerate_code_verifier=True is passed
    # to from_client_config (or from_client_secrets_file). Re-assigned by callers
    # to inject the persisted verifier into a freshly built Flow before fetch_token().
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
        autogenerate_code_verifier: bool = False,
        **kwargs: Any,
    ) -> "Flow": ...

    def authorization_url(self, **kwargs: Any) -> tuple[str, str]: ...
    def fetch_token(self, **kwargs: Any) -> dict[str, Any]: ...
