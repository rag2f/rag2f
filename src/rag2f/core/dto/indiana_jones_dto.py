"""DTOs for IndianaJones retrieval and search operations.

Core types for RAG retrieval and synthesis. All types support extensibility
via the `extra` dict field for plugin enrichment.
"""

from collections.abc import Mapping
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ReturnMode(str, Enum):
    """Control what data is returned from search operations.

    Attributes:
        MINIMAL: Response and used_source_ids only.
        WITH_ITEMS: Response, used_source_ids, and items.
    """

    MINIMAL = "minimal"
    WITH_ITEMS = "with_items"


class RetrievedItem(BaseModel):
    """A single retrieved chunk/document.

    Attributes:
        id: Stable identifier for the chunk/document.
        text: The passage text content.
        metadata: Loader/user metadata attached to the item.
        score: Optional relevance score from the retriever.
        extra: Plugin extension point for additional data.
    """

    id: str = Field(description="Stable identifier for chunk/doc")
    text: str = Field(description="Passage text")
    metadata: Mapping[str, Any] = Field(default_factory=dict, description="Loader/user metadata")
    score: float | None = Field(default=None, description="Optional relevance score")
    extra: dict[str, Any] = Field(default_factory=dict, description="Plugin extension point")

    model_config = {"extra": "forbid"}

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dictionary."""
        return self.model_dump()


class RetrieveResult(BaseModel):
    """Result of a retrieve() operation.

    Attributes:
        query: The original query string.
        items: List of retrieved items, ordered by relevance.
        extra: Plugin extension point for additional data.
    """

    query: str = Field(description="Original query string")
    items: list[RetrievedItem] = Field(
        default_factory=list, description="Retrieved items ordered by relevance"
    )
    extra: dict[str, Any] = Field(default_factory=dict, description="Plugin extension point")

    model_config = {"extra": "forbid"}

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dictionary."""
        return self.model_dump()


class SearchResult(BaseModel):
    """Result of a search() operation (retrieval + synthesis).

    Attributes:
        query: The original query string.
        response: The synthesized answer.
        used_source_ids: IDs of sources used in the response.
        items: Retrieved items (populated only when requested via return_mode).
        extra: Plugin extension point for additional data.
    """

    query: str = Field(description="Original query string")
    response: str = Field(default="", description="Synthesized answer")
    used_source_ids: list[str] = Field(
        default_factory=list, description="IDs of sources used in the response"
    )
    items: list[RetrievedItem] | None = Field(
        default=None, description="Retrieved items (when requested)"
    )
    extra: dict[str, Any] = Field(default_factory=dict, description="Plugin extension point")

    model_config = {"extra": "forbid"}

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dictionary."""
        return self.model_dump()
