"""Exception classes for IndianaJones RAG operations."""


class IndianaJonesError(Exception):
    """Base exception for all IndianaJones errors."""

    def __init__(self, message: str, *, context: dict | None = None):
        """Initialize the exception.

        Args:
            message: Error description.
            context: Optional diagnostic context for tracing.
        """
        super().__init__(message)
        self.context = context or {}


class RetrievalError(IndianaJonesError):
    """Error during retrieval phase."""

    pass


class PluginError(IndianaJonesError):
    """Error during plugin enrichment phase.

    Raised when a plugin fails while enriching results.
    """

    def __init__(
        self, message: str, *, plugin_name: str | None = None, context: dict | None = None
    ):
        """Initialize the exception.

        Args:
            message: Error description.
            plugin_name: Name of the plugin that failed.
            context: Optional diagnostic context for tracing.
        """
        super().__init__(message, context=context)
        self.plugin_name = plugin_name
