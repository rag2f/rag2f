"""IndianaJones retrieve manager.

IndianaJones handles RAG retrieval and search operations with extensible
backends and plugin enrichment.

"Fortune and glory, kid. Fortune and glory."
"""

import logging
from typing import Any

from rag2f.core.dto.indiana_jones_dto import (
    RetrieveResult,
    ReturnMode,
    SearchResult,
)
from rag2f.core.indiana_jones.exceptions import (
    RetrievalError,
)

logger = logging.getLogger(__name__)


class IndianaJones:
    """RAG retrieval and search orchestrator.

    Coordinates retrieval backends, generator backends, attribution strategies,
    and plugin enrichment to provide a complete RAG pipeline.

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

    def retrieve(self, query: str, k: int = 10, **kwargs: Any) -> RetrieveResult:
        """Retrieve relevant items for a query.

        Args:
            query: The search query string.
            k: Maximum number of items to retrieve.
            **kwargs: Backend-specific parameters.

        Returns:
            RetrieveResult containing the query and retrieved items.

        Raises:
            RetrievalError: If retrieval fails.
        """
        logger.debug("IndianaJones.retrieve query=%r k=%d", query, k)
        if query is None or not str(query).strip():
            raise RetrievalError(
                "Retrieval failed: query is empty",
                context={"query": query, "k": k, "kwargs": kwargs},
            )
        try:
            result = RetrieveResult(query=query)
            if self.rag2f:
                result = self.rag2f.morpheus.execute_hook(
                    "indiana_jones_retrieve", result, query, k, rag2f=self.rag2f
                )
        except Exception as e:
            logger.error("IndianaJones retrieval failed: %s", e)
            raise RetrievalError(
                f"Retrieval failed: {e}",
                context={"query": query, "k": k, "kwargs": kwargs},
            ) from e

        logger.debug("IndianaJones.retrieve returned %d items", len(result.items))
        return result

    def search(
        self,
        query: str,
        k: int = 10,
        return_mode: ReturnMode = ReturnMode.MINIMAL,
        **kwargs: Any,
    ) -> SearchResult:
        """Retrieve and synthesize a response for a query.

        Args:
            query: The search query string.
            k: Maximum number of items to retrieve.
            return_mode: Controls what data is included in the result.
            **kwargs: Backend-specific parameters.

        Returns:
            SearchResult containing the synthesized response and attribution.

        Raises:
            RetrievalError: If retrieval fails.
        """

        logger.debug(
            "IndianaJones.search query=%r k=%d return_mode=%s", query, k, return_mode.value
        )

        if query is None or not str(query).strip():
            raise RetrievalError(
                "Retrieval failed: query is empty",
                context={"query": query, "k": k, "kwargs": kwargs},
            )

        result = SearchResult(query=query)

        if self.rag2f:
            result = self.rag2f.morpheus.execute_hook(
                "indiana_jones_search", result, query, k, return_mode, kwargs, rag2f=self.rag2f
            )

        logger.debug(
            "IndianaJones.search completed: response_len=%d used_sources=%d",
            len(result.response),
            len(result.used_source_ids),
        )
        return result


RetrieveManager = IndianaJones
