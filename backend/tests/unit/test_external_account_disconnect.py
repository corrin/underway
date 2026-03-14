"""Unit tests for ExternalAccount.disconnect() method."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from underway.models.external_account import ExternalAccount
from underway.models.user import User


async def _create_user(session: AsyncSession) -> User:
    user = User(app_login="disconnect-test@test.com")
    user.id = uuid.uuid4()
    session.add(user)
    await session.flush()
    return user


async def _create_account(
    session: AsyncSession,
    user: User,
    *,
    provider: str = "google",
    email: str = "test@gmail.com",
    use_for_calendar: bool = False,
    use_for_tasks: bool = False,
    write_calendar: bool = False,
    write_tasks: bool = False,
) -> ExternalAccount:
    account = ExternalAccount(
        user_id=user.id,
        external_email=email,
        provider=provider,
        token="tok",
        use_for_calendar=use_for_calendar,
        use_for_tasks=use_for_tasks,
        write_calendar=write_calendar,
        write_tasks=write_tasks,
    )
    session.add(account)
    await session.flush()
    return account


class TestDisconnectSingleUse:
    """When an account is only used for one purpose, disconnect should hard delete."""

    async def test_calendar_only_hard_deletes(self, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        account = await _create_account(db_session, user, use_for_calendar=True)
        account_id = account.id
        await db_session.commit()

        await account.disconnect("calendar", db_session)
        await db_session.commit()

        result = await db_session.get(ExternalAccount, account_id)
        assert result is None

    async def test_tasks_only_hard_deletes(self, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        account = await _create_account(db_session, user, use_for_tasks=True)
        account_id = account.id
        await db_session.commit()

        await account.disconnect("tasks", db_session)
        await db_session.commit()

        result = await db_session.get(ExternalAccount, account_id)
        assert result is None


class TestDisconnectDualUse:
    """When an account is used for both purposes, disconnect should soft delete."""

    async def test_disconnect_calendar_keeps_tasks(self, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        account = await _create_account(
            db_session, user, use_for_calendar=True, use_for_tasks=True, write_calendar=True
        )
        account_id = account.id
        await db_session.commit()

        await account.disconnect("calendar", db_session)
        await db_session.commit()

        refreshed = await db_session.get(ExternalAccount, account_id)
        assert refreshed is not None
        assert refreshed.use_for_calendar is False
        assert refreshed.write_calendar is False
        assert refreshed.use_for_tasks is True

    async def test_disconnect_tasks_keeps_calendar(self, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        account = await _create_account(db_session, user, use_for_calendar=True, use_for_tasks=True, write_tasks=True)
        account_id = account.id
        await db_session.commit()

        await account.disconnect("tasks", db_session)
        await db_session.commit()

        refreshed = await db_session.get(ExternalAccount, account_id)
        assert refreshed is not None
        assert refreshed.use_for_tasks is False
        assert refreshed.write_tasks is False
        assert refreshed.use_for_calendar is True


class TestWriteReassignment:
    """When disconnecting the writable account, another should be promoted."""

    async def test_reassigns_write_calendar(self, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        writable = await _create_account(
            db_session, user, email="writable@gmail.com", use_for_calendar=True, write_calendar=True
        )
        other = await _create_account(
            db_session, user, email="other@gmail.com", use_for_calendar=True, write_calendar=False
        )
        await db_session.commit()

        await writable.disconnect("calendar", db_session)
        await db_session.commit()

        await db_session.refresh(other)
        assert other.write_calendar is True

    async def test_no_reassignment_when_no_candidates(self, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        account = await _create_account(db_session, user, use_for_calendar=True, write_calendar=True)
        await db_session.commit()

        await account.disconnect("calendar", db_session)
        await db_session.commit()
        # No error — just no primary anymore

    async def test_invalid_purpose_raises(self, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        account = await _create_account(db_session, user, use_for_calendar=True)
        await db_session.commit()

        with pytest.raises(ValueError, match="purpose must be"):
            await account.disconnect("invalid", db_session)
