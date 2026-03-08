from typing import Any

from fastapi import APIRouter

class SimpleRouter:
    def register(self, prefix: str, viewset: type, basename: str) -> None: ...
    @property
    def urls(self) -> APIRouter: ...

class DefaultRouter(SimpleRouter): ...
