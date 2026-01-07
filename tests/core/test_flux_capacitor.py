import asyncio
import pytest

import importlib

from rag2f.core.flux_capacitor.agent import AgentWorker
from rag2f.core.flux_capacitor.jobs import BaseJobStore, BaseQueue, JobStatus


class InMemoryJobStore(BaseJobStore):
    def __init__(self) -> None:
        self._jobs = {}
        self._parents = {}
        self._children = {}
        self._input_roots = {}

    async def _persist_job(self, job):
        self._jobs[job.job_id] = job
        if job.parent_job_id:
            self._parents[job.job_id] = job.parent_job_id
            self._children.setdefault(job.parent_job_id, set()).add(job.job_id)
        else:
            self._input_roots.setdefault(job.root_input_id, set()).add(job.job_id)

    async def get_job(self, job_id):
        return self._jobs.get(job_id)

    async def mark_status(self, job_id, status, *, error=None):
        job = self._jobs.get(job_id)
        if job is None:
            return
        job.status = status
        if error is not None:
            meta = dict(job.metadata)
            meta["last_error"] = error
            job.metadata = meta

    async def get_children_ids(self, job_id):
        return sorted(self._children.get(job_id, set()))

    async def get_root_jobs(self, input_id):
        return sorted(self._input_roots.get(input_id, set()))

    async def get_parent_id(self, job_id):
        return self._parents.get(job_id)


class InMemoryQueue(BaseQueue):
    def __init__(self) -> None:
        self._queues = {}

    async def enqueue(self, job):
        queue = self._queues.setdefault(job.plugin_id, asyncio.Queue())
        await queue.put(job.message())

    async def dequeue(self, plugin_id, *, timeout=0):
        queue = self._queues.setdefault(plugin_id, asyncio.Queue())
        if timeout == 0:
            return await queue.get()
        try:
            return await asyncio.wait_for(queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None


@pytest.mark.asyncio
async def test_job_store_tracks_tree_and_progress():
    store = InMemoryJobStore()

    root = await store.create_job(plugin_id="p1", hook="root_hook", root_input_id="root-123")
    child = await store.create_job(
        plugin_id="p1",
        hook="child_hook",
        root_input_id=root.root_input_id,
        parent_job_id=root.job_id,
    )
    grandchild = await store.create_job(
        plugin_id="p1",
        hook="grandchild_hook",
        root_input_id=root.root_input_id,
        parent_job_id=child.job_id,
    )

    view_initial = await store.get_status_view(root.job_id)
    assert view_initial.status == JobStatus.RUNNING  # children pending implies work in progress
    assert view_initial.progress == 0.0

    await store.mark_done(grandchild.job_id)
    await store.mark_done(child.job_id)
    await store.mark_done(root.job_id)

    view_final = await store.get_status_view(root.job_id)
    assert view_final.status == JobStatus.DONE
    assert view_final.progress == 1.0


@pytest.mark.asyncio
async def test_queue_payload_matches_spec():
    store = InMemoryJobStore()
    queue = InMemoryQueue()

    job = await store.create_job(
        plugin_id="spec_plugin",
        hook="spec_hook",
        root_input_id="root-abc",
        payload_ref={"repository": "raw_inputs", "id": "payload-1"},
        metadata={"retry": 0},
    )
    await queue.enqueue(job)

    message = await queue.dequeue("spec_plugin", timeout=1)
    assert message["job_id"] == job.job_id
    assert message["parent_job_id"] is None
    assert message["root_input_id"] == "root-abc"
    assert message["plugin_id"] == "spec_plugin"
    assert message["hook"] == "spec_hook"
    assert message["payload_ref"]["repository"] == "raw_inputs"
    assert message["payload_ref"]["id"] == "payload-1"
    assert "retry" in message["metadata"]


@pytest.mark.asyncio
async def test_agent_worker_executes_hook_and_fanout(morpheus):
    store = InMemoryJobStore()
    queue = InMemoryQueue()

    # NOTE: the plugin loader imports hook modules under the stable namespace
    # "plugins.<plugin_id>...". Importing the same file via the test package path
    # would create a second module instance with a different EXECUTION_LOG.
    agent_hooks = importlib.import_module("plugins.agent_plugin.agent_hooks")
    agent_hooks.EXECUTION_LOG.clear()

    root_job = await store.create_job(
        plugin_id="agent_plugin",
        hook="agent_entry_hook",
        root_input_id="input-1",
        payload_ref={"repository": "raw_inputs", "id": "root-doc"},
    )
    await queue.enqueue(root_job)

    worker = AgentWorker(plugin_id="agent_plugin", job_store=store, queue=queue, morpheus=morpheus)

    # Process parent job
    message = await queue.dequeue("agent_plugin", timeout=1)
    await worker._handle_message(message)

    child_ids = await store.get_children_ids(root_job.job_id)
    assert len(child_ids) == 1
    assert agent_hooks.EXECUTION_LOG[0]["name"] == "agent_entry_hook"

    # Process child job
    child_message = await queue.dequeue("agent_plugin", timeout=1)
    await worker._handle_message(child_message)

    status = await store.get_status_view(root_job.job_id)
    assert status.status == JobStatus.DONE
    assert status.progress == 1.0
    assert agent_hooks.EXECUTION_LOG[-1]["name"] == "agent_child_hook"
