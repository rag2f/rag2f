"""Tests for the async flux capacitor engine."""

from __future__ import annotations

import asyncio
import importlib

import pytest

from rag2f.core.flux_capacitor import (
    AgentWorker,
    AsyncJob,
    BaseJobStore,
    BaseQueue,
    JobStatus,
    PayloadRef,
)


class InMemoryJobStore(BaseJobStore):
    def __init__(self) -> None:
        self.jobs: dict[str, AsyncJob] = {}
        self.children: dict[str, list[str]] = {}
        self.parents: dict[str, str] = {}
        self.roots: dict[str, list[str]] = {}

    async def _persist_job(self, job: AsyncJob) -> None:
        self.jobs[job.job_id] = job
        if job.parent_job_id:
            self.parents[job.job_id] = job.parent_job_id
            self.children.setdefault(job.parent_job_id, []).append(job.job_id)
        else:
            self.roots.setdefault(job.root_input_id, []).append(job.job_id)

    async def get_job(self, job_id: str) -> AsyncJob | None:
        return self.jobs.get(job_id)

    async def mark_status(
        self, job_id: str, status: JobStatus, *, error: str | None = None
    ) -> None:
        job = self.jobs[job_id]
        job.status = status
        if error:
            job.metadata["error"] = error

    async def get_children_ids(self, job_id: str) -> list[str]:
        return list(self.children.get(job_id, []))

    async def get_root_jobs(self, input_id: str) -> list[str]:
        return list(self.roots.get(input_id, []))

    async def get_parent_id(self, job_id: str) -> str | None:
        return self.parents.get(job_id)


class InMemoryQueue(BaseQueue):
    def __init__(self) -> None:
        self.queues: dict[str, asyncio.Queue] = {}

    async def enqueue(self, job: AsyncJob) -> None:
        queue = self.queues.setdefault(job.plugin_id, asyncio.Queue())
        await queue.put(job.message())

    async def dequeue(self, plugin_id: str, *, timeout: int = 0) -> dict | None:
        queue = self.queues.setdefault(plugin_id, asyncio.Queue())
        if timeout <= 0:
            if queue.empty():
                return None
            return await queue.get()
        try:
            return await asyncio.wait_for(queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None


@pytest.mark.asyncio
async def test_job_store_tracks_tree_and_progress() -> None:
    store = InMemoryJobStore()

    root = await store.create_job(
        plugin_id="agent_plugin",
        hook="agent_entry_hook",
        root_input_id="input-1",
    )
    child = await store.create_job(
        plugin_id="agent_plugin",
        hook="agent_child_hook",
        root_input_id=root.root_input_id,
        parent_job_id=root.job_id,
    )
    grandchild = await store.create_job(
        plugin_id="agent_plugin",
        hook="agent_child_hook",
        root_input_id=root.root_input_id,
        parent_job_id=child.job_id,
    )

    initial_view = await store.get_status_view(root.job_id)
    assert initial_view.status == JobStatus.RUNNING
    assert initial_view.progress == 0.0

    await store.mark_done(grandchild.job_id)
    await store.mark_done(child.job_id)
    await store.mark_done(root.job_id)

    final_view = await store.get_status_view(root.job_id)
    assert final_view.status == JobStatus.DONE
    assert final_view.progress == 1.0


@pytest.mark.asyncio
async def test_queue_payload_matches_spec() -> None:
    queue = InMemoryQueue()
    job = AsyncJob(
        job_id="job-1",
        parent_job_id=None,
        root_input_id="input-1",
        plugin_id="agent_plugin",
        hook="agent_entry_hook",
        payload_ref=PayloadRef(repository="repo", id="payload-1"),
        metadata={"retry": 1},
    )

    await queue.enqueue(job)
    message = await queue.dequeue("agent_plugin")

    assert message is not None
    assert set(message.keys()) == {
        "job_id",
        "parent_job_id",
        "root_input_id",
        "plugin_id",
        "hook",
        "payload_ref",
        "metadata",
    }
    assert message["payload_ref"] == {"repository": "repo", "id": "payload-1", "meta": {}}
    assert message["metadata"]["retry"] == 1


@pytest.mark.asyncio
async def test_agent_worker_executes_hook_and_fanout(morpheus) -> None:
    hooks_module = importlib.import_module("plugins.agent_plugin.agent_hooks")
    hooks_module.EXECUTION_LOG.clear()

    store = InMemoryJobStore()
    queue = InMemoryQueue()

    root = await store.create_job(
        plugin_id="agent_plugin",
        hook="agent_entry_hook",
        root_input_id="input-42",
    )
    await queue.enqueue(root)

    worker = AgentWorker(
        plugin_id="agent_plugin",
        job_store=store,
        queue=queue,
        morpheus=morpheus,
    )

    message = await queue.dequeue("agent_plugin")
    assert message is not None
    await worker._handle_message(message)

    assert len(store.get_children_ids(root.job_id)) == 1
    assert hooks_module.EXECUTION_LOG[-1] == "agent_entry_hook"

    child_message = await queue.dequeue("agent_plugin")
    assert child_message is not None
    await worker._handle_message(child_message)

    status_view = await store.get_status_view(root.job_id)
    assert status_view.status == JobStatus.DONE
    assert status_view.progress == 1.0
    assert hooks_module.EXECUTION_LOG[-1] == "agent_child_hook"
