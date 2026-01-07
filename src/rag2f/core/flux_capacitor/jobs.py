import asyncio
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


class JobStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"


@dataclass(slots=True)
class PayloadRef:
    """Reference to persisted payload (agents never get raw payload)."""

    repository: str
    id: str
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "repository": self.repository,
            "id": self.id,
            "meta": self.meta,
        }

    @classmethod
    def from_mapping(cls, payload: Optional[Dict[str, Any]]) -> Optional["PayloadRef"]:
        if payload is None:
            return None
        return cls(
            repository=payload.get("repository", ""),
            id=payload.get("id", ""),
            meta=payload.get("meta") or {},
        )


@dataclass(slots=True)
class AsyncJob:
    """Atomic unit of asynchronous execution."""

    job_id: str
    parent_job_id: Optional[str]
    root_input_id: str
    plugin_id: str
    hook: str
    payload_ref: Optional[PayloadRef]
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: JobStatus = JobStatus.PENDING

    def message(self) -> Dict[str, Any]:
        """Return JSON-serializable queue message."""
        return {
            "job_id": self.job_id,
            "parent_job_id": self.parent_job_id,
            "root_input_id": self.root_input_id,
            "plugin_id": self.plugin_id,
            "hook": self.hook,
            "payload_ref": self.payload_ref.to_dict() if self.payload_ref else None,
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class ChildJobRequest:
    """Lightweight definition for a child job to be spawned."""

    hook: str
    plugin_id: str
    payload_ref: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    job_id: Optional[str] = None


@dataclass(slots=True)
class AgentHookResult:
    """Standardized return type for hook handlers."""

    children: List[ChildJobRequest] = field(default_factory=list)


@dataclass(slots=True)
class JobStatusView:
    job_id: str
    status: JobStatus
    children: List["JobStatusView"] = field(default_factory=list)
    progress: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status.value,
            "progress": self.progress,
            "children": [child.to_dict() for child in self.children],
        }


class BaseJobStore(ABC):
    """Storage-agnostic persistence for async jobs and their tree."""

    async def create_job(
        self,
        *,
        plugin_id: str,
        hook: str,
        root_input_id: str,
        payload_ref: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        parent_job_id: Optional[str] = None,
        job_id: Optional[str] = None,
    ) -> AsyncJob:
        job_metadata = {
            "retry": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if metadata:
            job_metadata.update(metadata)

        job = AsyncJob(
            job_id=job_id or str(uuid.uuid4()),
            parent_job_id=parent_job_id,
            root_input_id=root_input_id,
            plugin_id=plugin_id,
            hook=hook,
            payload_ref=PayloadRef.from_mapping(payload_ref),
            metadata=job_metadata,
            status=JobStatus.PENDING,
        )

        await self._persist_job(job)
        return job

    @abstractmethod
    async def _persist_job(self, job: AsyncJob) -> None:
        raise NotImplementedError

    async def attach_children(self, parent_job_id: str, children: Sequence[AsyncJob]) -> None:
        if not children:
            return
        await asyncio.gather(*(self._persist_job(child) for child in children))

    @abstractmethod
    async def get_job(self, job_id: str) -> Optional[AsyncJob]:
        raise NotImplementedError

    @abstractmethod
    async def mark_status(self, job_id: str, status: JobStatus, *, error: Optional[str] = None) -> None:
        raise NotImplementedError

    async def mark_running(self, job_id: str) -> None:
        await self.mark_status(job_id, JobStatus.RUNNING)

    async def mark_done(self, job_id: str) -> None:
        await self.mark_status(job_id, JobStatus.DONE)

    async def mark_failed(self, job_id: str, *, reason: Optional[str] = None) -> None:
        await self.mark_status(job_id, JobStatus.FAILED, error=reason)

    @abstractmethod
    async def get_children_ids(self, job_id: str) -> List[str]:
        raise NotImplementedError

    @abstractmethod
    async def get_root_jobs(self, input_id: str) -> List[str]:
        raise NotImplementedError

    @abstractmethod
    async def get_parent_id(self, job_id: str) -> Optional[str]:
        raise NotImplementedError

    async def get_status_view(self, job_id: str) -> JobStatusView:
        job = await self.get_job(job_id)
        if job is None:
            raise KeyError(f"Job {job_id} not found")

        child_ids = await self.get_children_ids(job_id)
        children_views = [await self.get_status_view(child_id) for child_id in child_ids]
        aggregated_status = self._aggregate_status(job.status, children_views)
        progress = self._calculate_progress(job.status, children_views)
        return JobStatusView(
            job_id=job.job_id,
            status=aggregated_status,
            children=children_views,
            progress=progress,
        )

    def _aggregate_status(self, own_status: JobStatus, children: Sequence[JobStatusView]) -> JobStatus:
        if any(child.status is JobStatus.FAILED for child in children):
            return JobStatus.FAILED

        if any(child.status in (JobStatus.RUNNING, JobStatus.PENDING) for child in children):
            return JobStatus.RUNNING

        if own_status is JobStatus.FAILED:
            return JobStatus.FAILED

        if own_status is not JobStatus.DONE:
            return own_status

        if children and any(child.status is not JobStatus.DONE for child in children):
            return JobStatus.RUNNING

        return JobStatus.DONE

    def _calculate_progress(self, own_status: JobStatus, children: Sequence[JobStatusView]) -> float:
        leaves_done, leaves_total = self._count_leaves(own_status, children)
        if leaves_total == 0:
            return 1.0 if own_status is JobStatus.DONE else 0.0
        return round(leaves_done / leaves_total, 4)

    def _count_leaves(
        self,
        own_status: JobStatus,
        children: Sequence[JobStatusView],
    ) -> Tuple[int, int]:
        if not children:
            done = 1 if own_status is JobStatus.DONE else 0
            return done, 1

        done = 0
        total = 0
        for child in children:
            child_done, child_total = self._count_leaves(child.status, child.children)
            done += child_done
            total += child_total
        return done, total


class BaseQueue(ABC):
    """Storage-agnostic message queue (Operator)."""

    @abstractmethod
    async def enqueue(self, job: AsyncJob) -> None:
        raise NotImplementedError

    async def enqueue_many(self, jobs: Iterable[AsyncJob]) -> None:
        tasks = [self.enqueue(job) for job in jobs]
        if tasks:
            await asyncio.gather(*tasks)

    @abstractmethod
    async def dequeue(self, plugin_id: str, *, timeout: int = 0) -> Optional[Dict[str, Any]]:
        raise NotImplementedError
