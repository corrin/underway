"""Task serializers for FastREST."""

from __future__ import annotations

from typing import ClassVar

from fastrest.fields import (
    CharField,
    DateTimeField,
    DictField,
    IntegerField,
    ListField,
    UUIDField,
)
from fastrest.serializers import ModelSerializer, Serializer

from underway.models.task import Task


class TaskSerializer(ModelSerializer):
    id = UUIDField(read_only=True)
    user_id = UUIDField(read_only=True)
    task_user_email = CharField(required=False, allow_null=True)
    provider = CharField(read_only=True)
    provider_task_id = CharField(read_only=True)
    title = CharField()
    description = CharField(required=False, allow_null=True)
    status = CharField(required=False, default="active")
    due_date = DateTimeField(required=False, allow_null=True)
    priority = IntegerField(required=False, allow_null=True)
    project_id = CharField(required=False, allow_null=True)
    project_name = CharField(required=False, allow_null=True)
    parent_id = CharField(required=False, allow_null=True)
    section_id = CharField(required=False, allow_null=True)
    list_type = CharField(required=False, allow_null=True)
    position = IntegerField(required=False, allow_null=True)
    content_hash = CharField(read_only=True)
    last_synced = DateTimeField(read_only=True)
    created_at = DateTimeField(read_only=True)
    updated_at = DateTimeField(read_only=True)

    class Meta:
        model = Task
        fields: ClassVar[list[str]] = [
            "id",
            "user_id",
            "task_user_email",
            "provider",
            "provider_task_id",
            "title",
            "description",
            "status",
            "due_date",
            "priority",
            "project_id",
            "project_name",
            "parent_id",
            "section_id",
            "list_type",
            "position",
            "content_hash",
            "last_synced",
            "created_at",
            "updated_at",
        ]
        read_only_fields: ClassVar[list[str]] = [
            "id",
            "user_id",
            "provider",
            "provider_task_id",
            "content_hash",
            "last_synced",
            "created_at",
            "updated_at",
        ]


class TaskCreateSerializer(ModelSerializer):
    """For creating tasks via chat or direct API."""

    title = CharField()
    description = CharField(required=False, allow_null=True)
    priority = IntegerField(required=False, allow_null=True)

    class Meta:
        model = Task
        fields: ClassVar[list[str]] = ["title", "description", "priority"]


class TaskMoveSerializer(Serializer):
    """For moving tasks between lists."""

    task_id = UUIDField()
    destination = CharField()  # 'prioritized', 'unprioritized', 'completed'
    position = IntegerField(required=False)


class TaskOrderSerializer(Serializer):
    """For reordering tasks within a list."""

    list_type = CharField()
    order = ListField(child=DictField())  # [{id, position}, ...]
