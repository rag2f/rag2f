"""DTOs for Johnny5 input processing."""

from typing import Literal

from pydantic import BaseModel, Field


class InsertResponse(BaseModel):
    """Response model for document insertion operations.

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

    class Config:
        """Pydantic model configuration."""

        extra = "allow"
        json_schema_extra = {
            "example": {
                "status": "success",
                "message": "File 'document.pdf' uploaded successfully. Processing will continue in background.",
                "track_id": "upload_20250729_170612_abc123",
                "custom_field": "any value",
            }
        }
