"""Errors for the FluxCapacitor task system."""


class FluxCapacitorError(Exception):
    """Base class for FluxCapacitor errors."""


class MissingStoreError(FluxCapacitorError):
    """Raised when a requested task store is missing."""


class MissingQueueError(FluxCapacitorError):
    """Raised when a requested task queue is missing."""


class HookResolutionError(FluxCapacitorError):
    """Raised when a hook cannot be resolved for a task."""
