"""Exception classes for Johnny5 input operations.

Explicit exception hierarchy for input handling and plugin errors.
"""


class Johnny5Error(Exception):
    """Base exception for all Johnny5 errors."""

    def __init__(self, message: str, *, context: dict | None = None):
        """Initialize the exception.

        Args:
            message: Error description.
            context: Optional diagnostic context for tracing.
        """
        super().__init__(message)
        self.context = context or {}


class InsertError(Johnny5Error):
    """Error during input insertion/handling phase.

    Raised when text input processing fails.
    """

    pass


class DuplicateInputError(Johnny5Error):
    """Error when input is detected as duplicate.

    Raised when input text has already been processed.
    """

    pass


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
