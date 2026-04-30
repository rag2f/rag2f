"""DTOs for IndianaJones retrieval and search operations.

Core types for RAG retrieval and synthesis. Expected states (empty query, etc.)
return status="error". System errors (backend crash) raise exceptions.
"""

from collections.abc import Mapping
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from rag2f.core.dto.result_dto import BaseResult


class ReturnMode(StrEnum):
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


class RetrieveResult(BaseResult):
    """Result of a retrieve() operation.

    [Result Pattern] Check result.is_ok() before using fields.

    Attributes:
        status: "success" if retrieval succeeded, "error" otherwise.
        query: The original query string.
        items: List of retrieved items, ordered by relevance.
        extra: Plugin extension point for additional data.
        detail: Status details if status="error".

    Example:
        >>> result = indiana.retrieve("how does X work?", k=5)
        >>> if result.is_ok():
        ...     for item in result.items:
        ...         print(item.text[:100])
        >>> else:
        ...     print(f"Error [{result.detail.code}]: {result.detail.message}")
    """

    query: str = Field(default="", description="Original query string")
    items: list[RetrievedItem] = Field(
        default_factory=list, description="Retrieved items ordered by relevance"
    )
    extra: dict[str, Any] = Field(default_factory=dict, description="Plugin extension point")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dictionary."""
        return self.model_dump()


class SearchResult(BaseResult):
    """Result of a search() operation (retrieval + synthesis).

    [Result Pattern] Check result.is_ok() before using fields.

    Attributes:
        status: "success" if search succeeded, "error" otherwise.
        query: The original query string.
        response: The synthesized answer.
        used_source_ids: IDs of sources used in the response.
        items: Retrieved items (populated only when requested via return_mode).
        extra: Plugin extension point for additional data.
        detail: Status details if status="error".

    Example:
        >>> result = indiana.search("how does X work?", k=5)
        >>> if result.is_ok():
        ...     print(result.response)
        >>> else:
        ...     print(f"Error [{result.detail.code}]: {result.detail.message}")
    """

    query: str = Field(default="", description="Original query string")
    response: str = Field(default="", description="Synthesized answer")
    used_source_ids: list[str] = Field(
        default_factory=list, description="IDs of sources used in the response"
    )
    items: list[RetrievedItem] | None = Field(
        default=None, description="Retrieved items (when requested)"
    )
    extra: dict[str, Any] = Field(default_factory=dict, description="Plugin extension point")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dictionary."""
        return self.model_dump()


class SubQuestionResult(BaseModel):
    """A single sub-question paired with its retrieve result.

    Produced during multi-step search to hold per-sub-question evidence.

    Attributes:
        sub_question: The planned sub-question string.
        retrieve_result: Retrieval outcome for this sub-question.
    """

    sub_question: str = Field(description="The planned sub-question")
    retrieve_result: RetrieveResult = Field(description="Retrieval result for this sub-question")

    model_config = {"extra": "forbid"}


class MultiStepSearchResult(BaseResult):
    """Result of a multi_step_search operation.

    [Result Pattern] Check result.is_ok() before using fields.

    Pipeline: plan sub-questions → retrieve per sub-question → synthesize.

    Attributes:
        status: "success" if the search succeeded, "error" otherwise.
        query: The original compound query string.
        response: Synthesized final answer.
        used_source_ids: IDs of sources referenced in the final response.
        sub_question_results: Per-sub-question retrieve results.
        items: All retrieved items across sub-questions (populated only with
            ReturnMode.WITH_ITEMS).
        extra: Plugin extension point.
        detail: Status details if status="error".

    Example:
        >>> result = indiana.execute_multi_step_search("What is X and how does Y work?")
        >>> if result.is_ok():
        ...     print(result.response)
        ...     for sq in result.sub_question_results:
        ...         print(sq.sub_question, len(sq.retrieve_result.items))
        >>> else:
        ...     print(f"Error [{result.detail.code}]: {result.detail.message}")
    """

    query: str = Field(default="", description="Original compound query string")
    response: str = Field(default="", description="Synthesized final answer")
    used_source_ids: list[str] = Field(
        default_factory=list, description="Source IDs referenced in the final response"
    )
    sub_question_results: list[SubQuestionResult] = Field(
        default_factory=list, description="Per-sub-question retrieve results"
    )
    items: list[RetrievedItem] | None = Field(
        default=None, description="All retrieved items (when requested via return_mode)"
    )
    extra: dict[str, Any] = Field(default_factory=dict, description="Plugin extension point")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dictionary."""
        return self.model_dump()
