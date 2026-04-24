"""IndianaJones retrieve manager.

IndianaJones handles RAG retrieval and search operations with extensible
backends and plugin enrichment. Expected states (empty query) return
Result with status="error". System errors (backend crash) raise exceptions.

Architecture:
- execute_retrieve() runs retrieval via `indiana_jones_retrieve` hook.
- execute_search() calls execute_retrieve() then `indiana_jones_synthesize` hook.

"Fortune and glory, kid. Fortune and glory."
"""

import logging
from typing import Any

from rag2f.core.dto.indiana_jones_dto import (
    RetrieveResult,
    ReturnMode,
    SearchResult,
)
from rag2f.core.dto.result_dto import StatusCode, StatusDetail
from rag2f.core.indiana_jones.exceptions import (
    RetrievalError,
)
from rag2f.core.observability import debug_event, exception_event, observation_scope

logger = logging.getLogger(__name__)


class IndianaJones:
    """RAG retrieval and search orchestrator.

    Coordinates retrieval backends, generator backends, attribution strategies,
    and plugin enrichment to provide a complete RAG pipeline.

    Flow:
    - execute_retrieve() → hook `indiana_jones_retrieve`
    - execute_search()   → execute_retrieve() → hook `indiana_jones_synthesize`

    Famous quote from Indiana Jones:
    "Fortune and glory, kid. Fortune and glory."
    """

    def __init__(self, rag2f_instance=None):
        """Create an IndianaJones instance.

        Args:
            rag2f_instance: Optional RAG2F instance used to invoke hooks.
        """
        self.rag2f = rag2f_instance
        debug_event(logger, "indiana_jones_initialized", has_rag2f=self.rag2f is not None)

    def execute_retrieve(
        self,
        query: str,
        k: int = 10,
        *,
        return_mode: ReturnMode = ReturnMode.WITH_ITEMS,
        for_synthesize: bool = False,
        **kwargs: Any,
    ) -> RetrieveResult:
        """Retrieve relevant items for a query.

        [Result Pattern] Check result.is_ok() before using fields.

        Args:
            query: The search query string.
            k: Maximum number of items to retrieve.
            return_mode: Controls what data is included in the result.
            for_synthesize: True when called internally by execute_search().
            **kwargs: Backend-specific parameters.

        Returns:
            RetrieveResult with status="success" and items if retrieval succeeded,
            or status="error" with detail for expected failures:
            - StatusCode.EMPTY: Query is empty or whitespace-only

        Raises:
            RetrievalError: Only for system errors (backend crash, timeout).
        """
        with observation_scope(operation="indiana_jones.execute_retrieve"):
            query_length = len(query) if query is not None else 0
            debug_event(
                logger,
                "indiana_jones_retrieve_start",
                query_length=query_length,
                k=k,
                return_mode=return_mode.value,
                for_synthesize=for_synthesize,
                kwargs_count=len(kwargs),
            )

            if query is None or not str(query).strip():
                debug_event(logger, "indiana_jones_retrieve_empty")
                return RetrieveResult.fail(
                    StatusDetail(code=StatusCode.EMPTY, message="Query is empty")
                )

            try:
                result = RetrieveResult.success(query=query)
                if self.rag2f:
                    result = self.rag2f.morpheus.execute_hook(
                        "indiana_jones_retrieve",
                        result,
                        query,
                        k,
                        return_mode,
                        for_synthesize,
                        rag2f=self.rag2f,
                    )
            except Exception as e:
                exception_event(
                    logger,
                    "indiana_jones_retrieve_failed",
                    query_length=query_length,
                    k=k,
                    return_mode=return_mode.value,
                    for_synthesize=for_synthesize,
                    error_type=type(e).__name__,
                )
                raise RetrievalError(
                    f"Retrieval failed: {e}",
                    context={"query": query, "k": k, "kwargs": kwargs},
                ) from e

            debug_event(
                logger,
                "indiana_jones_retrieve_complete",
                item_count=len(result.items),
                status=result.status,
            )
            return result

    def execute_search(
        self,
        query: str,
        k: int = 10,
        return_mode: ReturnMode = ReturnMode.MINIMAL,
        **kwargs: Any,
    ) -> SearchResult:
        """Retrieve and synthesize a response for a query.

        Internally calls execute_retrieve() then the `indiana_jones_synthesize` hook.

        [Result Pattern] Check result.is_ok() before using fields.

        Args:
            query: The search query string.
            k: Maximum number of items to retrieve.
            return_mode: Controls what data is included in the final result.
            **kwargs: Backend-specific parameters.

        Returns:
            SearchResult with status="success" if search succeeded,
            or status="error" with detail for expected failures:
            - StatusCode.EMPTY: Query is empty or whitespace-only

        Raises:
            RetrievalError: Only for system errors (backend crash, timeout).
        """
        with observation_scope(operation="indiana_jones.execute_search"):
            query_length = len(query) if query is not None else 0
            debug_event(
                logger,
                "indiana_jones_search_start",
                query_length=query_length,
                k=k,
                return_mode=return_mode.value,
                kwargs_count=len(kwargs),
            )

            retrieve_result = self.execute_retrieve(
                query, k, return_mode=ReturnMode.WITH_ITEMS, for_synthesize=True, **kwargs
            )

            if retrieve_result.is_error():
                debug_event(
                    logger,
                    "indiana_jones_search_retrieve_error",
                    detail_code=retrieve_result.detail.code if retrieve_result.detail else None,
                )
                return SearchResult.fail(retrieve_result.detail)

            try:
                result = SearchResult.success(query=query, items=retrieve_result.items)
                if self.rag2f:
                    result = self.rag2f.morpheus.execute_hook(
                        "indiana_jones_synthesize",
                        result,
                        retrieve_result,
                        return_mode,
                        kwargs,
                        rag2f=self.rag2f,
                    )

                if return_mode == ReturnMode.MINIMAL:
                    result.items = None

            except Exception as e:
                exception_event(
                    logger,
                    "indiana_jones_search_failed",
                    query_length=query_length,
                    k=k,
                    return_mode=return_mode.value,
                    error_type=type(e).__name__,
                )
                raise RetrievalError(
                    f"Search failed: {e}",
                    context={"query": query, "k": k, "kwargs": kwargs},
                ) from e

            debug_event(
                logger,
                "indiana_jones_search_complete",
                response_length=len(result.response),
                used_source_count=len(result.used_source_ids),
                returned_items=result.items is not None,
            )
            return result


RetrieveManager = IndianaJones
