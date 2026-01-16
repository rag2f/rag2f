"""DTOs for Johnny5 input processing."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class InsertResult(BaseModel):
    """Result model for document insertion operations.

    Attributes:
        status: Status of the operation (success, duplicated, partial_success, failure)
        message: Detailed message describing the operation result
        track_id: Tracking ID for monitoring processing status
    """

    status: Literal["success", "duplicated", "partial_success", "failure"] = Field(
        description="Status of the operation"
    )
    message: str | None = Field(
        default=None, description="Message describing the operation result"
    )
    track_id: str | None = Field(
        default=None, description="Tracking ID for monitoring processing status"
    )

    model_config = ConfigDict(extra="allow")
