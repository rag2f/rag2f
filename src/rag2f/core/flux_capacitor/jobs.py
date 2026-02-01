"""Async job execution primitives and storage abstractions."""

from __future__ import annotations

import asyncio
import uuid
from abc import ABC, abstractmethod
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Optional


class JobStatus(StrEnum):
    """Lifecycle states for async jobs."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"


@dataclass(slots=True)
class PayloadRef:
    """Reference to stored payload data."""

    repository: str
    id: str
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"repository": self.repository, "id": self.id, "meta": dict(self.meta)}

    @classmethod
    def from_mapping(cls, payload: Optional[dict[str, Any]]) -> Optional["PayloadRef"]:
        if not payload:
            return None
        return cls(
            repository=payload.get("repository", ""),
            id=payload.get("id", ""),
            meta=payload.get("meta", {}) or {},
        )


@dataclass(slots=True)
class AsyncJob:
    """Model representing a queued async job."""

    job_id: str
    parent_job_id: Optional[str]
    root_input_id: str
    plugin_id: str
    hook: str
    payload_ref: Optional[PayloadRef]
    metadata: dict[str, Any] = field(default_factory=dict)
    status: JobStatus = JobStatus.PENDING

    def message(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "parent_job_id": self.parent_job_id,
            "root_input_id": self.root_input_id,
            "plugin_id": self.plugin_id,
            "hook": self.hook,
            "payload_ref": self.payload_ref.to_dict() if self.payload_ref else None,
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class ChildJobRequest:
    """Request to enqueue a child job."""

    hook: str
    plugin_id: str
    payload_ref: Optional[dict[str, Any]] = None
    metadata: Optional[dict[str, Any]] = None
    job_id: Optional[str] = None


@dataclass(slots=True)
class AgentHookResult:
    """Wrapper for returning child job requests from a hook."""

    children: list[ChildJobRequest] = field(default_factory=list)


@dataclass(slots=True)
class JobStatusView:
    """Tree view of job status and progress."""

    job_id: str
    status: JobStatus
    children: list["JobStatusView"] = field(default_factory=list)
    progress: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status.value,
            "progress": self.progress,
            "children": [child.to_dict() for child in self.children],
        }


class BaseJobStore(ABC):
    """Abstract job persistence layer."""

    async def create_job(
        self,
        *,
        plugin_id: str,
        hook: str,
        root_input_id: str,
        payload_ref: Optional[PayloadRef | dict[str, Any]] = None,
        metadata: Optional[dict[str, Any]] = None,
        parent_job_id: Optional[str] = None,
        job_id: Optional[str] = None,
    ) -> AsyncJob:
        base_metadata = {
            "retry": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if metadata:
            base_metadata.update(metadata)

        payload_obj: Optional[PayloadRef]
        if isinstance(payload_ref, dict):
            payload_obj = PayloadRef.from_mapping(payload_ref)
        else:
            payload_obj = payload_ref

        job = AsyncJob(
            job_id=job_id or str(uuid.uuid4()),
            parent_job_id=parent_job_id,
            root_input_id=root_input_id,
            plugin_id=plugin_id,
            hook=hook,
            payload_ref=payload_obj,
            metadata=base_metadata,
            status=JobStatus.PENDING,
        )
        await self._persist_job(job)
        return job

    @abstractmethod
    async def _persist_job(self, job: AsyncJob) -> None:
        """Persist a job in storage."""

    async def attach_children(self, parent_job_id: str, children: Sequence[AsyncJob]) -> None:
        await asyncio.gather(*(self._persist_job(child) for child in children))

    @abstractmethod
    async def get_job(self, job_id: str) -> Optional[AsyncJob]:
        """Fetch a job by id."""

    @abstractmethod
    async def mark_status(
        self, job_id: str, status: JobStatus, *, error: Optional[str] = None
    ) -> None:
        """Mark a job with a specific status."""

    async def mark_running(self, job_id: str) -> None:
        await self.mark_status(job_id, JobStatus.RUNNING)

    async def mark_done(self, job_id: str) -> None:
        await self.mark_status(job_id, JobStatus.DONE)

    async def mark_failed(self, job_id: str, reason: Optional[str] = None) -> None:
        await self.mark_status(job_id, JobStatus.FAILED, error=reason)

    @abstractmethod
    async def get_children_ids(self, job_id: str) -> list[str]:
        """Return child job ids for a job."""

    @abstractmethod
    async def get_root_jobs(self, input_id: str) -> list[str]:
        """Return root job ids for a given input id."""

    @abstractmethod
    async def get_parent_id(self, job_id: str) -> Optional[str]:
        """Return the parent job id for a job."""

    async def get_status_view(self, job_id: str) -> JobStatusView:
        async def _build_view(job_id: str) -> tuple[JobStatusView, int, int]:
            job = await self.get_job(job_id)
            if job is None:
                raise KeyError(f"Job not found: {job_id}")

            child_ids = await self.get_children_ids(job_id)
            children_views: list[JobStatusView] = []
            leaves_total = 0
            leaves_done = 0

            for child_id in child_ids:
                child_view, child_total, child_done = await _build_view(child_id)
                children_views.append(child_view)
                leaves_total += child_total
                leaves_done += child_done

            if not child_ids:
                leaves_total = 1
                leaves_done = 1 if job.status == JobStatus.DONE else 0

            aggregated = self._aggregate_status(job.status, children_views)

            if leaves_total == 0:
                progress = 1.0 if job.status == JobStatus.DONE else 0.0
            else:
                progress = round(leaves_done / leaves_total, 4)

            view = JobStatusView(
                job_id=job.job_id,
                status=aggregated,
                children=children_views,
                progress=progress,
            )
            return view, leaves_total, leaves_done

        view, _, _ = await _build_view(job_id)
        return view

    @staticmethod
    def _aggregate_status(status: JobStatus, children: Sequence[JobStatusView]) -> JobStatus:
        child_statuses = [child.status for child in children]
        if any(child_status == JobStatus.FAILED for child_status in child_statuses):
            return JobStatus.FAILED
        if any(
            child_status in (JobStatus.RUNNING, JobStatus.PENDING)
            for child_status in child_statuses
        ):
            return JobStatus.RUNNING
        if status == JobStatus.FAILED:
            return JobStatus.FAILED
        if status != JobStatus.DONE:
            return status
        if status == JobStatus.DONE and any(
            child_status != JobStatus.DONE for child_status in child_statuses
        ):
            return JobStatus.RUNNING
        return JobStatus.DONE


class BaseQueue(ABC):
    """Abstract queue interface for async jobs."""

    @abstractmethod
    async def enqueue(self, job: AsyncJob) -> None:
        """Enqueue a job for processing."""

    async def enqueue_many(self, jobs: Iterable[AsyncJob]) -> None:
        await asyncio.gather(*(self.enqueue(job) for job in jobs))

    @abstractmethod
    async def dequeue(self, plugin_id: str, *, timeout: int = 0) -> Optional[dict[str, Any]]:
        """Dequeue a job message for a plugin."""
