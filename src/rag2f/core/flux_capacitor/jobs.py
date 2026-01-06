import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from redis.asyncio import Redis


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


class RedisKeys:
    """Helper to keep canonical Redis key naming with optional namespace."""

    def __init__(self, namespace: Optional[str] = None):
        self.namespace = namespace.strip() if namespace else None

    def _prefix(self, key: str) -> str:
        return f"{self.namespace}:{key}" if self.namespace else key

    def queue(self, plugin_id: str) -> str:
        return self._prefix(f"queue:{plugin_id}")

    def job(self, job_id: str) -> str:
        return self._prefix(f"job:{job_id}")

    def job_children(self, job_id: str) -> str:
        return self._prefix(f"job_children:{job_id}")

    def job_parent(self, job_id: str) -> str:
        return self._prefix(f"job_parent:{job_id}")

    def input_root(self, input_id: str) -> str:
        return self._prefix(f"input_root:{input_id}")


class RedisJobStore:
    """Redis-backed persistence for async jobs and their tree."""

    def __init__(self, redis: Redis, *, namespace: Optional[str] = None):
        self.redis = redis
        self.keys = RedisKeys(namespace)

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

    async def _persist_job(self, job: AsyncJob) -> None:
        mapping = {
            "job_id": job.job_id,
            "parent_job_id": job.parent_job_id or "",
            "root_input_id": job.root_input_id,
            "plugin_id": job.plugin_id,
            "hook": job.hook,
            "payload_ref": json.dumps(job.payload_ref.to_dict() if job.payload_ref else None),
            "metadata": json.dumps(job.metadata),
            "status": job.status.value,
        }
        await self.redis.hset(self.keys.job(job.job_id), mapping=mapping)

        if job.parent_job_id:
            await self.redis.set(self.keys.job_parent(job.job_id), job.parent_job_id)
            await self.redis.sadd(self.keys.job_children(job.parent_job_id), job.job_id)
        else:
            await self.redis.sadd(self.keys.input_root(job.root_input_id), job.job_id)

    async def attach_children(self, parent_job_id: str, children: Sequence[AsyncJob]) -> None:
        if not children:
            return
        await asyncio.gather(*(self._persist_job(child) for child in children))

    async def get_job(self, job_id: str) -> Optional[AsyncJob]:
        data = await self.redis.hgetall(self.keys.job(job_id))
        if not data:
            return None
        # Redis returns bytes
        decoded = {k.decode(): v.decode() for k, v in data.items()}
        payload_raw = decoded.get("payload_ref")
        metadata_raw = decoded.get("metadata") or "{}"
        return AsyncJob(
            job_id=decoded["job_id"],
            parent_job_id=decoded.get("parent_job_id") or None,
            root_input_id=decoded["root_input_id"],
            plugin_id=decoded["plugin_id"],
            hook=decoded["hook"],
            payload_ref=PayloadRef.from_mapping(json.loads(payload_raw)) if payload_raw else None,
            metadata=json.loads(metadata_raw),
            status=JobStatus(decoded.get("status", JobStatus.PENDING.value)),
        )

    async def mark_status(self, job_id: str, status: JobStatus, *, error: Optional[str] = None) -> None:
        updates: Dict[str, Any] = {"status": status.value}
        if error is not None:
            # Attach last_error inside metadata to avoid changing message schema
            existing = await self.get_job(job_id)
            meta = existing.metadata if existing else {}
            meta = dict(meta)
            meta["last_error"] = error
            updates["metadata"] = json.dumps(meta)
        await self.redis.hset(self.keys.job(job_id), mapping=updates)

    async def mark_running(self, job_id: str) -> None:
        await self.mark_status(job_id, JobStatus.RUNNING)

    async def mark_done(self, job_id: str) -> None:
        await self.mark_status(job_id, JobStatus.DONE)

    async def mark_failed(self, job_id: str, *, reason: Optional[str] = None) -> None:
        await self.mark_status(job_id, JobStatus.FAILED, error=reason)

    async def get_children_ids(self, job_id: str) -> List[str]:
        raw = await self.redis.smembers(self.keys.job_children(job_id))
        return sorted({val.decode() for val in raw})

    async def get_root_jobs(self, input_id: str) -> List[str]:
        raw = await self.redis.smembers(self.keys.input_root(input_id))
        return sorted({val.decode() for val in raw})

    async def get_parent_id(self, job_id: str) -> Optional[str]:
        value = await self.redis.get(self.keys.job_parent(job_id))
        return value.decode() if value else None

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


class RedisQueue:
    """Redis-backed message queue (Operator)."""

    def __init__(self, redis: Redis, *, namespace: Optional[str] = None):
        self.redis = redis
        self.keys = RedisKeys(namespace)

    async def enqueue(self, job: AsyncJob) -> None:
        await self.redis.lpush(self.keys.queue(job.plugin_id), json.dumps(job.message()))

    async def enqueue_many(self, jobs: Iterable[AsyncJob]) -> None:
        tasks = [self.enqueue(job) for job in jobs]
        if tasks:
            await asyncio.gather(*tasks)

    async def dequeue(self, plugin_id: str, *, timeout: int = 0) -> Optional[Dict[str, Any]]:
        result = await self.redis.brpop(self.keys.queue(plugin_id), timeout=timeout)
        if not result:
            return None
        _, raw_message = result
        payload = raw_message.decode()
        return json.loads(payload)
