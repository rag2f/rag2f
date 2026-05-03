"""Minimal FluxCapacitor task execution tests."""

from __future__ import annotations

import importlib
from datetime import UTC, datetime, timedelta

import pytest

from rag2f.core.flux_capacitor import (
    HookResolutionError,
    InMemoryTaskQueue,
    InMemoryTaskStore,
    TaskEnvelope,
    TaskRegistrationError,
    TaskResolutionError,
)


def _configure_test_backend(
    rag2f, flux, *, name: str
) -> tuple[InMemoryTaskStore, InMemoryTaskQueue]:
    store = InMemoryTaskStore()
    queue = InMemoryTaskQueue()
    flux.register_store(name, store)
    flux.register_queue(name, queue)
    rag2f.spock.set_rag2f_config("task_store_default", name)
    rag2f.spock.set_rag2f_config("task_queue_default", name)
    return store, queue


def test_flux_capacitor_runs_task_tree(rag2f) -> None:
    flux = rag2f.task_manager

    store, _queue = _configure_test_backend(rag2f, flux, name="test_memory")

    hooks_module = importlib.import_module("plugins.flux_plugin.flux_hooks")
    hooks_module.EXECUTION_LOG.clear()

    root_id = flux.enqueue(
        plugin_id="flux_plugin",
        hook="flux_entry_hook",
        payload_ref={"repository": "repo", "id": "payload-1"},
    )

    while flux.run_once():
        pass

    parent = store.get_task(root_id)
    assert parent is not None
    assert parent.finished_at is not None
    assert parent.error is None

    children = store.list_children(root_id)
    assert len(children) == 1
    child = children[0]
    assert child.parent_id == root_id
    assert child.finished_at is not None
    assert child.error is None

    assert hooks_module.EXECUTION_LOG == ["flux_entry_hook", "flux_child_hook"]


def test_flux_capacitor_reports_tree_status_during_nested_workflow(rag2f) -> None:
    flux = rag2f.task_manager
    store, _queue = _configure_test_backend(rag2f, flux, name="status_memory")

    hooks_module = importlib.import_module("plugins.flux_plugin.flux_hooks")
    hooks_module.EXECUTION_LOG.clear()

    root_id = flux.enqueue(
        plugin_id="flux_plugin",
        hook="flux_fanout_root_hook",
        payload_ref={"repository": "repo", "id": "root-1", "meta": {"kind": "primitive"}},
    )

    initial_status = store.get_status(root_id, include_descendants=True)
    assert initial_status.status == "pending"
    assert initial_status.descendant_count == 0
    assert not initial_status.tree_completed

    assert flux.run_once(worker_id="worker-root")
    after_root = store.get_status(root_id, include_descendants=True)
    assert after_root.status == "completed"
    assert after_root.descendant_count == 2
    assert after_root.pending_count == 2
    assert after_root.completed_count == 0
    assert not after_root.tree_completed

    assert flux.run_once(worker_id="worker-branch")
    after_branch = flux.get_status(root_id, include_descendants=True)
    assert after_branch.status == "completed"
    assert after_branch.descendant_count == 4
    assert after_branch.pending_count == 3
    assert after_branch.completed_count == 1
    assert not after_branch.tree_completed

    assert flux.run_once(worker_id="worker-leaf")
    after_leaf = store.get_status(root_id, include_descendants=True)
    assert after_leaf.pending_count == 2
    assert after_leaf.completed_count == 2
    assert not after_leaf.tree_completed

    assert flux.run_once(worker_id="worker-grandchild-a")
    assert flux.run_once(worker_id="worker-grandchild-b")

    final_status = store.get_status(root_id, include_descendants=True)
    assert final_status.tree_completed
    assert final_status.pending_count == 0
    assert final_status.reserved_count == 0
    assert final_status.failed_count == 0
    assert final_status.completed_count == 4
    assert len(final_status.descendants) == 4
    assert flux.is_tree_done(root_id)

    root_task = store.get_task(root_id)
    assert root_task is not None
    assert root_task.root_id == root_id

    descendants = final_status.descendants
    assert all(descendant.root_id == root_id for descendant in descendants)
    assert hooks_module.EXECUTION_LOG == [
        "flux_fanout_root_hook",
        "flux_branch_hook",
        "flux_leaf_hook",
        "flux_grandchild_a_hook",
        "flux_grandchild_b_hook",
    ]


def test_flux_capacitor_retry_preserves_task_identity(rag2f) -> None:
    flux = rag2f.task_manager
    store, _queue = _configure_test_backend(rag2f, flux, name="retry_memory")

    task_id = flux.enqueue(
        plugin_id="flux_plugin",
        hook="flux_child_hook",
        payload_ref={"repository": "repo", "id": "retry-1"},
    )

    first_reservation = flux.reserve(worker_id="worker-a")
    assert first_reservation is not None
    assert first_reservation.task_id == task_id

    reserved_status = store.get_status(task_id, include_descendants=True)
    assert reserved_status.status == "reserved"
    assert reserved_status.attempts == 1

    flux.retry(
        task_id,
        error_msg="temporary failure",
        reservation_ref=first_reservation.reservation_ref,
    )

    retry_status = store.get_status(task_id, include_descendants=True)
    assert retry_status.status == "retry_scheduled"
    assert retry_status.last_error == "temporary failure"

    second_reservation = flux.reserve(worker_id="worker-b")
    assert second_reservation is not None
    assert second_reservation.task_id == task_id

    task = store.get_task(task_id)
    assert task is not None
    assert task.root_id == task_id
    assert task.attempts == 2


