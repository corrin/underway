"""Tests for SQLAlchemy models and MySQLUUID type."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from underway.models.conversation import ChatMessage, Conversation
from underway.models.external_account import ExternalAccount
from underway.models.task import Task
from underway.models.types import MySQLUUID
from underway.models.user import User


class TestMySQLUUID:
    def test_process_bind_param_uuid(self) -> None:
        col_type = MySQLUUID()
        test_uuid = uuid.uuid4()
        result = col_type.process_bind_param(test_uuid, None)  # type: ignore[arg-type]
        assert result == test_uuid.bytes

    def test_process_bind_param_string(self) -> None:
        col_type = MySQLUUID()
        test_uuid = uuid.uuid4()
        result = col_type.process_bind_param(str(test_uuid), None)  # type: ignore[arg-type]
        assert result == test_uuid.bytes

    def test_process_bind_param_none(self) -> None:
        col_type = MySQLUUID()
        assert col_type.process_bind_param(None, None) is None  # type: ignore[arg-type]

    def test_process_result_value_bytes(self) -> None:
        col_type = MySQLUUID()
        test_uuid = uuid.uuid4()
        result = col_type.process_result_value(test_uuid.bytes, None)  # type: ignore[arg-type]
        assert result == test_uuid

    def test_process_result_value_none(self) -> None:
        col_type = MySQLUUID()
        assert col_type.process_result_value(None, None) is None  # type: ignore[arg-type]


class TestUserModel:
    async def test_create_user(self, db_session: AsyncSession) -> None:
        user = User(app_login="test@example.com")
        user.id = uuid.uuid4()
        db_session.add(user)
        await db_session.flush()

        result = await db_session.execute(select(User).where(User.app_login == "test@example.com"))
        loaded = result.scalar_one()
        assert loaded.id == user.id
        assert loaded.app_login == "test@example.com"
        assert loaded.schedule_slot_duration == 60

    async def test_user_repr(self) -> None:
        user = User(app_login="repr@test.com")
        user.id = uuid.uuid4()
        assert "repr@test.com" in repr(user)

    async def test_user_defaults(self, db_session: AsyncSession) -> None:
        user = User(app_login="defaults@test.com")
        user.id = uuid.uuid4()
        db_session.add(user)
        await db_session.flush()

        result = await db_session.execute(select(User).where(User.id == user.id))
        loaded = result.scalar_one()
        assert loaded.ai_api_key is None
        assert loaded.ai_instructions is None
        assert loaded.llm_model is None


class TestExternalAccountModel:
    async def test_create_external_account(self, db_session: AsyncSession) -> None:
        user = User(app_login="ea@test.com")
        user.id = uuid.uuid4()
        db_session.add(user)
        await db_session.flush()

        account = ExternalAccount(
            id=uuid.uuid4(),
            user_id=user.id,
            external_email="ext@gmail.com",
            provider="google",
        )
        db_session.add(account)
        await db_session.flush()

        result = await db_session.execute(select(ExternalAccount).where(ExternalAccount.user_id == user.id))
        loaded = result.scalar_one()
        assert loaded.external_email == "ext@gmail.com"
        assert loaded.provider == "google"

    async def test_user_relationship(self, db_session: AsyncSession) -> None:
        user = User(app_login="rel@test.com")
        user.id = uuid.uuid4()
        db_session.add(user)
        await db_session.flush()

        account = ExternalAccount(
            id=uuid.uuid4(),
            user_id=user.id,
            external_email="rel-ext@gmail.com",
            provider="google",
        )
        db_session.add(account)
        await db_session.commit()

        result = await db_session.execute(select(User).where(User.id == user.id))
        loaded_user = result.scalar_one()
        accounts = await db_session.run_sync(lambda _: loaded_user.external_accounts)
        assert len(accounts) == 1
        assert accounts[0].external_email == "rel-ext@gmail.com"


class TestTaskModel:
    async def test_create_task(self, db_session: AsyncSession) -> None:
        user = User(app_login="task@test.com")
        user.id = uuid.uuid4()
        db_session.add(user)
        await db_session.flush()

        task = Task(
            id=uuid.uuid4(),
            user_id=user.id,
            task_user_email="task@test.com",
            provider="google",
            provider_task_id="gtask_123",
            title="Test task",
            status="needsAction",
            content_hash="abc123",
        )
        db_session.add(task)
        await db_session.flush()

        result = await db_session.execute(select(Task).where(Task.user_id == user.id))
        loaded = result.scalar_one()
        assert loaded.title == "Test task"
        assert loaded.provider == "google"

    def test_to_dict(self) -> None:
        task_id = uuid.uuid4()
        user_id = uuid.uuid4()
        task = Task(
            id=task_id,
            user_id=user_id,
            title="Dict test",
            provider="google",
            provider_task_id="g123",
            status="needsAction",
            content_hash="abc123",
        )
        d = task.to_dict()
        assert d["id"] == str(task_id)
        assert d["user_id"] == str(user_id)
        assert d["title"] == "Dict test"
        assert d["status"] == "needsAction"


class TestConversationModel:
    async def test_create_conversation_with_messages(self, db_session: AsyncSession) -> None:
        user = User(app_login="conv@test.com")
        user.id = uuid.uuid4()
        db_session.add(user)
        await db_session.flush()

        convo = Conversation(id=uuid.uuid4(), user_id=user.id, title="Test convo")
        db_session.add(convo)
        await db_session.flush()

        msg = ChatMessage(
            id=uuid.uuid4(),
            conversation_id=convo.id,
            role="user",
            content="Hello",
            sequence=1,
        )
        db_session.add(msg)
        await db_session.flush()

        result = await db_session.execute(select(Conversation).where(Conversation.id == convo.id))
        loaded = result.scalar_one()
        assert loaded.title == "Test convo"
        # messages use lazy='noload' — fetch explicitly
        msg_result = await db_session.execute(
            select(ChatMessage).where(ChatMessage.conversation_id == convo.id)
        )
        msgs = list(msg_result.scalars().all())
        assert len(msgs) == 1
        assert msgs[0].content == "Hello"
