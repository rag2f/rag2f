"""Functional tests for the ATeam manager."""

import pytest
from tests.utils import PATH_MOCK

from rag2f.core.a_team import AgentExecutionError, AgentPromptError, AgentResolutionError
from rag2f.core.dto import AgentRunRequest
from rag2f.core.rag2f import RAG2F

PATH_A_TEAM_PLUGINS = f"{PATH_MOCK}/plugins/"


@pytest.mark.asyncio
async def test_a_team_resolves_defaults_from_plugins_and_spock():
    """ATeam should expose plugin and global defaults plus raw agent access."""
    rag2f = await RAG2F.create(
        plugins_folder=PATH_A_TEAM_PLUGINS,
        config={
            "rag2f": {"a_team_default": "a_team_beta_plugin.reviewer"},
            "plugins": {"a_team_alpha_plugin": {"default_agent": "a_team_alpha_plugin.writer"}},
        },
    )

    assert rag2f.agent_manager is rag2f.a_team
    assert rag2f.a_team.get_default("a_team_alpha_plugin") is rag2f.a_team.get(
        "a_team_alpha_plugin.writer"
    )
    assert rag2f.a_team.get_default() is rag2f.a_team.get("a_team_beta_plugin.reviewer")

    raw_agent = rag2f.a_team.get_raw("a_team_alpha_plugin.writer")
    assert raw_agent is not None
    assert raw_agent.name == "alpha-raw"


@pytest.mark.asyncio
async def test_a_team_executes_selected_agents_with_ordered_prompt_hooks():
    """ATeam should execute different agents and compose prompts through ordered hooks."""
    rag2f = await RAG2F.create(plugins_folder=PATH_A_TEAM_PLUGINS)

    draft_result = rag2f.a_team.execute_run(
        AgentRunRequest(
            input="Prepare release notes for the async rollout.",
            plugin_id="a_team_alpha_plugin",
            purpose="draft",
            caller="tests.core.test_a_team",
        )
    )

    assert draft_result.is_ok()
    assert draft_result.agent_key == "a_team_alpha_plugin.writer"
    assert draft_result.output["agent"] == "alpha"
    assert draft_result.prompt is not None
    assert "Prepare release notes for the async rollout." in draft_result.prompt.text
    assert "Alpha instruction: write the first draft" in draft_result.prompt.text
    assert (
        "Beta constraint: add risks, edge cases, and a review checklist."
        in draft_result.prompt.text
    )
    assert draft_result.prompt.text.index("Alpha instruction") < draft_result.prompt.text.index(
        "Beta constraint"
    )

    review_result = await rag2f.a_team.execute_run_async(
        AgentRunRequest(
            input="Review the release notes for production readiness.",
            agent_key="a_team_beta_plugin.reviewer",
            purpose="review",
            caller="tests.core.test_a_team",
        )
    )

    assert review_result.is_ok()
    assert review_result.agent_key == "a_team_beta_plugin.reviewer"
    assert review_result.output["agent"] == "beta"
    assert review_result.prompt is not None
    assert (
        "Beta review focus: critique correctness, gaps, and operational risk."
        in review_result.prompt.text
    )
    assert review_result.prompt.text.endswith("Final mode: review")


@pytest.mark.asyncio
async def test_a_team_explicit_agent_key_overrides_plugin_default_scope():
    """Explicit agent keys should win over plugin-scoped defaults."""
    rag2f = await RAG2F.create(plugins_folder=PATH_A_TEAM_PLUGINS)

    result = rag2f.a_team.execute_run(
        AgentRunRequest(
            input="Review this deployment checklist.",
            agent_key="a_team_beta_plugin.reviewer",
            plugin_id="a_team_alpha_plugin",
            purpose="review",
            caller="tests.core.test_a_team",
        )
    )

    assert result.is_ok()
    assert result.agent_key == "a_team_beta_plugin.reviewer"
    assert result.output["agent"] == "beta"


@pytest.mark.asyncio
async def test_a_team_plugin_lifecycle_unregisters_and_restores_agents():
    """Plugin deactivate/activate should keep ATeam registry state coherent."""
    rag2f = await RAG2F.create(plugins_folder=PATH_A_TEAM_PLUGINS)
    plugin = rag2f.morpheus.plugins["a_team_beta_plugin"]

    plugin.deactivate()

    assert not rag2f.a_team.has("a_team_beta_plugin.reviewer")
    with pytest.raises(AgentResolutionError, match="No default agent configured for plugin"):
        rag2f.a_team.get_default("a_team_beta_plugin")

    plugin.activate()

    assert rag2f.a_team.has("a_team_beta_plugin.reviewer")
    assert rag2f.a_team.get_default("a_team_beta_plugin") is rag2f.a_team.get(
        "a_team_beta_plugin.reviewer"
    )


@pytest.mark.asyncio
async def test_a_team_wraps_invalid_prompt_pipeline_with_module_exception(monkeypatch):
    """Broken prompt hooks should raise AgentPromptError with local context."""
    rag2f = await RAG2F.create(plugins_folder=PATH_A_TEAM_PLUGINS)
    original_execute_hook = rag2f.morpheus.execute_hook

    def broken_execute_hook(hook_name, *args, rag2f):
        if hook_name == "agent_collect_prompt_fragments":
            return "broken"
        return original_execute_hook(hook_name, *args, rag2f=rag2f)

    monkeypatch.setattr(rag2f.morpheus, "execute_hook", broken_execute_hook)

    with pytest.raises(AgentPromptError, match="Prompt fragment hooks must return a list"):
        rag2f.a_team.execute_run(
            AgentRunRequest(
                input="Prepare the prompt pipeline.",
                plugin_id="a_team_alpha_plugin",
                purpose="draft",
                caller="tests.core.test_a_team",
            )
        )


@pytest.mark.asyncio
async def test_a_team_wraps_adapter_failures_with_module_exception():
    """Adapter runtime failures should be wrapped in AgentExecutionError."""
    rag2f = await RAG2F.create(plugins_folder=PATH_A_TEAM_PLUGINS)

    class FailingAdapter:
        @property
        def raw(self):
            return {"provider": "failing"}

        @property
        def metadata(self):
            return {"adapter": "failing"}

        def run(self, request, *, rag2f):
            raise RuntimeError("sync boom")

        async def run_async(self, request, *, rag2f):
            raise RuntimeError("async boom")

    rag2f.a_team.register(
        "manual_plugin.failing",
        FailingAdapter(),
        plugin_id="manual_plugin",
    )

    with pytest.raises(AgentExecutionError, match="manual_plugin.failing") as exc_info:
        rag2f.a_team.execute_run(
            AgentRunRequest(
                input="Trigger failing execution.",
                agent_key="manual_plugin.failing",
                purpose="draft",
                caller="tests.core.test_a_team",
            )
        )

    assert exc_info.value.context["agent_key"] == "manual_plugin.failing"
