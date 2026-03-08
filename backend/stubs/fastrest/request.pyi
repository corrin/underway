from typing import Any

from starlette.requests import Request as StarletteRequest

class Request:
    _request: StarletteRequest
    data: dict[str, Any] | Any
    user: Any
    auth: Any
    method: str
    headers: dict[str, str]
    def __init__(self, request: StarletteRequest | Any) -> None: ...
