import fakeredis.aioredis
import pytest

from rag2f.core.flux_capacitor.agent import AgentWorker
from rag2f.core.flux_capacitor.jobs import JobStatus, RedisJobStore, RedisQueue
from tests.mocks.plugins.agent_plugin import agent_hooks


@pytest.mark.asyncio
async def test_job_store_tracks_tree_and_progress():
    redis = fakeredis.aioredis.FakeRedis()
    store = RedisJobStore(redis)

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
    redis = fakeredis.aioredis.FakeRedis()
    store = RedisJobStore(redis)
    queue = RedisQueue(redis)

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
    redis = fakeredis.aioredis.FakeRedis()
    store = RedisJobStore(redis)
    queue = RedisQueue(redis)

    agent_hooks.EXECUTION_LOG.clear()

    root_job = await store.create_job(
        plugin_id="agent_plugin",
        hook="agent_entry_hook",
        root_input_id="input-1",
        payload_ref={"repository": "raw_inputs", "id": "root-doc"},
    )
    await queue.enqueue(root_job)

    worker = AgentWorker(plugin_id="agent_plugin", redis=redis, morpheus=morpheus)

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
