"""Task models for the FluxCapacitor subsystem."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


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
class Task:
    """Minimal task record stored by the FluxCapacitor."""

    id: str
    plugin_id: str
    hook: str
    payload_ref: PayloadRef | dict[str, Any] | None
    parent_id: str | None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    error: str | None = None

    @property
    def done(self) -> bool:
        return self.finished_at is not None and self.error is None

    def payload_mapping(self) -> dict[str, Any] | None:
        if self.payload_ref is None:
            return None
        if isinstance(self.payload_ref, PayloadRef):
            return self.payload_ref.to_dict()
        if isinstance(self.payload_ref, dict):
            return self.payload_ref
        return None


@dataclass(slots=True)
class TaskChildRequest:
    """Request emitted by a hook to spawn a child task."""

    hook: str
    plugin_id: str | None = None
    payload_ref: dict[str, Any] | None = None


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
