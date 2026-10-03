"""Temporary local intentions master and rebuildable scheduler coordination state."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from underway.models.base import Base
from underway.models.types import MySQLUUID


class IntentionsRecord(Base):
    __tablename__ = "intentions"

    user_id: Mapped[UUID] = mapped_column(MySQLUUID, ForeignKey("app_user.id"), primary_key=True)
    document: Mapped[dict[str, Any]] = mapped_column(JSON)
    revision: Mapped[int] = mapped_column(default=0)
    last_warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    last_error: Mapped[str | None] = mapped_column(Text, default=None)
    last_published: Mapped[datetime | None] = mapped_column(default=None)
