"""Async agent execution for flux capacitor jobs."""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Awaitable, Callable, Iterable, Sequence
from typing import Any, Optional

from rag2f.core.flux_capacitor.jobs import (
    AgentHookResult,
    AsyncJob,
    BaseJobStore,
    BaseQueue,
    ChildJobRequest,
    PayloadRef,
)
from rag2f.core.morpheus.morpheus import Morpheus

logger = logging.getLogger(__name__)
PayloadLoader = Callable[[Any], Awaitable[Any] | Any]


async def _run_sync_or_async(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    result = func(*args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


class AgentContext:
    """Context passed to async agent hooks."""

    def __init__(self, *, job: AsyncJob, payload_loader: Optional[PayloadLoader] = None):
        self.job = job
        self._payload_loader = payload_loader
        self._children: list[ChildJobRequest] = []

    def emit_child(
        self,
        hook: str,
        *,
        plugin_id: Optional[str] = None,
        payload_ref: Optional[dict[str, Any]] = None,
        metadata: Optional[dict[str, Any]] = None,
        job_id: Optional[str] = None,
    ) -> ChildJobRequest:
        child = ChildJobRequest(
            hook=hook,
            plugin_id=plugin_id or self.job.plugin_id,
            payload_ref=payload_ref,
            metadata=metadata,
            job_id=job_id,
        )
        self._children.append(child)
        return child

    def emit_children(self, children: Iterable[ChildJobRequest]) -> None:
        for child in children:
            self._children.append(child)

    @property
    def staged_children(self) -> list[ChildJobRequest]:
        return list(self._children)

    async def load_payload(self) -> Any:
        if self._payload_loader is None:
            raise RuntimeError("No payload loader configured")
        return await _run_sync_or_async(self._payload_loader, self.job.payload_ref)


class AgentWorker:
    """Worker that pulls async jobs and executes matching hooks."""

    def __init__(
        self,
        *,
        plugin_id: str,
        job_store: BaseJobStore,
        queue: BaseQueue,
        morpheus: Morpheus,
        rag2f: Any = None,
        payload_loader: Optional[PayloadLoader] = None,
        dequeue_timeout: int = 1,
    ) -> None:
        self.plugin_id = plugin_id
        self.job_store = job_store
        self.queue = queue
        self.morpheus = morpheus
        self.rag2f = rag2f
        self.payload_loader = payload_loader
        self.dequeue_timeout = dequeue_timeout
        self._stop_event = asyncio.Event()

    def stop(self) -> None:
        self._stop_event.set()

    async def run_forever(self) -> None:
        while not self._stop_event.is_set():
            try:
                message = await self.queue.dequeue(
                    self.plugin_id, timeout=self.dequeue_timeout
                )
                if message is None:
                    continue
                await self._handle_message(message)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Agent worker failed to process message")

    async def _handle_message(self, message: dict[str, Any]) -> None:
        job = await self._load_or_restore_job(message)
        await self.job_store.mark_running(job.job_id)

        hook = self.morpheus.resolve_hook(job.plugin_id, job.hook)
        if hook is None:
            await self.job_store.mark_failed(job.job_id, reason="Hook not found")
            return

        context = AgentContext(job=job, payload_loader=self.payload_loader)

        try:
            result = await self._invoke_handler(hook.function, job, context)
            children = self._collect_children(context, result, job)

            if children:
                created_children = [
                    await self.job_store.create_job(
                        plugin_id=child.plugin_id,
                        hook=child.hook,
                        root_input_id=job.root_input_id,
                        payload_ref=child.payload_ref,
                        metadata=child.metadata,
                        parent_job_id=job.job_id,
                        job_id=child.job_id,
                    )
                    for child in children
                ]
                await self.queue.enqueue_many(created_children)

            await self.job_store.mark_done(job.job_id)
        except Exception as exc:
            logger.exception("Agent hook failed: %s", job.job_id)
            await self.job_store.mark_failed(job.job_id, reason=str(exc))

    async def _load_or_restore_job(self, message: dict[str, Any]) -> AsyncJob:
        job_id = message.get("job_id")
        if job_id:
            existing = await self.job_store.get_job(job_id)
            if existing is not None:
                return existing

        return await self.job_store.create_job(
            plugin_id=message["plugin_id"],
            hook=message["hook"],
            root_input_id=message["root_input_id"],
            payload_ref=message.get("payload_ref"),
            metadata=message.get("metadata"),
            parent_job_id=message.get("parent_job_id"),
            job_id=job_id,
        )

    async def _invoke_handler(
        self,
        handler: Callable[..., Any],
        job: AsyncJob,
        context: AgentContext,
    ) -> Any:
        payload_ref: Optional[dict[str, Any]]
        if job.payload_ref is None:
            payload_ref = None
        elif isinstance(job.payload_ref, PayloadRef):
            payload_ref = job.payload_ref.to_dict()
        else:
            payload_ref = job.payload_ref  # type: ignore[assignment]

        available = {
            "job": job,
            "context": context,
            "payload_ref": payload_ref,
            "metadata": job.metadata,
            "root_input_id": job.root_input_id,
        }
        if self.rag2f is not None:
            available["rag2f"] = self.rag2f
        if self.payload_loader is not None:
            available["payload_loader"] = self.payload_loader

        signature = inspect.signature(handler)
        if any(param.kind == param.VAR_KEYWORD for param in signature.parameters.values()):
            call_kwargs = available
        else:
            call_kwargs = {
                name: value
                for name, value in available.items()
                if name in signature.parameters
            }

        return await _run_sync_or_async(handler, **call_kwargs)

    def _collect_children(
        self,
        context: AgentContext,
        result: Any,
        job: AsyncJob,
    ) -> list[ChildJobRequest]:
        requests = list(context.staged_children)

        if isinstance(result, AgentHookResult):
            requests.extend(result.children)
        elif isinstance(result, ChildJobRequest):
            requests.append(result)
        elif isinstance(result, dict) and "hook" in result:
            requests.append(self._normalize_child_request(result, job))
        elif isinstance(result, Sequence) and not isinstance(result, (str, bytes)):
            for item in result:
                if isinstance(item, ChildJobRequest):
                    requests.append(item)
                elif isinstance(item, dict) and "hook" in item:
                    requests.append(self._normalize_child_request(item, job))

        normalized: list[ChildJobRequest] = []
        for request in requests:
            if request is None:
                continue
            if request.plugin_id is None:
                request.plugin_id = job.plugin_id
            normalized.append(request)

        return normalized

    def _normalize_child_request(
        self, item: dict[str, Any], job: AsyncJob
    ) -> ChildJobRequest:
        return ChildJobRequest(
            hook=item["hook"],
            plugin_id=item.get("plugin_id") or job.plugin_id,
            payload_ref=item.get("payload_ref"),
            metadata=item.get("metadata"),
            job_id=item.get("job_id"),
        )
