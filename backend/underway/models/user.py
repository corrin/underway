"""User model."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from underway.models.base import Base
from underway.models.types import MySQLUUID

if TYPE_CHECKING:
    from underway.models.external_account import ExternalAccount


class User(Base):
    __tablename__ = "app_user"

    id: Mapped[uuid.UUID] = mapped_column(MySQLUUID, primary_key=True, default=uuid.uuid4)
    app_login: Mapped[str] = mapped_column(String(120), unique=True, index=True)

    ai_api_key: Mapped[str | None] = mapped_column(String(255), default=None)
    ai_instructions: Mapped[str | None] = mapped_column(Text, default=None)
    schedule_slot_duration: Mapped[int | None] = mapped_column(default=60)
    llm_model: Mapped[str] = mapped_column(String(100), default="claude-sonnet-4-6")

    external_accounts: Mapped[list[ExternalAccount]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} app_login={self.app_login}>"
