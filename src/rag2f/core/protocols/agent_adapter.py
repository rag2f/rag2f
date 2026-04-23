"""Agent adapter protocol definitions.

This module defines the minimal protocol used by ATeam to execute agents
registered by plugins without coupling the core to any provider SDK.
"""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class AgentAdapter(Protocol):
    """Structural interface for agent adapters registered in ATeam."""

    @property
    def raw(self) -> Any:
        """Return the underlying provider-specific agent object."""
        ...

    @property
    def metadata(self) -> dict[str, Any]:
        """Return lightweight adapter metadata when available."""
        ...

    def run(self, request, *, rag2f) -> Any:
        """Execute the agent synchronously."""
        ...

    async def run_async(self, request, *, rag2f) -> Any:
        """Execute the agent asynchronously."""
        ...
