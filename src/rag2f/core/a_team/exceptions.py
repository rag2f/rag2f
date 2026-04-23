"""Exception classes for ATeam agent orchestration."""


class ATeamError(Exception):
    """Base exception for all ATeam system errors."""

    def __init__(self, message: str, *, context: dict | None = None):
        """Initialize the exception.

        Args:
            message: Error description.
            context: Optional diagnostic context for tracing.
        """
        super().__init__(message)
        self.context = context or {}


class AgentRegistrationError(ATeamError):
    """Error during agent registration or unregistration."""


class AgentResolutionError(ATeamError):
    """Error while resolving an agent key or default."""


class AgentPromptError(ATeamError):
    """Error while collecting or finalizing an agent prompt."""


class AgentExecutionError(ATeamError):
    """Error while executing an agent adapter."""
