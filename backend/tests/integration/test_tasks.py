"""Integration tests for task CRUD and custom actions."""

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from underway.auth.jwt import create_access_token
from underway.models.task import Task
from underway.models.user import User

SECRET = "test-secret-key-at-least-32-chars!"


async def _create_user(db_session: AsyncSession, email: str = "tasks@example.com") -> User:
    user = User(app_login=email)
    user.id = uuid.uuid4()
    db_session.add(user)
    await db_session.commit()
    return user


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(user.id, user.app_login, SECRET)
    return {"Authorization": f"Bearer {token}"}


async def _create_task(db_session: AsyncSession, user: User, title: str = "Test task", **kwargs: object) -> Task:
    task = Task(
        user_id=user.id,
        provider="local",
        provider_task_id=str(uuid.uuid4()),
        title=title,
        status=kwargs.get("status", "active"),
        list_type=kwargs.get("list_type", "unprioritized"),
        position=kwargs.get("position", 0),
        content_hash="",
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)
    return task


class TestTaskList:
    async def test_list_returns_users_tasks(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        await _create_task(db_session, user, "My task")
        response = await client.get("/api/tasks", headers=_auth_headers(user))
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "My task"

    async def test_list_scoped_to_user(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user1 = await _create_user(db_session, "user1@example.com")
        user2 = await _create_user(db_session, "user2@example.com")
        await _create_task(db_session, user1, "User1 task")
        await _create_task(db_session, user2, "User2 task")

        response = await client.get("/api/tasks", headers=_auth_headers(user1))
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "User1 task"

    async def test_filter_by_list_type(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        await _create_task(db_session, user, "Prioritized", list_type="prioritized")
        await _create_task(db_session, user, "Unprioritized", list_type="unprioritized")

        response = await client.get("/api/tasks?list_type=prioritized", headers=_auth_headers(user))
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "Prioritized"

    async def test_filter_by_status(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        await _create_task(db_session, user, "Active", status="active")
        await _create_task(db_session, user, "Done", status="completed")

        response = await client.get("/api/tasks?status=completed", headers=_auth_headers(user))
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "Done"


class TestTaskCreate:
    async def test_create_task(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        response = await client.post(
            "/api/tasks",
            json={"title": "New task", "description": "A description", "priority": 2},
            headers=_auth_headers(user),
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "New task"
        assert data["status"] == "active"
        assert data["list_type"] == "unprioritized"
        assert data["provider"] == "local"


class TestTaskRetrieve:
    async def test_get_task_by_id(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        task = await _create_task(db_session, user, "Specific task")
        response = await client.get(f"/api/tasks/{task.id}", headers=_auth_headers(user))
        assert response.status_code == 200
        assert response.json()["title"] == "Specific task"


class TestTaskUpdate:
    async def test_update_task(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        task = await _create_task(db_session, user, "Old title")
        response = await client.put(
            f"/api/tasks/{task.id}",
            json={
                "title": "New title",
                "status": "active",
            },
            headers=_auth_headers(user),
        )
        assert response.status_code == 200
        assert response.json()["title"] == "New title"

    async def test_partial_update(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        task = await _create_task(db_session, user, "Original")
        response = await client.patch(
            f"/api/tasks/{task.id}",
            json={"title": "Patched"},
            headers=_auth_headers(user),
        )
        assert response.status_code == 200
        assert response.json()["title"] == "Patched"


class TestTaskDelete:
    async def test_delete_task(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        task = await _create_task(db_session, user, "Doomed")
        response = await client.delete(f"/api/tasks/{task.id}", headers=_auth_headers(user))
        assert response.status_code == 204

        response = await client.get(f"/api/tasks/{task.id}", headers=_auth_headers(user))
        assert response.status_code == 404


class TestByList:
    async def test_by_list_groups_tasks(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        await _create_task(db_session, user, "P1", list_type="prioritized")
        await _create_task(db_session, user, "U1", list_type="unprioritized")
        await _create_task(db_session, user, "C1", status="completed", list_type="completed")

        response = await client.get("/api/tasks/by-list", headers=_auth_headers(user))
        assert response.status_code == 200
        data = response.json()
        assert len(data["prioritized"]) == 1
        assert len(data["unprioritized"]) == 1
        assert len(data["completed"]) == 1
        assert data["prioritized"][0]["title"] == "P1"


class TestMoveTask:
    async def test_move_task_between_lists(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        task = await _create_task(db_session, user, "Movable")

        response = await client.post(
            "/api/tasks/move",
            json={
                "task_id": str(task.id),
                "destination": "prioritized",
                "position": 1,
            },
            headers=_auth_headers(user),
        )
        assert response.status_code == 200

        # Verify it moved
        response = await client.get(f"/api/tasks/{task.id}", headers=_auth_headers(user))
        assert response.json()["list_type"] == "prioritized"

    async def test_move_to_completed_sets_status(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        task = await _create_task(db_session, user, "Complete me")

        response = await client.post(
            "/api/tasks/move",
            json={"task_id": str(task.id), "destination": "completed"},
            headers=_auth_headers(user),
        )
        assert response.status_code == 200

        response = await client.get(f"/api/tasks/{task.id}", headers=_auth_headers(user))
        assert response.json()["status"] == "completed"

    async def test_move_nonexistent_task_returns_404(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        response = await client.post(
            "/api/tasks/move",
            json={"task_id": str(uuid.uuid4()), "destination": "prioritized"},
            headers=_auth_headers(user),
        )
        assert response.status_code == 404


class TestReorder:
    async def test_reorder_updates_positions(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        t1 = await _create_task(db_session, user, "First", position=0)
        t2 = await _create_task(db_session, user, "Second", position=1)

        response = await client.post(
            "/api/tasks/reorder",
            json={
                "list_type": "unprioritized",
                "order": [
                    {"id": str(t2.id), "position": 0},
                    {"id": str(t1.id), "position": 1},
                ],
            },
            headers=_auth_headers(user),
        )
        assert response.status_code == 200


class TestUpdateStatus:
    async def test_update_status_to_completed(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        task = await _create_task(db_session, user, "Complete me")

        response = await client.post(
            f"/api/tasks/{task.id}/update-status",
            json={"status": "completed"},
            headers=_auth_headers(user),
        )
        assert response.status_code == 200

        response = await client.get(f"/api/tasks/{task.id}", headers=_auth_headers(user))
        data = response.json()
        assert data["status"] == "completed"
        assert data["list_type"] == "completed"

    async def test_update_status_nonexistent_returns_404(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        response = await client.post(
            f"/api/tasks/{uuid.uuid4()}/update-status",
            json={"status": "completed"},
            headers=_auth_headers(user),
        )
        assert response.status_code == 404


class TestSync:
    async def test_sync_returns_ok(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        response = await client.post("/api/tasks/sync", headers=_auth_headers(user))
        assert response.status_code == 200
