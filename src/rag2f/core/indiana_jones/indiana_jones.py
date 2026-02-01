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
        logger.debug("IndianaJones created")

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
        logger.debug(
            "IndianaJones.execute_retrieve query=%r k=%d return_mode=%s for_synthesize=%s",
            query,
            k,
            return_mode.value,
            for_synthesize,
        )

        if query is None or not str(query).strip():
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
            logger.error("IndianaJones retrieval failed: %s", e)
            raise RetrievalError(
                f"Retrieval failed: {e}",
                context={"query": query, "k": k, "kwargs": kwargs},
            ) from e

        logger.debug("IndianaJones.execute_retrieve returned %d items", len(result.items))
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
        logger.debug(
            "IndianaJones.execute_search query=%r k=%d return_mode=%s", query, k, return_mode.value
        )

        # Step 1: Retrieve (always WITH_ITEMS internally for synthesis)
        retrieve_result = self.execute_retrieve(
            query, k, return_mode=ReturnMode.WITH_ITEMS, for_synthesize=True, **kwargs
        )

        if retrieve_result.is_error():
            return SearchResult.fail(retrieve_result.detail)

        # Step 2: Synthesize via hook
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

            # Apply return_mode policy: drop items if MINIMAL
            if return_mode == ReturnMode.MINIMAL:
                result.items = None

        except Exception as e:
            logger.error("IndianaJones synthesis failed: %s", e)
            raise RetrievalError(
                f"Search failed: {e}",
                context={"query": query, "k": k, "kwargs": kwargs},
            ) from e

        logger.debug(
            "IndianaJones.execute_search completed: response_len=%d used_sources=%d",
            len(result.response),
            len(result.used_source_ids),
        )
        return result


RetrieveManager = IndianaJones
