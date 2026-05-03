"""FluxCapacitor - minimal task execution engine for RAG2F.

A task maps to exactly one hook. Hooks can emit child tasks via TaskContext.
"""

from __future__ import annotations

import inspect
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from rag2f.core.flux_capacitor.errors import (
    HookResolutionError,
    MissingQueueError,
    MissingStoreError,
    TaskRegistrationError,
    TaskResolutionError,
)
from rag2f.core.flux_capacitor.queue import BaseTaskQueue
from rag2f.core.flux_capacitor.store import BaseTaskStore
from rag2f.core.flux_capacitor.task_models import (
    PayloadRef,
    Task,
    TaskChildRequest,
    TaskContext,
    TaskEnvelope,
    TaskStatusView,
)
from rag2f.core.observability import (
    debug_event,
    error_event,
    exception_event,
    observation_scope,
    warning_event,
)

logger = logging.getLogger(__name__)


RAG2F_TASK_STORE_DEFAULT_KEY = "task_store_default"
RAG2F_TASK_QUEUE_DEFAULT_KEY = "task_queue_default"
RAG2F_TASK_DEFAULT_HOOK_KEY = "task_default_hook"


@dataclass(slots=True)
class FluxCapacitorConfig:
    """Configuration values read from Spock."""

    default_hook: str | None = None

    @classmethod
    def from_spock(cls, spock: Any | None) -> FluxCapacitorConfig:
        if spock is None:
            return cls()
        default_hook = spock.get_rag2f_config(RAG2F_TASK_DEFAULT_HOOK_KEY)
        if isinstance(default_hook, str):
            default_hook = default_hook.strip() or None
        return cls(default_hook=default_hook)


