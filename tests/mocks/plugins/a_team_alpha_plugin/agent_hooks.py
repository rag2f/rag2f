"""ATeam alpha hooks used by integration tests."""

from rag2f.core.dto import PromptFragment
from rag2f.core.morpheus.decorators import hook


@hook("agent_collect_prompt_fragments", priority=20)
def provide_writer_prompt(fragments, context, rag2f):
    """Provide the base writing instruction before lower-priority hooks."""
    if context.purpose == "draft":
        fragments.append(
            PromptFragment(
                text="Alpha instruction: write the first draft with a concise structure.",
                plugin_id="a_team_alpha_plugin",
            )
        )
    return fragments
