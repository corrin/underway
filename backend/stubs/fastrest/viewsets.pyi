from typing import Any

from fastrest.generics import GenericAPIView

class ViewSetMixin:
    action_map: dict[str, str]
    @classmethod
    def get_action_endpoints(
        cls, actions: dict[str, str], basename: str, serializer_class: type | None = None
    ) -> dict[str, Any]: ...

class ModelViewSet(ViewSetMixin, GenericAPIView): ...
class ReadOnlyModelViewSet(ViewSetMixin, GenericAPIView): ...
