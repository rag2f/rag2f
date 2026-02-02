"""FluxCapacitor - minimal task execution engine for RAG2F.

A task maps to exactly one hook. Hooks can emit child tasks via TaskContext.
"""

from __future__ import annotations

import inspect
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any

from rag2f.core.flux_capacitor.errors import MissingQueueError, MissingStoreError
from rag2f.core.flux_capacitor.queue import BaseTaskQueue
from rag2f.core.flux_capacitor.store import BaseTaskStore
from rag2f.core.flux_capacitor.task_models import PayloadRef, Task, TaskChildRequest, TaskContext

logger = logging.getLogger(__name__)


RAG2F_TASK_STORE_DEFAULT_KEY = "task_store_default"
RAG2F_TASK_QUEUE_DEFAULT_KEY = "task_queue_default"


@dataclass(slots=True)
class FluxCapacitorConfig:
    """Configuration values read from Spock."""

    default_store: str | None = None
    default_queue: str | None = None

    @classmethod
    def from_spock(cls, spock: Any | None) -> FluxCapacitorConfig:
        if spock is None:
            return cls()
        store = spock.get_rag2f_config(RAG2F_TASK_STORE_DEFAULT_KEY)
        queue = spock.get_rag2f_config(RAG2F_TASK_QUEUE_DEFAULT_KEY)
        if isinstance(store, str):
            store = store.strip() or None
        if isinstance(queue, str):
            queue = queue.strip() or None
        return cls(default_store=store, default_queue=queue)


