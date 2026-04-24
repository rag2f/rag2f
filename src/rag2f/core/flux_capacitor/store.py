"""Task store interfaces and in-memory implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import UTC, datetime

from rag2f.core.flux_capacitor.task_models import Task, TaskStatusView


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
    def list_unfinished_tasks(self) -> list[Task]:
        """Return tasks that are not in a terminal state."""

    @abstractmethod
    def mark_reserved(self, task_id: str, *, worker_id: str, reservation_ref: str | None) -> None:
        """Mark a task as reserved for execution."""

    @abstractmethod
    def mark_completed(self, task_id: str) -> None:
        """Mark task as finished successfully."""

    @abstractmethod
    def mark_failed(self, task_id: str, *, error_msg: str) -> None:
        """Mark task as finished with error."""

    @abstractmethod
    def mark_retry(self, task_id: str, *, error_msg: str) -> None:
        """Mark task for retry after a failed execution attempt."""

    @abstractmethod
    def get_status(self, task_id: str, *, include_descendants: bool = False) -> TaskStatusView:
        """Return the status projection for a task."""

    def mark_done(self, task_id: str) -> None:
        """Backward-compatible alias for ``mark_completed``."""
        self.mark_completed(task_id)

    def mark_error(self, task_id: str, error_msg: str) -> None:
        """Backward-compatible alias for ``mark_failed``."""
        self.mark_failed(task_id, error_msg=error_msg)


class InMemoryTaskStore(BaseTaskStore):
    """In-memory task store for tests and local execution."""

    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}
        self._children: dict[str, list[str]] = defaultdict(list)

    def create_task(self, task: Task) -> Task:
        if task.parent_id:
            parent = self._tasks.get(task.parent_id)
            if parent is not None:
                task.root_id = parent.root_id
                self._children[task.parent_id].append(task.id)
        else:
            task.root_id = task.id
        self._tasks[task.id] = task
        return task

    def get_task(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    def list_children(self, parent_id: str) -> list[Task]:
        return [self._tasks[child_id] for child_id in self._children.get(parent_id, [])]

    def list_unfinished_tasks(self) -> list[Task]:
        return [
            task for task in self._tasks.values() if task.status not in {"completed", "failed"}
        ]

    def mark_reserved(self, task_id: str, *, worker_id: str, reservation_ref: str | None) -> None:
        task = self._tasks[task_id]
        task.status = "reserved"
        task.started_at = datetime.now(UTC)
        task.finished_at = None
        task.worker_id = worker_id
        task.reservation_ref = reservation_ref
        task.last_error = None
        task.attempts += 1

    def mark_completed(self, task_id: str) -> None:
        task = self._tasks[task_id]
        task.status = "completed"
        task.finished_at = datetime.now(UTC)
        task.worker_id = None
        task.reservation_ref = None
        task.last_error = None

    def mark_failed(self, task_id: str, *, error_msg: str) -> None:
        task = self._tasks[task_id]
        task.status = "failed"
        task.finished_at = datetime.now(UTC)
        task.worker_id = None
        task.reservation_ref = None
        task.last_error = error_msg

    def mark_retry(self, task_id: str, *, error_msg: str) -> None:
        task = self._tasks[task_id]
        task.status = "retry_scheduled"
        task.finished_at = None
        task.worker_id = None
        task.reservation_ref = None
        task.last_error = error_msg

    def get_status(self, task_id: str, *, include_descendants: bool = False) -> TaskStatusView:
        task = self._tasks.get(task_id)
        if task is None:
            return TaskStatusView(
                exists=False,
                task_id=task_id,
                root_id=None,
                parent_id=None,
                plugin_id=None,
                hook=None,
                status="missing",
            )

        descendants = self._list_descendants(task.id)
        counts = {
            "pending": 0,
            "reserved": 0,
            "completed": 0,
            "failed": 0,
            "retry_scheduled": 0,
        }
        for descendant in descendants:
            counts[descendant.status] += 1

        return TaskStatusView(
            exists=True,
            task_id=task.id,
            root_id=task.root_id,
            parent_id=task.parent_id,
            plugin_id=task.plugin_id,
            hook=task.hook,
            status=task.status,
            attempts=task.attempts,
            worker_id=task.worker_id,
            last_error=task.last_error,
            has_children=bool(self._children.get(task.id)),
            descendant_count=len(descendants),
            pending_count=counts["pending"],
            reserved_count=counts["reserved"],
            completed_count=counts["completed"],
            failed_count=counts["failed"],
            retry_scheduled_count=counts["retry_scheduled"],
            tree_completed=(
                task.status == "completed"
                and all(descendant.status == "completed" for descendant in descendants)
            ),
            descendants=list(descendants) if include_descendants else [],
        )

    def _list_descendants(self, task_id: str) -> list[Task]:
        descendants: list[Task] = []
        for child_id in self._children.get(task_id, []):
            child = self._tasks[child_id]
            descendants.append(child)
            descendants.extend(self._list_descendants(child.id))
        return descendants
