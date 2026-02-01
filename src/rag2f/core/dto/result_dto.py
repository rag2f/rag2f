"""Base result types for RAG2F operations.

Provides a consistent pattern for returning operation results across all
RAG2F modules. Expected states (empty input, duplicates, etc.) are returned
as Result with status="error", while system errors (backend crash, timeout)
raise exceptions.

This design:
- Minimizes overhead for frequent expected states (no stack trace creation)
- Provides type-safe, inspectable results (IDE/AI sees exact fields)
- Maintains consistency across Johnny5, IndianaJones, XFiles
"""

from typing import Any, Final, Literal, Self

from pydantic import BaseModel, Field


class StatusDetail(BaseModel):
    """Structured status information for operation results.

    Used for both error and partial success states. The hook/caller decides
    whether the status represents success or error.

    Attributes:
        code: Machine-readable status code (e.g., "empty", "duplicate", "partial").
        message: Human-readable status description.
        context: Additional diagnostic data (safe to log/serialize).
    """

    code: str = Field(description="Status code: 'empty', 'duplicate', 'partial', etc.")
    message: str = Field(description="Human-readable status description")
    context: dict[str, Any] = Field(default_factory=dict, description="Diagnostic context")


class BaseResult(BaseModel):
    """Base class for all RAG2F operation results.

    Pattern:
    - status="success" → operation succeeded, specific fields populated
    - status="error" → expected failure, error field contains details

    Use is_ok()/is_error() for clear status checks.
    Subclasses add operation-specific fields (track_id, items, rows, etc.).

    Example:
        >>> result = johnny5.handle_text_foreground(text)
        >>> if result.is_ok():
        ...     print(f"Track ID: {result.track_id}")
        >>> else:
        ...     print(f"Error [{result.detail.code}]: {result.detail.message}")
    """

    status: Literal["success", "error"] = Field(default="success", description="Operation status")
    detail: StatusDetail | None = Field(
        default=None, description="Status details (present for error or partial success)"
    )

    model_config = {"extra": "forbid"}

    def is_ok(self) -> bool:
        """Check if operation succeeded."""
        return self.status == "success"

    def is_error(self) -> bool:
        """Check if operation failed with expected error."""
        return self.status == "error"

    @classmethod
    def success(cls, *, detail: StatusDetail | None = None, **kwargs: Any) -> Self:
        """Factory method for successful result.

        Args:
            detail: Optional status details for partial success or informational status.
            **kwargs: Subclass-specific fields.

        Returns:
            Result instance with status="success".

        Example:
            >>> # Full success
            >>> InsertResult.success(track_id="abc123")
            >>> # Partial success with detail
            >>> InsertResult.success(
            ...     track_id="abc123",
            ...     detail=StatusDetail(code="duplicate_merged", message="Merged")
            ... )
        """
        return cls(status="success", detail=detail, **kwargs)

    @classmethod
    def fail(
        cls,
        detail: StatusDetail,
        **kwargs: Any,
    ) -> Self:
        """Factory method for expected failure result.

        Args:
            detail: Required status details describing the failure.
            **kwargs: Subclass-specific fields (use defaults).

        Returns:
            Result instance with status="error".

        Example:
            >>> InsertResult.fail(StatusDetail(
            ...     code=StatusCode.EMPTY,
            ...     message="Input is empty"
            ... ))
        """
        return cls(status="error", detail=detail, **kwargs)


# =============================================================================
# STATUS CODE REGISTRY
# =============================================================================


class StatusCode:
    """Centralized registry of status codes used across RAG2F.

    Use these constants instead of magic strings to ensure consistency
    and enable IDE autocomplete.

    Example:
        >>> result = InsertResult.fail(StatusDetail(
        ...     code=StatusCode.EMPTY,
        ...     message="Input is empty"
        ... ))
        >>> if result.detail.code == StatusCode.DUPLICATE:
        ...     handle_duplicate()
    """

    # -------------------------------------------------------------------------
    # Common (all modules)
    # -------------------------------------------------------------------------
    EMPTY: Final = "empty"
    """[Common] Input or query is empty/whitespace-only."""

    INVALID: Final = "invalid"
    """[Common] Invalid parameter, ID, or configuration."""

    NOT_FOUND: Final = "not_found"
    """[Common] Requested resource not found (expected state, not error)."""

    PARTIAL: Final = "partial"
    """[Common] Operation partially completed."""

    # -------------------------------------------------------------------------
    # Johnny5 (input processing)
    # -------------------------------------------------------------------------
    DUPLICATE: Final = "duplicate"
    """[Johnny5] Input already processed (exact duplicate detected)."""

    DUPLICATE_MERGED: Final = "duplicate_merged"
    """[Johnny5] Input merged with existing document (partial success)."""

    NOT_HANDLED: Final = "not_handled"
    """[Johnny5] No hook handled the input."""

    # -------------------------------------------------------------------------
    # IndianaJones (retrieval/search)
    # -------------------------------------------------------------------------
    NO_RESULTS: Final = "no_results"
    """[IndianaJones] Query returned no matching items."""

    DEGRADED: Final = "degraded"
    """[IndianaJones] Response partially degraded (e.g., formatting failed)."""

    # -------------------------------------------------------------------------
    # XFiles (repository management)
    # -------------------------------------------------------------------------
    CACHE_MISS: Final = "cache_miss"
    """[XFiles] Cache lookup missed (explicit cache request failed)."""

    ALREADY_EXISTS: Final = "already_exists"
    """[XFiles] Resource already exists with different instance."""

    INVALID_SPEC: Final = "invalid_spec"
    """[XFiles] Invalid query specification."""

    PARTIAL_RESULTS: Final = "partial_results"
    """[XFiles] Query returned partial results (some repos failed)."""


__all__ = ["BaseResult", "StatusDetail", "StatusCode"]
