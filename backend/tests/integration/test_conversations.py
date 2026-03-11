"""Integration tests for conversation CRUD and messages action."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from underway.auth.jwt import create_access_token

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession
from underway.models.conversation import ChatMessage, Conversation
from underway.models.user import User

SECRET = "test-secret-key-at-least-32-chars!"


async def _create_user(db_session: AsyncSession, email: str = "chat@example.com") -> User:
    user = User(app_login=email)
    user.id = uuid.uuid4()
    db_session.add(user)
    await db_session.commit()
    return user


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(user.id, user.app_login, SECRET)
    return {"Authorization": f"Bearer {token}"}


async def _create_conversation(
    db_session: AsyncSession,
    user: User,
    title: str | None = "Test conversation",
) -> Conversation:
    conv = Conversation(user_id=user.id, title=title)
    db_session.add(conv)
    await db_session.commit()
    await db_session.refresh(conv)
    return conv


async def _create_message(
    db_session: AsyncSession,
    conversation: Conversation,
    role: str = "user",
    content: str = "Hello",
    sequence: int = 0,
) -> ChatMessage:
    msg = ChatMessage(
        conversation_id=conversation.id,
        role=role,
        content=content,
        sequence=sequence,
    )
    db_session.add(msg)
    await db_session.commit()
    await db_session.refresh(msg)
    return msg


class TestConversationList:
    async def test_list_returns_users_conversations(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        await _create_conversation(db_session, user, "My chat")
        response = await client.get("/api/conversations", headers=_auth_headers(user))
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "My chat"

    async def test_list_scoped_to_user(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user1 = await _create_user(db_session, "user1@chat.com")
        user2 = await _create_user(db_session, "user2@chat.com")
        await _create_conversation(db_session, user1, "User1 chat")
        await _create_conversation(db_session, user2, "User2 chat")

        response = await client.get("/api/conversations", headers=_auth_headers(user1))
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "User1 chat"


class TestConversationCreate:
    async def test_create_conversation(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        response = await client.post(
            "/api/conversations",
            json={"title": "New chat"},
            headers=_auth_headers(user),
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "New chat"
        assert data["user_id"] is not None


class TestConversationDelete:
    async def test_delete_conversation(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        conv = await _create_conversation(db_session, user, "Doomed")
        response = await client.delete(f"/api/conversations/{conv.id}", headers=_auth_headers(user))
        assert response.status_code == 204

        response = await client.get(f"/api/conversations/{conv.id}", headers=_auth_headers(user))
        assert response.status_code == 404

    async def test_cannot_delete_other_users_conversation(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user1 = await _create_user(db_session, "owner@chat.com")
        user2 = await _create_user(db_session, "intruder@chat.com")
        conv = await _create_conversation(db_session, user1, "Private")

        response = await client.delete(f"/api/conversations/{conv.id}", headers=_auth_headers(user2))
        assert response.status_code == 404


class TestConversationMessages:
    async def test_get_messages_for_conversation(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        conv = await _create_conversation(db_session, user, "With messages")
        await _create_message(db_session, conv, "user", "Hello", sequence=0)
        await _create_message(db_session, conv, "assistant", "Hi there!", sequence=1)

        response = await client.get(
            f"/api/conversations/{conv.id}/messages",
            headers=_auth_headers(user),
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["role"] == "user"
        assert data[0]["content"] == "Hello"
        assert data[1]["role"] == "assistant"
        assert data[1]["content"] == "Hi there!"
