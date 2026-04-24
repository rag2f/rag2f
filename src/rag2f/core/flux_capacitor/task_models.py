"""Task models for the FluxCapacitor subsystem."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

type TaskLifecycleStatus = Literal[
    "pending",
    "reserved",
    "completed",
    "failed",
    "retry_scheduled",
]


@dataclass(slots=True)
class PayloadRef:
    """Reference to stored payload data."""

    repository: str
    id: str
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"repository": self.repository, "id": self.id, "meta": dict(self.meta)}

    @classmethod
    def from_mapping(cls, payload: dict[str, Any] | None) -> PayloadRef | None:
        if not payload:
            return None
        repository = payload.get("repository") or payload.get("repo") or ""
        return cls(
            repository=repository,
            id=payload.get("id", ""),
            meta=payload.get("meta", {}) or {},
        )


@dataclass(slots=True)
class TaskEnvelope:
    """Queue-facing task payload with enough routing metadata to execute a task."""

    task_id: str
    root_id: str
    parent_id: str | None
    plugin_id: str
    hook: str
    payload_ref: PayloadRef | dict[str, Any] | None = None
    reservation_ref: str | None = None
    queue_ref: str | None = None
    available_at: datetime | None = None


@dataclass(slots=True)
class TaskBackendCapabilities:
    """Capabilities declared by a queue backend."""

    supports_ack: bool = False
    supports_delay: bool = False
    supports_reclaim: bool = False
    supports_ordering: bool = False
    supports_visibility_timeout: bool = False


@dataclass(slots=True)
class Task:
    """Authoritative task record stored by the FluxCapacitor."""

    id: str
    plugin_id: str
    hook: str
    payload_ref: PayloadRef | dict[str, Any] | None
    parent_id: str | None
    root_id: str | None = None
    status: TaskLifecycleStatus = "pending"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    finished_at: datetime | None = None
    attempts: int = 0
    worker_id: str | None = None
    last_error: str | None = None
    queue_ref: str | None = None
    reservation_ref: str | None = None

    def __post_init__(self) -> None:
        if self.root_id is None:
            self.root_id = self.parent_id or self.id

    @property
    def error(self) -> str | None:
        """Backward-compatible alias used by existing tests."""
        return self.last_error

    @error.setter
    def error(self, value: str | None) -> None:
        self.last_error = value

    @property
    def done(self) -> bool:
        return self.status == "completed"

    def payload_mapping(self) -> dict[str, Any] | None:
        if self.payload_ref is None:
            return None
        if isinstance(self.payload_ref, PayloadRef):
            return self.payload_ref.to_dict()
        if isinstance(self.payload_ref, dict):
            return self.payload_ref
        return None

    def to_envelope(self) -> TaskEnvelope:
        """Return the queue-facing envelope for this task."""
        return TaskEnvelope(
            task_id=self.id,
            root_id=self.root_id or self.id,
            parent_id=self.parent_id,
            plugin_id=self.plugin_id,
            hook=self.hook,
            payload_ref=self.payload_ref,
            reservation_ref=self.reservation_ref,
            queue_ref=self.queue_ref,
        )


@dataclass(slots=True)
class TaskChildRequest:
    """Request emitted by a hook to spawn a child task."""

    hook: str
    plugin_id: str | None = None
    payload_ref: dict[str, Any] | None = None


@dataclass(slots=True)
class TaskStatusView:
    """Projection of the current state of a task and, optionally, its descendants."""

    exists: bool
    task_id: str
    root_id: str | None
    parent_id: str | None
    plugin_id: str | None
    hook: str | None
    status: TaskLifecycleStatus | Literal["missing"]
    attempts: int = 0
    worker_id: str | None = None
    last_error: str | None = None
    has_children: bool = False
    descendant_count: int = 0
    pending_count: int = 0
    reserved_count: int = 0
    completed_count: int = 0
    failed_count: int = 0
    retry_scheduled_count: int = 0
    tree_completed: bool = False
    descendants: list[Task] = field(default_factory=list)

    @property
    def has_open_descendants(self) -> bool:
        return (self.pending_count + self.reserved_count + self.retry_scheduled_count) > 0


class TaskContext:
    """Context passed to task hooks.

    Hooks can emit child tasks by calling ``emit_child`` or ``emit_children``.
    """

    def __init__(
        self,
        *,
        task: Task,
        rag2f: Any | None = None,
        payload_loader: Any | None = None,
    ) -> None:
        self.task = task
        self.rag2f = rag2f
        self._payload_loader = payload_loader
        self._children: list[TaskChildRequest] = []

    def emit_child(
        self,
        *args: str,
        plugin_id: str | None = None,
        hook: str | None = None,
        payload_ref: dict[str, Any] | None = None,
    ) -> TaskChildRequest:
        if len(args) == 1:
            if hook is None:
                hook = args[0]
            else:
                plugin_id = args[0]
        elif len(args) == 2:
            plugin_id, hook = args
        elif len(args) > 2:
            raise ValueError("emit_child expects (hook) or (plugin_id, hook)")

        if hook is None:
            raise ValueError("emit_child requires a hook name")
        child = TaskChildRequest(
            hook=hook,
            plugin_id=plugin_id or self.task.plugin_id,
            payload_ref=payload_ref,
        )
        self._children.append(child)
        return child

    def emit_children(self, children: Iterable[TaskChildRequest]) -> None:
        for child in children:
            self._children.append(child)

    @property
    def staged_children(self) -> list[TaskChildRequest]:
        return list(self._children)

    def load_payload(self) -> Any:
        if self._payload_loader is None:
            raise RuntimeError("No payload loader configured")
        return self._payload_loader(self.task.payload_ref)
