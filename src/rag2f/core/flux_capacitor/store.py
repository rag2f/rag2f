"""Task store interfaces and in-memory implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import UTC, datetime

from rag2f.core.flux_capacitor.task_models import Task


class BaseTaskStore(ABC):
    """Abstract persistence layer for tasks."""

    @abstractmethod
    def create_task(self, task: Task) -> Task:
        """Persist a task and return it."""

    @abstractmethod
    def get_task(self, task_id: str) -> Task | None:
        """Fetch a task by id."""

    @abstractmethod
    def list_children(self, parent_id: str) -> list[Task]:
        """Return tasks that have ``parent_id`` as parent."""

    @abstractmethod
    def mark_done(self, task_id: str) -> None:
        """Mark task as finished successfully."""

    @abstractmethod
    def mark_error(self, task_id: str, error_msg: str) -> None:
        """Mark task as finished with error."""


class InMemoryTaskStore(BaseTaskStore):
    """In-memory task store for tests and local execution."""

    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}
        self._children: dict[str, list[str]] = defaultdict(list)

    def create_task(self, task: Task) -> Task:
        self._tasks[task.id] = task
        if task.parent_id:
            self._children[task.parent_id].append(task.id)
        return task

    def get_task(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    def list_children(self, parent_id: str) -> list[Task]:
        return [self._tasks[child_id] for child_id in self._children.get(parent_id, [])]

    def mark_done(self, task_id: str) -> None:
        task = self._tasks[task_id]
        task.finished_at = datetime.now(UTC)
        task.error = None

    def mark_error(self, task_id: str, error_msg: str) -> None:
        task = self._tasks[task_id]
        task.finished_at = datetime.now(UTC)
        task.error = error_msg
