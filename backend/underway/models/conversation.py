"""Conversation and ChatMessage models."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from underway.models.base import Base
from underway.models.types import MySQLUUID


class Conversation(Base):
    __tablename__ = "conversation"

    id: Mapped[uuid.UUID] = mapped_column(MySQLUUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(MySQLUUID, ForeignKey("app_user.id"))
    title: Mapped[str | None] = mapped_column(String(255), default=None)
    created_at: Mapped[datetime | None] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime | None] = mapped_column(
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    messages: Mapped[list[ChatMessage]] = relationship(
        back_populates="conversation",
        lazy="noload",  # never auto-load; fetch explicitly via the /messages action
        order_by="ChatMessage.sequence",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Conversation {self.id} user={self.user_id}>"


class ChatMessage(Base):
    __tablename__ = "chat_message"

    id: Mapped[uuid.UUID] = mapped_column(MySQLUUID, primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(MySQLUUID, ForeignKey("conversation.id"))
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str | None] = mapped_column(Text, default=None)
    tool_calls: Mapped[Any | None] = mapped_column(type_=JSON, default=None)
    tool_call_id: Mapped[str | None] = mapped_column(String(255), default=None)
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime | None] = mapped_column(default=lambda: datetime.now(UTC))

    conversation: Mapped[Conversation] = relationship(back_populates="messages")

    def to_dict(self) -> dict[str, object]:
        d: dict[str, object] = {"role": self.role, "content": self.content or ""}
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        return d

    def __repr__(self) -> str:
        return f"<ChatMessage {self.id} role={self.role}>"
