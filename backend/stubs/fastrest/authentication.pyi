from collections.abc import Callable
from typing import Any

class BaseAuthentication:
    def authenticate(self, request: Any) -> tuple[Any, Any] | None: ...

class TokenAuthentication(BaseAuthentication):
    keyword: str
    get_user_by_token: Callable[[str], Any] | None
    def __init__(
        self,
        get_user_by_token: Callable[[str], Any] | None = None,
        keyword: str | None = None,
    ) -> None: ...

class BasicAuthentication(BaseAuthentication): ...
class SessionAuthentication(BaseAuthentication): ...
