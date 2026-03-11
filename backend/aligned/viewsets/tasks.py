"""Task viewset — CRUD + custom actions for task management."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from fastrest.decorators import action
from fastrest.viewsets import ModelViewSet

if TYPE_CHECKING:
    from fastrest.request import Request
from sqlalchemy import select, update

from aligned.models.task import Task
from aligned.serializers.task import (
    TaskMoveSerializer,
    TaskOrderSerializer,
    TaskSerializer,
)
from aligned.viewsets.base import SessionMixin


class TaskViewSet(SessionMixin, ModelViewSet):
    queryset = Task
    serializer_class = TaskSerializer
    lookup_field_type = str

    async def get_queryset(self) -> list[Task]:
        """Scope to current user. Supports ?list_type= and ?status= filters."""
        user = self.request.user
        session = self._session
        stmt = select(Task).where(Task.user_id == user.id)

        list_type = self.request.query_params.get("list_type")
        if list_type:
            stmt = stmt.where(Task.list_type == list_type)

        status = self.request.query_params.get("status")
        if status:
            stmt = stmt.where(Task.status == status)

        result = await session.execute(stmt.order_by(Task.position))
        return list(result.scalars().all())

    async def perform_create(self, serializer: TaskSerializer) -> None:
        """Set user_id and defaults when creating a task."""
        user = self.request.user
        session = self._session
        data = dict(serializer.validated_data)
        data.pop("status", None)
        data.pop("list_type", None)
        task = Task(
            user_id=user.id,
            provider="local",
            provider_task_id=str(uuid.uuid4()),
            status="active",
            list_type="unprioritized",
            position=0,
            content_hash="",
            **data,
        )
        session.add(task)
        await session.flush()
        serializer.instance = task

    @action(methods=["get"], detail=False, url_path="by-list")
    async def by_list(self, request: Request, **kwargs: str) -> dict[str, list[dict[str, object]]]:
        """GET /api/tasks/by-list — returns tasks grouped by list type."""
        user = request.user
        session = self._session
        prioritized, unprioritized, completed = await Task.get_user_tasks_by_list(session, user.id)
        serializer_class = self.get_serializer_class()
        return {
            "prioritized": serializer_class(prioritized, many=True).data,
            "unprioritized": serializer_class(unprioritized, many=True).data,
            "completed": serializer_class(completed, many=True).data,
        }

    @action(methods=["post"], detail=False, url_path="move")
    async def move_task(self, request: Request, **kwargs: str) -> dict[str, str]:
        """POST /api/tasks/move — move task between lists."""
        serializer = TaskMoveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = request.user
        session = self._session

        result = await session.execute(select(Task).where(Task.id == data["task_id"], Task.user_id == user.id))
        task = result.scalar_one_or_none()
        if task is None:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Task not found.")

        destination = data["destination"]
        task.list_type = destination
        task.position = data.get("position", 0)

        if destination == "completed":
            task.status = "completed"
        elif task.status == "completed":
            task.status = "active"

        await session.flush()
        return {"status": "ok"}

    @action(methods=["post"], detail=False, url_path="reorder")
    async def reorder(self, request: Request, **kwargs: str) -> dict[str, str]:
        """POST /api/tasks/reorder — update positions within a list."""
        serializer = TaskOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = request.user
        session = self._session

        for item in data["order"]:
            task_id = item.get("id")
            position = item.get("position")
            if task_id is None or position is None:
                continue
            await session.execute(
                update(Task)
                .where(Task.id == uuid.UUID(str(task_id)), Task.user_id == user.id)
                .values(position=position)
            )

        await session.flush()
        return {"status": "ok"}

    @action(methods=["post"], detail=False, url_path="sync")
    async def sync(self, request: Request, **kwargs: str) -> dict[str, str]:
        """POST /api/tasks/sync — trigger sync from all providers."""
        # Provider sync will be implemented in step 2.3/2.6
        return {"status": "ok", "message": "Sync not yet implemented."}

    @action(methods=["post"], detail=True, url_path="update-status")
    async def update_status(self, request: Request, pk: str = "", **kwargs: str) -> dict[str, str]:
        """POST /api/tasks/{pk}/update-status — update status + sync to provider."""
        user = request.user
        session = self._session

        result = await session.execute(select(Task).where(Task.id == uuid.UUID(pk), Task.user_id == user.id))
        task = result.scalar_one_or_none()
        if task is None:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Task not found.")

        new_status = request.data.get("status")
        if not new_status:
            return {"status": "ok"}

        task.status = new_status
        if new_status == "completed":
            task.list_type = "completed"
        elif task.list_type == "completed":
            task.list_type = "unprioritized"

        await session.flush()
        return {"status": "ok"}
