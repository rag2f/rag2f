"""ATeam beta plugin overrides used by integration tests."""

from rag2f.core.dto import AgentRunResult
from rag2f.core.morpheus.decorators.plugin_decorator import plugin


class BetaRawAgent:
    """Provider-specific mock object for raw access tests."""

    def __init__(self, name: str):
        """Store a stable provider name for assertions."""
        self.name = name


class BetaAgentAdapter:
    """Simple sync/async adapter registered by the beta plugin."""

    def __init__(self):
        """Create the adapter and its raw agent."""
        self._raw = BetaRawAgent("beta-raw")

    @property
    def raw(self):
        """Return the underlying raw mock object."""
        return self._raw

    @property
    def metadata(self) -> dict[str, str]:
        """Return lightweight adapter metadata."""
        return {"adapter": "beta", "mode": "reviewer"}

    def run(self, request, *, rag2f):
        """Return a normalized result containing the resolved prompt."""
        return AgentRunResult.success(
            output={
                "agent": "beta",
                "purpose": request.purpose,
                "prompt": request.prompt.text,
            },
            raw_response={"provider": self._raw.name, "prompt": request.prompt.text},
        )

    async def run_async(self, request, *, rag2f):
        """Mirror sync behavior for async execution."""
        return self.run(request, rag2f=rag2f)


@plugin
def activated(plugin, rag2f_instance):
    """Register the beta agent as the plugin default."""
    key = "a_team_beta_plugin.reviewer"
    if rag2f_instance.a_team.has(key):
        return

    rag2f_instance.a_team.register(
        key,
        BetaAgentAdapter(),
        plugin_id=plugin.id,
        metadata={"registered_by": plugin.id},
    )


@plugin
def deactivated(plugin, rag2f_instance):
    """Remove the beta agent during plugin deactivation."""
    rag2f_instance.a_team.unregister("a_team_beta_plugin.reviewer")
