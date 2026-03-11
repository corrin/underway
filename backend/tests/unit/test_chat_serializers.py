"""Tests for chat serializers."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

from aligned.serializers.chat import (
    ChatInputSerializer,
    ChatMessageSerializer,
    ConversationSerializer,
)


class TestConversationSerializer:
    def test_serializes_correctly(self) -> None:
        conv = MagicMock()
        conv.id = uuid.uuid4()
        conv.user_id = uuid.uuid4()
        conv.title = "Test conversation"
        conv.created_at = datetime(2026, 1, 1, tzinfo=UTC)
        conv.updated_at = datetime(2026, 1, 2, tzinfo=UTC)

        serializer = ConversationSerializer(instance=conv)
        data = serializer.data

        assert data["id"] == str(conv.id)
        assert data["user_id"] == str(conv.user_id)
        assert data["title"] == "Test conversation"
        assert data["created_at"] == "2026-01-01T00:00:00+00:00"
        assert data["updated_at"] == "2026-01-02T00:00:00+00:00"

    def test_serializes_null_title(self) -> None:
        conv = MagicMock()
        conv.id = uuid.uuid4()
        conv.user_id = uuid.uuid4()
        conv.title = None
        conv.created_at = datetime(2026, 1, 1, tzinfo=UTC)
        conv.updated_at = datetime(2026, 1, 1, tzinfo=UTC)

        serializer = ConversationSerializer(instance=conv)
        data = serializer.data

        assert data["title"] == ""


class TestChatMessageSerializer:
    def test_serializes_correctly(self) -> None:
        msg = MagicMock()
        msg.id = uuid.uuid4()
        msg.conversation_id = uuid.uuid4()
        msg.role = "user"
        msg.content = "Hello, world!"
        msg.tool_calls = None
        msg.tool_call_id = None
        msg.sequence = 0
        msg.created_at = datetime(2026, 1, 1, tzinfo=UTC)

        serializer = ChatMessageSerializer(instance=msg)
        data = serializer.data

        assert data["id"] == str(msg.id)
        assert data["conversation_id"] == str(msg.conversation_id)
        assert data["role"] == "user"
        assert data["content"] == "Hello, world!"
        assert data["tool_calls"] is None
        assert data["tool_call_id"] == ""
        assert data["sequence"] == 0
        assert data["created_at"] == "2026-01-01T00:00:00+00:00"

    def test_serializes_with_tool_calls(self) -> None:
        msg = MagicMock()
        msg.id = uuid.uuid4()
        msg.conversation_id = uuid.uuid4()
        msg.role = "assistant"
        msg.content = None
        msg.tool_calls = [{"id": "call_1", "function": {"name": "test"}}]
        msg.tool_call_id = None
        msg.sequence = 1
        msg.created_at = datetime(2026, 1, 1, tzinfo=UTC)

        serializer = ChatMessageSerializer(instance=msg)
        data = serializer.data

        assert data["content"] == ""
        assert data["tool_calls"] == [{"id": "call_1", "function": {"name": "test"}}]


class TestChatInputSerializer:
    def test_validates_required_message(self) -> None:
        serializer = ChatInputSerializer(data={"message": "Hi there"})
        assert serializer.is_valid()
        assert serializer.validated_data["message"] == "Hi there"

    def test_accepts_optional_conversation_id(self) -> None:
        conv_id = uuid.uuid4()
        serializer = ChatInputSerializer(data={"message": "Hi", "conversation_id": str(conv_id)})
        assert serializer.is_valid()
        assert serializer.validated_data["conversation_id"] == conv_id

    def test_valid_without_conversation_id(self) -> None:
        serializer = ChatInputSerializer(data={"message": "Hello"})
        assert serializer.is_valid()
        assert "conversation_id" not in serializer.validated_data

    def test_rejects_empty_data(self) -> None:
        serializer = ChatInputSerializer(data={})
        assert not serializer.is_valid()
        assert "message" in serializer.errors

    def test_rejects_missing_message(self) -> None:
        conv_id = uuid.uuid4()
        serializer = ChatInputSerializer(data={"conversation_id": str(conv_id)})
        assert not serializer.is_valid()
        assert "message" in serializer.errors
