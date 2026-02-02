"""Task queue interfaces and in-memory implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from collections.abc import Iterable


class BaseTaskQueue(ABC):
    """Abstract queue interface for task ids."""

    @abstractmethod
    def push(self, task_id: str) -> None:
        """Push a task id into the queue."""

    def push_many(self, task_ids: Iterable[str]) -> None:
        for task_id in task_ids:
            self.push(task_id)

    @abstractmethod
    def pop(self) -> str | None:
        """Pop a task id from the queue, if available."""


class InMemoryTaskQueue(BaseTaskQueue):
    """Simple FIFO queue stored in memory."""

    def __init__(self) -> None:
        self._queue: deque[str] = deque()

    def push(self, task_id: str) -> None:
        self._queue.append(task_id)

    def pop(self) -> str | None:
        if not self._queue:
            return None
        return self._queue.popleft()
