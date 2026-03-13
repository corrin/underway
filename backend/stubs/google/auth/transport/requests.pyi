from typing import Any

from google.oauth2.credentials import Credentials


class Request:
    def __init__(self) -> None: ...


class AuthorizedSession:
    def __init__(
        self,
        credentials: Credentials,
        refresh_status_codes: tuple[int, ...] = ...,
        max_refresh_attempts: int = 2,
        refresh_timeout: float | None = None,
        auth_request: Any = None,
        default_host: str | None = None,
    ) -> None: ...
    def get(self, url: str, **kwargs: Any) -> Any: ...
    def post(self, url: str, **kwargs: Any) -> Any: ...