class FluxCapacitor:
    """Task manager that executes hooks in a deterministic, one-hook-per-task model."""

    def __init__(
        self,
        *,
        rag2f_instance: Any,
        payload_loader: Any | None = None,
    ) -> None:
        self._rag2f = rag2f_instance
        self._spock = rag2f_instance.config_manager
        self._morpheus = rag2f_instance.plugin_manager
        self._payload_loader = payload_loader
        self._stores: dict[str, BaseTaskStore] = {}
        self._queues: dict[str, BaseTaskQueue] = {}
        self._default_store_name: str | None = None
        self._default_queue_name: str | None = None
        self._config = FluxCapacitorConfig.from_spock(self._spock)
        logger.debug("FluxCapacitor instance created.")

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_store(self, name: str, store: BaseTaskStore) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Store name must be a non-empty string")
        if not isinstance(store, BaseTaskStore):
            raise TypeError("Store does not implement BaseTaskStore")
        if name in self._stores:
            if self._stores[name] is store:
                logger.warning(
                    "Store '%s' already registered with the same instance; skipping.", name
                )
                return
            raise ValueError(f"Override not allowed for already registered store: {name!r}")
        self._stores[name] = store
        logger.debug("Task store '%s' registered.", name)

    def unregister_store(self, name: str) -> bool:
        if name in self._stores:
            del self._stores[name]
            if self._default_store_name == name:
                self._default_store_name = None
            logger.debug("Task store '%s' unregistered.", name)
            return True
        return False

    def register_queue(self, name: str, queue: BaseTaskQueue) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Queue name must be a non-empty string")
        if not isinstance(queue, BaseTaskQueue):
            raise TypeError("Queue does not implement BaseTaskQueue")
        if name in self._queues:
            if self._queues[name] is queue:
                logger.warning(
                    "Queue '%s' already registered with the same instance; skipping.", name
                )
                return
            raise ValueError(f"Override not allowed for already registered queue: {name!r}")
        self._queues[name] = queue
        logger.debug("Task queue '%s' registered.", name)

    def unregister_queue(self, name: str) -> bool:
        if name in self._queues:
            del self._queues[name]
            if self._default_queue_name == name:
                self._default_queue_name = None
            logger.debug("Task queue '%s' unregistered.", name)
            return True
        return False

    def set_default_store(self, name: str) -> None:
        if name not in self._stores:
            raise MissingStoreError(f"Store '{name}' not registered")
        self._default_store_name = name

    def set_default_queue(self, name: str) -> None:
        if name not in self._queues:
            raise MissingQueueError(f"Queue '{name}' not registered")
        self._default_queue_name = name

    def get_store(self, name: str | None = None) -> BaseTaskStore:
        store_name = name or self._resolve_default_store_name()
        if not store_name or store_name not in self._stores:
            raise MissingStoreError("No task store configured")
        return self._stores[store_name]

    def get_queue(self, name: str | None = None) -> BaseTaskQueue:
        queue_name = name or self._resolve_default_queue_name()
        if not queue_name or queue_name not in self._queues:
            raise MissingQueueError("No task queue configured")
        return self._queues[queue_name]

    def _resolve_default_store_name(self) -> str | None:
        if self._default_store_name:
            return self._default_store_name
        if self._config.default_store:
            return self._config.default_store
        if len(self._stores) == 1:
            return next(iter(self._stores.keys()))
        return None

    def _resolve_default_queue_name(self) -> str | None:
        if self._default_queue_name:
            return self._default_queue_name
        if self._config.default_queue:
            return self._config.default_queue
        if len(self._queues) == 1:
            return next(iter(self._queues.keys()))
        return None

    # ------------------------------------------------------------------
    # Task operations
    # ------------------------------------------------------------------

    def enqueue(
        self,
        *,
        plugin_id: str,
        hook: str,
        payload_ref: dict[str, Any] | PayloadRef | None,
        parent_id: str | None = None,
    ) -> str:
        store = self.get_store()
        queue = self.get_queue()
        task_id = str(uuid.uuid4())
        normalized_payload = payload_ref
        if isinstance(payload_ref, dict):
            normalized_payload = PayloadRef.from_mapping(payload_ref)
        task = Task(
            id=task_id,
            plugin_id=plugin_id,
            hook=hook,
            payload_ref=normalized_payload,
            parent_id=parent_id,
        )
        store.create_task(task)
        queue.push(task.id)
        return task.id

    def run_once(self) -> bool:
        queue = self.get_queue()
        store = self.get_store()
        task_id = queue.pop()
        if task_id is None:
            return False

        task = store.get_task(task_id)
        if task is None:
            logger.error("Task '%s' missing from store; dropping.", task_id)
            return True

        hook = self._morpheus.resolve_hook(task.plugin_id, task.hook)
        if hook is None:
            store.mark_error(task.id, "Hook not found")
            logger.error("Hook '%s' not found for plugin '%s'", task.hook, task.plugin_id)
            return True

        context = TaskContext(task=task, rag2f=self._rag2f, payload_loader=self._payload_loader)

        try:
            self._invoke_hook(hook.function, task, context)
            children = self._collect_children(task, context)
            for child in children:
                child_task = Task(
                    id=str(uuid.uuid4()),
                    plugin_id=child.plugin_id or task.plugin_id,
                    hook=child.hook,
                    payload_ref=PayloadRef.from_mapping(child.payload_ref),
                    parent_id=task.id,
                )
                store.create_task(child_task)
                queue.push(child_task.id)
            store.mark_done(task.id)
        except Exception as exc:
            logger.exception("Task hook failed: %s", task.id)
            store.mark_error(task.id, str(exc))
        return True

    def worker_loop(
        self, *, max_iterations: int | None = None, sleep_seconds: float = 0.1
    ) -> None:
        iterations = 0
        while True:
            processed = self.run_once()
            if processed:
                iterations += 1
            if max_iterations is not None and iterations >= max_iterations:
                break
            if not processed:
                if sleep_seconds <= 0:
                    break
                time.sleep(sleep_seconds)

    def is_tree_done(self, root_task_id: str) -> bool:
        store = self.get_store()
        root = store.get_task(root_task_id)
        if root is None:
            return False

        def _walk(task: Task) -> bool:
            if task.finished_at is None or task.error is not None:
                return False
            children = store.list_children(task.id)
            return all(_walk(child) for child in children)

        return _walk(root)

    def _invoke_hook(self, handler: Any, task: Task, context: TaskContext) -> None:
        payload_ref = task.payload_mapping()
        available = {
            "task": task,
            "context": context,
            "payload_ref": payload_ref,
            "rag2f": self._rag2f,
        }

        signature = inspect.signature(handler)
        if any(param.kind == param.VAR_KEYWORD for param in signature.parameters.values()):
            call_kwargs = available
        else:
            call_kwargs = {
                name: value for name, value in available.items() if name in signature.parameters
            }
        handler(**call_kwargs)

    def _collect_children(self, task: Task, context: TaskContext) -> list[TaskChildRequest]:
        children = context.staged_children
        normalized: list[TaskChildRequest] = []
        for child in children:
            if child is None:
                continue
            if child.plugin_id is None:
                child.plugin_id = task.plugin_id
            normalized.append(child)
        return normalized


TaskManager = FluxCapacitor
