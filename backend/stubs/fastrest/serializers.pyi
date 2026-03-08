from typing import Any

class BaseSerializer:
    instance: Any
    data: Any
    context: dict[str, Any]
    validated_data: dict[str, Any]
    def __init__(self, instance: Any = None, data: Any = None, many: bool = False, context: dict[str, Any] | None = None, **kwargs: Any) -> None: ...
    def is_valid(self, raise_exception: bool = False) -> bool: ...
    async def save(self, **kwargs: Any) -> Any: ...
    async def create(self, validated_data: dict[str, Any]) -> Any: ...
    async def update(self, instance: Any, validated_data: dict[str, Any]) -> Any: ...

class Serializer(BaseSerializer): ...

class ModelSerializer(BaseSerializer):
    class Meta:
        model: type
        fields: list[str] | str
        read_only_fields: list[str]
        extra_kwargs: dict[str, dict[str, Any]]
