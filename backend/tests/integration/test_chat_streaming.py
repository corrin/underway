"""Integration tests for the SSE streaming chat and dashboard endpoints."""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from underway.auth.jwt import create_access_token
from underway.models.conversation import Conversation
from underway.models.task import Task
from underway.models.user import User

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

SECRET = "test-secret-key-at-least-32-chars!"


async def _create_user(
    db_session: AsyncSession,
    email: str = "chat@example.com",
    ai_api_key: str = "test-key",
    llm_model: str = "claude-sonnet-4-6",
) -> User:
    user = User(app_login=email, ai_api_key=ai_api_key, llm_model=llm_model)
    user.id = uuid.uuid4()
    db_session.add(user)
    await db_session.commit()
    return user


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(user.id, user.app_login, SECRET)
    return {"Authorization": f"Bearer {token}"}


async def _mock_chunks(content: str) -> AsyncGenerator[MagicMock, None]:
    """Yield mock streaming chunks with content tokens."""
    for word in content.split():
        chunk = MagicMock()
        chunk.choices = [MagicMock()]
        chunk.choices[0].delta = MagicMock()
        chunk.choices[0].delta.content = word + " "
        chunk.choices[0].delta.tool_calls = None
        yield chunk


async def _mock_tool_call_chunks() -> AsyncGenerator[MagicMock, None]:
    """Yield mock streaming chunks that contain a tool call."""
    # First chunk: start of tool call
    chunk1 = MagicMock()
    chunk1.choices = [MagicMock()]
    chunk1.choices[0].delta = MagicMock()
    chunk1.choices[0].delta.content = None
    tc = MagicMock()
    tc.index = 0
    tc.id = "call_123"
    tc.function = MagicMock()
    tc.function.name = "get_tasks"
    tc.function.arguments = "{}"
    chunk1.choices[0].delta.tool_calls = [tc]
    yield chunk1


async def _mock_content_after_tool(content: str) -> AsyncGenerator[MagicMock, None]:
    """Yield content chunks (used as second LLM call after tool execution)."""
    for word in content.split():
        chunk = MagicMock()
        chunk.choices = [MagicMock()]
        chunk.choices[0].delta = MagicMock()
        chunk.choices[0].delta.content = word + " "
        chunk.choices[0].delta.tool_calls = None
        yield chunk


def _parse_sse_events(text: str) -> list[dict[str, Any]]:
    """Parse SSE text into a list of event dicts."""
    events: list[dict[str, Any]] = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            data = json.loads(line[6:])
            events.append(data)
    return events


