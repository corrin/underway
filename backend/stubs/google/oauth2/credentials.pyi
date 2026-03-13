from datetime import datetime

class Credentials:
    token: str | None
    expiry: datetime | None
    expired: bool
    refresh_token: str | None
    token_uri: str | None
    client_id: str | None
    client_secret: str | None
    scopes: list[str] | None

    def __init__(
        self,
        token: str | None = None,
        refresh_token: str | None = None,
        id_token: str | None = None,
        token_uri: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        scopes: list[str] | None = None,
        default_scopes: list[str] | None = None,
        quota_project_id: str | None = None,
        expiry: datetime | None = None,
        rapt_token: str | None = None,
        refresh_handler: object | None = None,
        enable_reauth_refresh: bool = False,
        granted_scopes: list[str] | None = None,
        trust_boundary: object | None = None,
        universe_domain: str = ...,
        account: str | None = None,
    ) -> None: ...

    def refresh(self, request: object) -> None: ...