class FluxCapacitor:
    """Task manager that executes hooks in a deterministic, one-hook-per-task model."""

    def __init__(
        self,
        *,
        rag2f_instance: Any,
        payload_loader: Any | None = None,
    ) -> None:
        self._rag2f = rag2f_instance
        self._spock = rag2f_instance.spock
        self._morpheus = rag2f_instance.morpheus
        self._payload_loader = payload_loader
        self._stores: dict[str, BaseTaskStore] = {}
        self._queues: dict[str, BaseTaskQueue] = {}
        self._config = FluxCapacitorConfig.from_spock(self._spock)
        debug_event(
            logger,
            "flux_capacitor_initialized",
            has_payload_loader=self._payload_loader is not None,
        )

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_store(self, name: str, store: BaseTaskStore) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Store name must be a non-empty string")
        if not isinstance(store, BaseTaskStore):
            raise TaskRegistrationError(
                "Store does not implement BaseTaskStore",
                context={"store_name": name, "type": type(store).__name__},
            )
        if name in self._stores:
            if self._stores[name] is store:
                warning_event(logger, "flux_store_register_duplicate", store_name=name)
                return
            raise TaskRegistrationError(
                f"Override not allowed for already registered store: {name!r}",
                context={"store_name": name},
            )
        self._stores[name] = store
        debug_event(logger, "flux_store_registered", store_name=name)

    def unregister_store(self, name: str) -> bool:
        if name in self._stores:
            del self._stores[name]
            debug_event(logger, "flux_store_unregistered", store_name=name)
            return True
        return False

    def register_queue(self, name: str, queue: BaseTaskQueue) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Queue name must be a non-empty string")
        if not isinstance(queue, BaseTaskQueue):
            raise TaskRegistrationError(
                "Queue does not implement BaseTaskQueue",
                context={"queue_name": name, "type": type(queue).__name__},
            )
        if name in self._queues:
            if self._queues[name] is queue:
                warning_event(logger, "flux_queue_register_duplicate", queue_name=name)
                return
            raise TaskRegistrationError(
                f"Override not allowed for already registered queue: {name!r}",
                context={"queue_name": name},
            )
        self._queues[name] = queue
        debug_event(logger, "flux_queue_registered", queue_name=name)

    def unregister_queue(self, name: str) -> bool:
        if name in self._queues:
            del self._queues[name]
            debug_event(logger, "flux_queue_unregistered", queue_name=name)
            return True
        return False

    def get_store(self, name: str | None = None) -> BaseTaskStore:
        store_name = name or self._resolve_default_store_name()
        if not store_name or store_name not in self._stores:
            raise MissingStoreError(
                "No task store configured",
                context={"store_name": store_name},
            )
        return self._stores[store_name]

    def get_queue(self, name: str | None = None) -> BaseTaskQueue:
        queue_name = name or self._resolve_default_queue_name()
        if not queue_name or queue_name not in self._queues:
            raise MissingQueueError(
                "No task queue configured",
                context={"queue_name": queue_name},
            )
        return self._queues[queue_name]

    def _resolve_default_store_name(self) -> str | None:
        configured = self._resolve_config_key(RAG2F_TASK_STORE_DEFAULT_KEY)
        if configured:
            return configured
        if len(self._stores) == 1:
            return next(iter(self._stores.keys()))
        return None

    def _resolve_default_queue_name(self) -> str | None:
        configured = self._resolve_config_key(RAG2F_TASK_QUEUE_DEFAULT_KEY)
        if configured:
            return configured
        if len(self._queues) == 1:
            return next(iter(self._queues.keys()))
        return None

    def _resolve_config_key(self, key: str) -> str | None:
        if self._spock is None:
            return None

        value = self._spock.get_rag2f_config(key)
        if isinstance(value, str):
            value = value.strip()
        return value or None

    # ------------------------------------------------------------------
    # Task operations
    # ------------------------------------------------------------------

    def enqueue(
        self,
        *,
        plugin_id: str,
        hook: str | None = None,
        payload_ref: dict[str, Any] | PayloadRef | None,
        parent_id: str | None = None,
    ) -> str:
        store = self.get_store()
        task_id = str(uuid.uuid4())
        resolved_hook = self._resolve_task_hook(plugin_id=plugin_id, hook=hook)
        normalized_payload = self._normalize_payload(payload_ref)
        root_id = self._resolve_root_id(parent_id=parent_id, task_id=task_id)
        task = Task(
            id=task_id,
            plugin_id=plugin_id,
            hook=resolved_hook,
            payload_ref=normalized_payload,
            parent_id=parent_id,
            root_id=root_id,
        )
        store.create_task(task)
        self._publish_task(task)
        with observation_scope(
            correlation_id=root_id,
            task_id=task_id,
            root_id=root_id,
            plugin_id=plugin_id,
            hook_name=resolved_hook,
        ):
            debug_event(
                logger,
                "flux_task_enqueued",
                has_parent=parent_id is not None,
                payload_kind=type(normalized_payload).__name__,
            )
        return task.id

    def reserve(self, *, worker_id: str) -> TaskEnvelope | None:
        queue = self.get_queue()
        store = self.get_store()
        envelope = queue.reserve(worker_id=worker_id)
        if envelope is None:
            return None

        task = store.get_task(envelope.task_id)
        if task is None:
            error_event(logger, "flux_task_missing_after_reserve", task_id=envelope.task_id)
            if envelope.reservation_ref:
                queue.ack(envelope.reservation_ref)
            return None

        store.mark_reserved(
            task.id,
            worker_id=worker_id,
            reservation_ref=envelope.reservation_ref,
        )
        refreshed_task = store.get_task(task.id)
        if refreshed_task is None:
            return envelope
        return refreshed_task.to_envelope()

    def complete(self, task_id: str, *, reservation_ref: str | None = None) -> None:
        store = self.get_store()
        queue = self.get_queue()
        task = store.get_task(task_id)
        effective_reservation_ref = reservation_ref or (task.reservation_ref if task else None)
        store.mark_completed(task_id)
        if effective_reservation_ref:
            queue.ack(effective_reservation_ref)
        debug_event(logger, "flux_task_completed", task_id=task_id)

    def fail(
        self,
        task_id: str,
        *,
        error_msg: str,
        reservation_ref: str | None = None,
    ) -> None:
        store = self.get_store()
        queue = self.get_queue()
        task = store.get_task(task_id)
        effective_reservation_ref = reservation_ref or (task.reservation_ref if task else None)
        store.mark_failed(task_id, error_msg=error_msg)
        if effective_reservation_ref:
            queue.ack(effective_reservation_ref)
        debug_event(logger, "flux_task_failed", task_id=task_id)

    def retry(
        self,
        task_id: str,
        *,
        error_msg: str,
        retry_at: datetime | None = None,
        reservation_ref: str | None = None,
    ) -> None:
        store = self.get_store()
        queue = self.get_queue()
        task = store.get_task(task_id)
        if task is None:
            raise TaskResolutionError(
                f"Unknown task: {task_id}",
                context={"task_id": task_id},
            )

        effective_reservation_ref = reservation_ref or task.reservation_ref
        store.mark_retry(task_id, error_msg=error_msg)
        if effective_reservation_ref:
            queue.release(effective_reservation_ref, retry_at=retry_at)
            return

        refreshed_task = store.get_task(task_id)
        if refreshed_task is not None:
            self._publish_task(refreshed_task, available_at=retry_at)

    def get_status(self, task_id: str, *, include_descendants: bool = False) -> TaskStatusView:
        store = self.get_store()
        return store.get_status(task_id, include_descendants=include_descendants)

    def find_recoverable_tasks(self) -> list[Task]:
        """Return unfinished tasks that are neither queued nor reserved."""
        store = self.get_store()
        queue = self.get_queue()
        pending_ids = queue.pending_task_ids()
        reserved_ids = queue.reserved_task_ids()
        return [
            task
            for task in store.list_unfinished_tasks()
            if task.id not in pending_ids
            and task.id not in reserved_ids
            and task.reservation_ref is None
        ]

    def run_once(self, *, worker_id: str = "flux-worker") -> bool:
        store = self.get_store()
        envelope = self.reserve(worker_id=worker_id)
        if envelope is None:
            return False

        task = store.get_task(envelope.task_id)
        if task is None:
            error_event(logger, "flux_task_missing_after_mark_reserved", task_id=envelope.task_id)
            return False

        with observation_scope(
            correlation_id=task.root_id,
            task_id=task.id,
            root_id=task.root_id,
            plugin_id=task.plugin_id,
            hook_name=task.hook,
            worker_id=worker_id,
        ):
            hook = self._morpheus.resolve_hook(task.plugin_id, task.hook)
            if hook is None:
                self.fail(
                    task.id, error_msg="Hook not found", reservation_ref=envelope.reservation_ref
                )
                error_event(logger, "flux_hook_missing")
                return True

            context = TaskContext(
                task=task, rag2f=self._rag2f, payload_loader=self._payload_loader
            )
            debug_event(logger, "flux_task_execution_start")

            try:
                self._invoke_hook(hook.function, task, context)
                children = self._collect_children(task, context)
                for child in children:
                    self.enqueue(
                        plugin_id=child.plugin_id or task.plugin_id,
                        hook=child.hook,
                        payload_ref=child.payload_ref,
                        parent_id=task.id,
                    )
                self.complete(task.id, reservation_ref=envelope.reservation_ref)
                debug_event(logger, "flux_task_execution_complete", child_count=len(children))
            except Exception as exc:
                exception_event(
                    logger,
                    "flux_task_execution_failed",
                    error_type=type(exc).__name__,
                )
                self.fail(task.id, error_msg=str(exc), reservation_ref=envelope.reservation_ref)
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
        status = self.get_status(root_task_id, include_descendants=True)
        return status.exists and status.tree_completed

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

    def _normalize_payload(
        self, payload_ref: dict[str, Any] | PayloadRef | None
    ) -> PayloadRef | dict[str, Any] | None:
        if isinstance(payload_ref, dict):
            return PayloadRef.from_mapping(payload_ref)
        return payload_ref

    def _resolve_root_id(self, *, parent_id: str | None, task_id: str) -> str:
        if parent_id is None:
            return task_id
        parent = self.get_store().get_task(parent_id)
        if parent is None:
            raise TaskResolutionError(
                f"Parent task '{parent_id}' not found",
                context={"parent_id": parent_id, "task_id": task_id},
            )
        return parent.root_id or parent.id

    def _resolve_task_hook(self, *, plugin_id: str, hook: str | None) -> str:
        resolved_hook = hook or self._config.default_hook or "task_default"
        if self._morpheus.resolve_hook(plugin_id, resolved_hook) is None:
            raise HookResolutionError(
                f"Hook '{resolved_hook}' not found for plugin '{plugin_id}'",
                context={"plugin_id": plugin_id, "hook_name": resolved_hook},
            )
        return resolved_hook

    def _publish_task(self, task: Task, *, available_at: datetime | None = None) -> None:
        queue = self.get_queue()
        envelope = task.to_envelope()
        envelope.available_at = available_at
        queue_ref = queue.publish(envelope)
        if queue_ref is not None:
            stored_task = self.get_store().get_task(task.id)
            if stored_task is not None:
                stored_task.queue_ref = queue_ref


TaskManager = FluxCapacitor
