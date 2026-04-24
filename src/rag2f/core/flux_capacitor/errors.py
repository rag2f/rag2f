"""Errors for the FluxCapacitor task system."""


class FluxCapacitorError(Exception):
    """Base class for FluxCapacitor errors."""

    def __init__(self, message: str, *, context: dict | None = None):
        """Initialize the exception.

        Args:
            message: Error description.
            context: Optional diagnostic context for tracing.
        """
        super().__init__(message)
        self.context = context or {}


class TaskRegistrationError(FluxCapacitorError):
    """Raised when a store or queue registration operation fails."""


class MissingStoreError(FluxCapacitorError):
    """Raised when a requested task store is missing."""


class MissingQueueError(FluxCapacitorError):
    """Raised when a requested task queue is missing."""


class TaskResolutionError(FluxCapacitorError):
    """Raised when a task or parent task cannot be resolved."""


class HookResolutionError(FluxCapacitorError):
    """Raised when a hook cannot be resolved for a task."""
