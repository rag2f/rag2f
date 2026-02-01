"""DTOs for Johnny5 input processing.

InsertResult represents the outcome of input processing operations.
Expected states (empty, duplicate, not_handled) return status="error".
"""

from pydantic import Field

from rag2f.core.dto.result_dto import BaseResult


class InsertResult(BaseResult):
    """Result of Johnny5 input processing operations.

    [Result Pattern] Check result.is_ok() before using fields.

    Attributes:
        status: "success" if input was processed, "error" otherwise.
        track_id: Tracking ID for the processed input (empty if error).
        detail: Status details if status="error".

    Example:
        >>> result = johnny5.handle_text_foreground(text)
        >>> if result.is_ok():
        ...     print(f"Processed with ID: {result.track_id}")
        >>> else:
        ...     print(f"Failed [{result.detail.code}]: {result.detail.message}")
    """

    track_id: str = Field(default="", description="Tracking ID (empty if error)")
