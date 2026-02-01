"""Exception classes for Johnny5 input operations.

These exceptions are for SYSTEM errors only (bugs, invariant violations).
Expected states (empty, duplicate, not_handled) are returned as InsertResult
with status="error" - see dto/johnny5_dto.py.
"""


class Johnny5Error(Exception):
    """Base exception for Johnny5 system errors."""

    def __init__(self, message: str, *, context: dict | None = None):
        """Initialize the exception.

        Args:
            message: Error description.
            context: Optional diagnostic context for tracing.
        """
        super().__init__(message)
        self.context = context or {}


class PluginError(Johnny5Error):
    """Error during plugin hook execution phase.

    Raised when a plugin hook fails while processing input.
    """

    def __init__(self, message: str, *, hook_name: str | None = None, context: dict | None = None):
        """Initialize the exception.

        Args:
            message: Error description.
            hook_name: Name of the hook that failed.
            context: Optional diagnostic context for tracing.
        """
        super().__init__(message, context=context)
        self.hook_name = hook_name
