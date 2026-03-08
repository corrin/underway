from typing import Any

from starlette.responses import JSONResponse

class Response(JSONResponse):
    data: Any
    def __init__(self, data: Any = None, status: int = 200, **kwargs: Any) -> None: ...