class TestChatEndpoint:
    @pytest.mark.usefixtures("db_session")
    async def test_chat_returns_sse_stream(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)

        with patch("underway.chat.streaming.litellm") as mock_litellm:
            mock_litellm.acompletion = AsyncMock(return_value=_mock_chunks("Hello world"))
            response = await client.post(
                "/api/chat",
                json={"message": "Hi there"},
                headers=_auth_headers(user),
            )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        events = _parse_sse_events(response.text)
        token_events = [e for e in events if e["type"] == "token"]
        done_events = [e for e in events if e["type"] == "done"]

        assert len(token_events) >= 1
        assert len(done_events) == 1
        assert "conversation_id" in done_events[0]

    @pytest.mark.usefixtures("db_session")
    async def test_chat_creates_conversation(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)

        with patch("underway.chat.streaming.litellm") as mock_litellm:
            mock_litellm.acompletion = AsyncMock(return_value=_mock_chunks("OK"))
            await client.post(
                "/api/chat",
                json={"message": "My test message"},
                headers=_auth_headers(user),
            )

        from sqlalchemy import select

        result = await db_session.execute(select(Conversation).where(Conversation.user_id == user.id))
        convs = list(result.scalars().all())
        assert len(convs) == 1
        assert convs[0].title == "My test message"

    @pytest.mark.usefixtures("db_session")
    async def test_chat_persists_messages(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)

        with patch("underway.chat.streaming.litellm") as mock_litellm:
            mock_litellm.acompletion = AsyncMock(return_value=_mock_chunks("Reply"))
            await client.post(
                "/api/chat",
                json={"message": "Hello"},
                headers=_auth_headers(user),
            )

        from sqlalchemy import select

        from underway.models.conversation import ChatMessage

        result = await db_session.execute(select(ChatMessage).order_by(ChatMessage.sequence))
        msgs = list(result.scalars().all())
        assert len(msgs) == 2
        assert msgs[0].role == "user"
        assert msgs[0].content == "Hello"
        assert msgs[1].role == "assistant"
        assert "Reply" in (msgs[1].content or "")

    @pytest.mark.usefixtures("db_session")
    async def test_chat_requires_message(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        response = await client.post(
            "/api/chat",
            json={"message": ""},
            headers=_auth_headers(user),
        )
        assert response.status_code == 400

    @pytest.mark.usefixtures("db_session")
    async def test_chat_requires_api_key(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session, email="nokey@example.com", ai_api_key=None)  # type: ignore[arg-type]
        response = await client.post(
            "/api/chat",
            json={"message": "Hello"},
            headers=_auth_headers(user),
        )
        assert response.status_code == 400

    @pytest.mark.usefixtures("db_session")
    async def test_chat_with_existing_conversation(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        conv = Conversation(id=uuid.uuid4(), user_id=user.id, title="Existing")
        db_session.add(conv)
        await db_session.commit()

        with patch("underway.chat.streaming.litellm") as mock_litellm:
            mock_litellm.acompletion = AsyncMock(return_value=_mock_chunks("OK"))
            response = await client.post(
                "/api/chat",
                json={"message": "Follow up", "conversation_id": str(conv.id)},
                headers=_auth_headers(user),
            )

        assert response.status_code == 200

        from sqlalchemy import select

        result = await db_session.execute(select(Conversation).where(Conversation.user_id == user.id))
        convs = list(result.scalars().all())
        # Should reuse existing, not create new
        assert len(convs) == 1
        assert convs[0].id == conv.id


class TestToolCallingLoop:
    @pytest.mark.usefixtures("db_session")
    async def test_tool_call_and_response(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        call_count = 0

        async def _side_effect(*args: object, **kwargs: object) -> AsyncGenerator[MagicMock, None]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _mock_tool_call_chunks()
            return _mock_content_after_tool("Here are your tasks")

        with patch("underway.chat.streaming.litellm") as mock_litellm:
            mock_litellm.acompletion = AsyncMock(side_effect=_side_effect)
            response = await client.post(
                "/api/chat",
                json={"message": "Show my tasks"},
                headers=_auth_headers(user),
            )

        assert response.status_code == 200
        events = _parse_sse_events(response.text)
        types = [e["type"] for e in events]
        assert "tool_call" in types
        assert "done" in types


class TestDashboard:
    @pytest.mark.usefixtures("db_session")
    async def test_dashboard_returns_tasks_and_calendar(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        task = Task(
            id=uuid.uuid4(),
            user_id=user.id,
            provider="chat",
            provider_task_id=str(uuid.uuid4()),
            title="Test task",
            status="active",
            list_type="unprioritized",
            position=0,
            content_hash="",
        )
        db_session.add(task)
        await db_session.commit()

        response = await client.get("/api/dashboard", headers=_auth_headers(user))
        assert response.status_code == 200
        data = response.json()
        assert "tasks" in data
        assert "events" in data
        assert "prioritized" in data["tasks"]
        assert "unprioritized" in data["tasks"]
        assert "completed" in data["tasks"]
        assert len(data["tasks"]["unprioritized"]) == 1
        assert data["events"] == []

    @pytest.mark.usefixtures("db_session")
    async def test_dashboard_scoped_to_user(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user1 = await _create_user(db_session, email="dash1@example.com")
        user2 = await _create_user(db_session, email="dash2@example.com")

        task1 = Task(
            id=uuid.uuid4(),
            user_id=user1.id,
            provider="chat",
            provider_task_id=str(uuid.uuid4()),
            title="User1 task",
            status="active",
            list_type="unprioritized",
            position=0,
            content_hash="",
        )
        task2 = Task(
            id=uuid.uuid4(),
            user_id=user2.id,
            provider="chat",
            provider_task_id=str(uuid.uuid4()),
            title="User2 task",
            status="active",
            list_type="unprioritized",
            position=0,
            content_hash="",
        )
        db_session.add_all([task1, task2])
        await db_session.commit()

        response = await client.get("/api/dashboard", headers=_auth_headers(user1))
        data = response.json()
        assert len(data["tasks"]["unprioritized"]) == 1
        assert data["tasks"]["unprioritized"][0]["title"] == "User1 task"