def test_inmemory_queue_reclaims_expired_reservation() -> None:
    queue = InMemoryTaskQueue(visibility_timeout=timedelta(seconds=10))
    queue.publish(
        TaskEnvelope(
            task_id="task-1",
            root_id="task-1",
            parent_id=None,
            plugin_id="flux_plugin",
            hook="flux_child_hook",
        )
    )

    first_reservation = queue.reserve(worker_id="worker-a")
    assert first_reservation is not None
    assert first_reservation.reservation_ref is not None
    assert queue.pending_task_ids() == set()
    assert queue.reserved_task_ids() == {"task-1"}

    reclaimed = queue.reclaim_expired(now=datetime.now(UTC) + timedelta(seconds=11))

    assert [envelope.task_id for envelope in reclaimed] == ["task-1"]
    assert reclaimed[0].reservation_ref is None
    assert queue.pending_task_ids() == {"task-1"}
    assert queue.reserved_task_ids() == set()

    second_reservation = queue.reserve(worker_id="worker-b")
    assert second_reservation is not None
    assert second_reservation.task_id == "task-1"
    assert second_reservation.reservation_ref != first_reservation.reservation_ref


def test_flux_capacitor_can_reserve_reclaimed_inmemory_task(rag2f) -> None:
    flux = rag2f.task_manager
    store = InMemoryTaskStore()
    queue = InMemoryTaskQueue(visibility_timeout=timedelta(seconds=10))
    flux.register_store("reclaim_memory", store)
    flux.register_queue("reclaim_memory", queue)
    rag2f.spock.set_rag2f_config("task_store_default", "reclaim_memory")
    rag2f.spock.set_rag2f_config("task_queue_default", "reclaim_memory")

    task_id = flux.enqueue(
        plugin_id="flux_plugin",
        hook="flux_child_hook",
        payload_ref={"repository": "repo", "id": "reclaim-1"},
    )

    first_reservation = flux.reserve(worker_id="worker-a")
    assert first_reservation is not None
    assert first_reservation.task_id == task_id

    queue.reclaim_expired(now=datetime.now(UTC) + timedelta(seconds=11))
    second_reservation = flux.reserve(worker_id="worker-b")

    assert second_reservation is not None
    assert second_reservation.task_id == task_id
    assert second_reservation.reservation_ref != first_reservation.reservation_ref

    task = store.get_task(task_id)
    assert task is not None
    assert task.status == "reserved"
    assert task.worker_id == "worker-b"
    assert task.attempts == 2


def test_flux_capacitor_duplicate_store_registration_raises_module_error(rag2f) -> None:
    flux = rag2f.task_manager

    flux.register_store("duplicate_store", InMemoryTaskStore())

    with pytest.raises(TaskRegistrationError, match="Override not allowed") as exc_info:
        flux.register_store("duplicate_store", InMemoryTaskStore())

    assert exc_info.value.context == {"store_name": "duplicate_store"}


def test_flux_capacitor_missing_parent_raises_task_resolution_error(rag2f) -> None:
    flux = rag2f.task_manager
    _configure_test_backend(rag2f, flux, name="missing_parent_memory")

    with pytest.raises(
        TaskResolutionError, match="Parent task 'missing-parent' not found"
    ) as exc_info:
        flux.enqueue(
            plugin_id="flux_plugin",
            hook="flux_child_hook",
            payload_ref={"repository": "repo", "id": "child-1"},
            parent_id="missing-parent",
        )

    assert exc_info.value.context["parent_id"] == "missing-parent"
    assert "task_id" in exc_info.value.context


def test_flux_capacitor_retry_unknown_task_raises_task_resolution_error(rag2f) -> None:
    flux = rag2f.task_manager
    _configure_test_backend(rag2f, flux, name="missing_task_memory")

    with pytest.raises(TaskResolutionError, match="Unknown task: missing-task") as exc_info:
        flux.retry("missing-task", error_msg="temporary failure")

    assert exc_info.value.context == {"task_id": "missing-task"}


def test_flux_capacitor_missing_hook_exposes_resolution_context(rag2f) -> None:
    flux = rag2f.task_manager
    _configure_test_backend(rag2f, flux, name="missing_hook_memory")

    with pytest.raises(HookResolutionError, match="Hook 'missing_hook' not found") as exc_info:
        flux.enqueue(
            plugin_id="flux_plugin",
            hook="missing_hook",
            payload_ref={"repository": "repo", "id": "missing-hook-1"},
        )

    assert exc_info.value.context == {
        "plugin_id": "flux_plugin",
        "hook_name": "missing_hook",
    }


def test_flux_capacitor_reads_store_and_queue_defaults_from_live_spock(rag2f) -> None:
    flux = rag2f.task_manager

    primary_store = InMemoryTaskStore()
    primary_queue = InMemoryTaskQueue()
    secondary_store = InMemoryTaskStore()
    secondary_queue = InMemoryTaskQueue()

    flux.register_store("spock_primary", primary_store)
    flux.register_queue("spock_primary", primary_queue)
    flux.register_store("spock_secondary", secondary_store)
    flux.register_queue("spock_secondary", secondary_queue)

    rag2f.spock.set_rag2f_config("task_store_default", "spock_primary")
    rag2f.spock.set_rag2f_config("task_queue_default", "spock_primary")

    assert flux.get_store() is primary_store
    assert flux.get_queue() is primary_queue

    rag2f.spock.set_rag2f_config("task_store_default", "spock_secondary")
    rag2f.spock.set_rag2f_config("task_queue_default", "spock_secondary")

    assert flux.get_store() is secondary_store
    assert flux.get_queue() is secondary_queue
