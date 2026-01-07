import asyncio
import inspect
import logging
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional, Sequence

from rag2f.core.flux_capacitor.jobs import (
    AgentHookResult,
    AsyncJob,
    BaseJobStore,
    BaseQueue,
    ChildJobRequest,
)
from rag2f.core.morpheus.morpheus import Morpheus


logger = logging.getLogger(__name__)

PayloadLoader = Callable[[Any], Awaitable[Any] | Any]


class AgentContext:
    """Context passed to hook handlers."""

    def __init__(
        self,
        *,
        job: AsyncJob,
        payload_loader: Optional[PayloadLoader] = None,
    ):
        self.job = job
        self._payload_loader = payload_loader
        self._child_requests: List[ChildJobRequest] = []

    def emit_child(
        self,
        hook: str,
        *,
        plugin_id: Optional[str] = None,
        payload_ref: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        job_id: Optional[str] = None,
    ) -> ChildJobRequest:
        child = ChildJobRequest(
            hook=hook,
            plugin_id=plugin_id or self.job.plugin_id,
            payload_ref=payload_ref,
            metadata=metadata,
            job_id=job_id,
        )
        self._child_requests.append(child)
        return child

    def emit_children(self, children: Iterable[ChildJobRequest]) -> List[ChildJobRequest]:
        staged = []
        for child in children:
            if not isinstance(child, ChildJobRequest):
                continue
            self._child_requests.append(child)
            staged.append(child)
        return staged

    @property
    def staged_children(self) -> List[ChildJobRequest]:
        return list(self._child_requests)

    async def load_payload(self) -> Any:
        if self._payload_loader is None:
            raise RuntimeError("No payload loader configured for this AgentContext")
        return await _run_sync_or_async(self._payload_loader, self.job.payload_ref)


class AgentWorker:
    """Stateless worker that executes a single hook at a time."""

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
    ):
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
        logger.info("Starting AgentWorker for plugin %s", self.plugin_id)
        while not self._stop_event.is_set():
            try:
                message = await self.queue.dequeue(self.plugin_id, timeout=self.dequeue_timeout)
                if message is None:
                    continue
                await self._handle_message(message)
            except asyncio.CancelledError:
                break
            except Exception as exc:  # pragma: no cover - guardrail for robustness
                logger.exception("Worker loop error: %s", exc)
        logger.info("AgentWorker for plugin %s stopped", self.plugin_id)

    async def _handle_message(self, message: Dict[str, Any]) -> None:
        job = await self._load_or_restore_job(message)
        await self.job_store.mark_running(job.job_id)

        context = AgentContext(job=job, payload_loader=self.payload_loader)
        hook = self.morpheus.resolve_hook(job.plugin_id, job.hook)
        if hook is None:
            logger.error("Hook %s not found for plugin %s", job.hook, job.plugin_id)
            await self.job_store.mark_failed(job.job_id, reason="Hook not found")
            return

        try:
            result = await self._invoke_handler(hook.function, job, context)
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.exception("Job %s failed executing hook %s: %s", job.job_id, job.hook, exc)
            await self.job_store.mark_failed(job.job_id, reason=str(exc))
            return

        children_requests = self._collect_child_requests(result, context)
        if children_requests:
            children_jobs = await self._materialize_children(job, children_requests)
            await self.queue.enqueue_many(children_jobs)

        await self.job_store.mark_done(job.job_id)

    async def _load_or_restore_job(self, message: Dict[str, Any]) -> AsyncJob:
        existing = await self.job_store.get_job(message["job_id"])
        if existing:
            return existing

        job = await self.job_store.create_job(
            plugin_id=message["plugin_id"],
            hook=message["hook"],
            root_input_id=message["root_input_id"],
            payload_ref=message.get("payload_ref"),
            metadata=message.get("metadata"),
            parent_job_id=message.get("parent_job_id"),
            job_id=message.get("job_id"),
        )
        return job

    async def _materialize_children(
        self,
        parent: AsyncJob,
        requests: Sequence[ChildJobRequest],
    ) -> List[AsyncJob]:
        jobs: List[AsyncJob] = []
        for req in requests:
            job = await self.job_store.create_job(
                plugin_id=req.plugin_id,
                hook=req.hook,
                root_input_id=parent.root_input_id,
                payload_ref=req.payload_ref,
                metadata=req.metadata,
                parent_job_id=parent.job_id,
                job_id=req.job_id,
            )
            jobs.append(job)
        return jobs

    async def _invoke_handler(self, handler: Callable[..., Any], job: AsyncJob, context: AgentContext) -> Any:
        kwargs = self._build_kwargs(handler, job, context)
        result = handler(**kwargs)
        if inspect.isawaitable(result):
            result = await result
        return result

    def _build_kwargs(self, handler: Callable[..., Any], job: AsyncJob, context: AgentContext) -> Dict[str, Any]:
        sig = inspect.signature(handler)
        available: Dict[str, Any] = {
            "job": job,
            "context": context,
            "payload_ref": job.payload_ref.to_dict() if job.payload_ref else None,
            "metadata": job.metadata,
            "root_input_id": job.root_input_id,
        }
        if self.rag2f is not None:
            available["rag2f"] = self.rag2f
        if context._payload_loader is not None:
            available["payload_loader"] = context._payload_loader

        kwargs: Dict[str, Any] = {}
        for name, param in sig.parameters.items():
            if param.kind == inspect.Parameter.VAR_KEYWORD:
                kwargs.update(available)
                break
            if name in available:
                kwargs[name] = available[name]
        return kwargs

    def _collect_child_requests(
        self,
        result: Any,
        context: AgentContext,
    ) -> List[ChildJobRequest]:
        requests: List[ChildJobRequest] = []
        requests.extend(context.staged_children)

        if isinstance(result, AgentHookResult):
            requests.extend(result.children)
        elif isinstance(result, ChildJobRequest):
            requests.append(result)
        elif isinstance(result, Sequence) and not isinstance(result, (str, bytes, dict)):
            requests.extend(self._normalize_sequence(result))
        elif isinstance(result, dict):
            normalized = self._normalize_dict(result)
            if normalized:
                requests.append(normalized)

        return requests

    def _normalize_sequence(self, seq: Sequence[Any]) -> List[ChildJobRequest]:
        normalized: List[ChildJobRequest] = []
        for item in seq:
            if isinstance(item, ChildJobRequest):
                normalized.append(item)
            elif isinstance(item, dict):
                cj = self._normalize_dict(item)
                if cj:
                    normalized.append(cj)
        return normalized

    def _normalize_dict(self, raw: Dict[str, Any]) -> Optional[ChildJobRequest]:
        if "hook" not in raw:
            return None
        plugin_id = raw.get("plugin_id") or self.plugin_id
        payload_ref = raw.get("payload_ref")
        metadata = raw.get("metadata")
        job_id = raw.get("job_id")
        return ChildJobRequest(
            hook=raw["hook"],
            plugin_id=plugin_id,
            payload_ref=payload_ref,
            metadata=metadata,
            job_id=job_id,
        )


async def _run_sync_or_async(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    result = func(*args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result
