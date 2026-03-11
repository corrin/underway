"""Conversation viewset — CRUD + messages action."""

from __future__ import annotations

import uuid as _uuid
from typing import cast

from fastrest.decorators import action
from fastrest.exceptions import NotFound
from fastrest.request import Request
from fastrest.viewsets import ModelViewSet
from sqlalchemy import select

from underway.models.conversation import Conversation
from underway.serializers.chat import ChatMessageSerializer, ConversationSerializer
from underway.viewsets.base import SessionMixin


class ConversationViewSet(SessionMixin, ModelViewSet):
    queryset = Conversation
    serializer_class = ConversationSerializer
    lookup_field_type = str

    async def get_queryset(self) -> list[Conversation]:
        """Scope to current user, ordered by most recently updated."""
        user = self.request.user
        session = self._session
        stmt = select(Conversation).where(Conversation.user_id == user.id).order_by(Conversation.updated_at.desc())
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_object(self) -> Conversation:
        """Retrieve a single conversation scoped to the current user."""
        user = self.request.user
        session = self._session
        lookup_value = self.kwargs.get(self.lookup_url_kwarg or self.lookup_field)
        result = await session.execute(
            select(Conversation).where(
                Conversation.id == _uuid.UUID(str(lookup_value)),
                Conversation.user_id == user.id,
            )
        )
        obj = result.scalar_one_or_none()
        if obj is None:
            raise NotFound()
        return cast("Conversation", obj)

    async def perform_create(self, serializer: ConversationSerializer) -> None:
        """Set user_id from the authenticated request user."""
        user = self.request.user
        session = self._session
        data = dict(serializer.validated_data)
        conversation = Conversation(user_id=user.id, **data)
        session.add(conversation)
        await session.flush()
        serializer.instance = conversation

    @action(methods=["get"], detail=True, url_path="messages")
    async def messages(self, request: Request, pk: str = "", **kwargs: str) -> list[dict[str, object]]:
        """GET /api/conversations/{pk}/messages — return messages for a conversation."""
        user = request.user
        session = self._session

        result = await session.execute(
            select(Conversation).where(
                Conversation.id == _uuid.UUID(pk),
                Conversation.user_id == user.id,
            )
        )
        conversation = result.scalar_one_or_none()
        if conversation is None:
            raise NotFound()

        result_data: list[dict[str, object]] = ChatMessageSerializer(conversation.messages, many=True).data
        return result_data
