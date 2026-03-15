"""ExternalAccount serializer for FastREST."""

from __future__ import annotations

from typing import ClassVar

from fastrest.fields import BooleanField, CharField, DateTimeField, UUIDField
from fastrest.serializers import ModelSerializer

from underway.models.external_account import ExternalAccount


class ExternalAccountSerializer(ModelSerializer):
    id = UUIDField(read_only=True)
    user_id = UUIDField(read_only=True)

    external_email = CharField(read_only=True)
    provider = CharField(read_only=True)
    write_calendar = BooleanField(read_only=True)
    write_tasks = BooleanField(read_only=True)
    use_for_calendar = BooleanField(read_only=True)
    use_for_tasks = BooleanField(read_only=True)
    needs_reauth = BooleanField(read_only=True)
    last_sync = DateTimeField(read_only=True)

    class Meta:
        model = ExternalAccount
        fields: ClassVar[list[str]] = [
            "id",
            "external_email",
            "provider",
            "user_id",
            "write_calendar",
            "write_tasks",
            "use_for_calendar",
            "use_for_tasks",
            "needs_reauth",
            "last_sync",
        ]
        read_only_fields: ClassVar[list[str]] = ["id", "user_id"]
