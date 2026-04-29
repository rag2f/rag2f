"""Task queue interfaces and in-memory implementation."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

from rag2f.core.flux_capacitor.task_models import (
    TaskBackendCapabilities,
    TaskEnvelope,
)


@dataclass(slots=True)
class _QueuedTask:
    """Internal queue entry for in-memory delivery."""

    envelope: TaskEnvelope


@dataclass(slots=True)
class _Reservation:
    """Internal reservation metadata for in-memory delivery."""

    envelope: TaskEnvelope
    worker_id: str
    reserved_at: datetime
    expires_at: datetime | None


class BaseTaskQueue(ABC):
    """Abstract queue interface for task envelopes."""

    @property
    def capabilities(self) -> TaskBackendCapabilities:
        """Return the capabilities declared by the backend."""
        return TaskBackendCapabilities()

    @abstractmethod
    def publish(self, envelope: TaskEnvelope) -> str | None:
        """Publish a task envelope and optionally return a queue reference."""

    def publish_many(self, envelopes: Iterable[TaskEnvelope]) -> None:
        for envelope in envelopes:
            self.publish(envelope)

    @abstractmethod
    def reserve(self, *, worker_id: str) -> TaskEnvelope | None:
        """Reserve the next available envelope for execution."""

    @abstractmethod
    def ack(self, reservation_ref: str) -> None:
        """Acknowledge successful processing of a reservation."""

    @abstractmethod
    def release(self, reservation_ref: str, *, retry_at: datetime | None = None) -> None:
        """Release a reservation back to the queue."""

    def reclaim_expired(self, *, now: datetime | None = None) -> list[TaskEnvelope]:
        """Requeue expired reservations and return the reclaimed envelopes."""
        return []

    def pending_task_ids(self) -> set[str]:
        """Return pending task ids if supported by the backend."""
        return set()

    def reserved_task_ids(self) -> set[str]:
        """Return currently reserved task ids if supported by the backend."""
        return set()

    def push(self, task_id: str) -> None:
        """Backward-compatible helper used only by legacy code paths."""
        self.publish(
            TaskEnvelope(
                task_id=task_id,
                root_id=task_id,
                parent_id=None,
                plugin_id="",
                hook="",
            )
        )

    def push_many(self, task_ids: Iterable[str]) -> None:
        for task_id in task_ids:
            self.push(task_id)

    def pop(self) -> str | None:
        """Backward-compatible helper used only by legacy code paths."""
        envelope = self.reserve(worker_id="legacy-pop")
        if envelope is None:
            return None
        self.ack(envelope.reservation_ref or "")
        return envelope.task_id


class InMemoryTaskQueue(BaseTaskQueue):
    """Simple FIFO queue stored in memory."""

    def __init__(self, *, visibility_timeout: timedelta | None = timedelta(minutes=5)) -> None:
        if visibility_timeout is not None and visibility_timeout < timedelta(0):
            raise ValueError("visibility_timeout must be non-negative")
        self._queue: deque[_QueuedTask] = deque()
        self._reservations: dict[str, _Reservation] = {}
        self._visibility_timeout = visibility_timeout

    @property
    def capabilities(self) -> TaskBackendCapabilities:
        return TaskBackendCapabilities(
            supports_ack=True,
            supports_delay=True,
            supports_reclaim=self._visibility_timeout is not None,
            supports_ordering=True,
            supports_visibility_timeout=self._visibility_timeout is not None,
        )

    def publish(self, envelope: TaskEnvelope) -> str | None:
        queue_ref = envelope.queue_ref or str(uuid.uuid4())
        queued_envelope = replace(
            envelope,
            queue_ref=queue_ref,
            reservation_ref=None,
            available_at=_normalize_datetime(envelope.available_at) or datetime.now(UTC),
        )
        self._queue.append(_QueuedTask(envelope=queued_envelope))
        return queue_ref

    def reserve(self, *, worker_id: str) -> TaskEnvelope | None:
        now = datetime.now(UTC)
        self.reclaim_expired(now=now)
        for _ in range(len(self._queue)):
            queued_task = self._queue.popleft()
            available_at = queued_task.envelope.available_at or now
            if available_at <= now:
                reservation_ref = str(uuid.uuid4())
                reserved = replace(
                    queued_task.envelope,
                    reservation_ref=reservation_ref,
                    available_at=None,
                )
                self._reservations[reservation_ref] = _Reservation(
                    envelope=reserved,
                    worker_id=worker_id,
                    reserved_at=now,
                    expires_at=self._reservation_expires_at(now),
                )
                return reserved
            self._queue.append(queued_task)
        return None

    def ack(self, reservation_ref: str) -> None:
        if reservation_ref:
            self._reservations.pop(reservation_ref, None)

    def release(self, reservation_ref: str, *, retry_at: datetime | None = None) -> None:
        reserved = self._reservations.pop(reservation_ref, None)
        if reserved is None:
            return
        released = replace(
            reserved.envelope,
            reservation_ref=None,
            available_at=_normalize_datetime(retry_at) or datetime.now(UTC),
        )
        self._queue.append(_QueuedTask(envelope=released))

    def reclaim_expired(self, *, now: datetime | None = None) -> list[TaskEnvelope]:
        if self._visibility_timeout is None:
            return []

        effective_now = _normalize_datetime(now) or datetime.now(UTC)
        expired_refs = [
            reservation_ref
            for reservation_ref, reservation in self._reservations.items()
            if reservation.expires_at is not None and reservation.expires_at <= effective_now
        ]
        reclaimed: list[TaskEnvelope] = []
        for reservation_ref in expired_refs:
            reservation = self._reservations.pop(reservation_ref)
            envelope = replace(
                reservation.envelope,
                reservation_ref=None,
                available_at=None,
            )
            self._queue.append(_QueuedTask(envelope=envelope))
            reclaimed.append(envelope)
        return reclaimed

    def pending_task_ids(self) -> set[str]:
        self.reclaim_expired()
        return {queued_task.envelope.task_id for queued_task in self._queue}

    def reserved_task_ids(self) -> set[str]:
        self.reclaim_expired()
        return {reservation.envelope.task_id for reservation in self._reservations.values()}

    def _reservation_expires_at(self, reserved_at: datetime) -> datetime | None:
        if self._visibility_timeout is None:
            return None
        return reserved_at + self._visibility_timeout


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
