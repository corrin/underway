"""Chat serializers for conversations and messages."""

from __future__ import annotations

from typing import ClassVar

from fastrest.fields import (
    CharField,
    DateTimeField,
    IntegerField,
    JSONField,
    UUIDField,
)
from fastrest.serializers import ModelSerializer, Serializer

from aligned.models.conversation import ChatMessage, Conversation


class ConversationSerializer(ModelSerializer):
    id = UUIDField(read_only=True)
    user_id = UUIDField(read_only=True)
    title = CharField(required=False, allow_null=True)
    created_at = DateTimeField(read_only=True)
    updated_at = DateTimeField(read_only=True)

    class Meta:
        model = Conversation
        fields: ClassVar[list[str]] = [
            "id",
            "user_id",
            "title",
            "created_at",
            "updated_at",
        ]
        read_only_fields: ClassVar[list[str]] = [
            "id",
            "user_id",
            "created_at",
            "updated_at",
        ]


class ChatMessageSerializer(ModelSerializer):
    id = UUIDField(read_only=True)
    conversation_id = UUIDField(read_only=True)
    role = CharField()
    content = CharField(required=False, allow_null=True)
    tool_calls = JSONField(required=False, allow_null=True)
    tool_call_id = CharField(required=False, allow_null=True)
    sequence = IntegerField(read_only=True)
    created_at = DateTimeField(read_only=True)

    class Meta:
        model = ChatMessage
        fields: ClassVar[list[str]] = [
            "id",
            "conversation_id",
            "role",
            "content",
            "tool_calls",
            "tool_call_id",
            "sequence",
            "created_at",
        ]
        read_only_fields: ClassVar[list[str]] = [
            "id",
            "conversation_id",
            "sequence",
            "created_at",
        ]


class ChatInputSerializer(Serializer):
    """Validates user chat input."""

    message = CharField(required=True)
    conversation_id = UUIDField(required=False)
