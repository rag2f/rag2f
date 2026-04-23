"""ATeam beta hooks used by integration tests."""

from rag2f.core.dto import PromptFragment
from rag2f.core.morpheus.decorators import hook


@hook("agent_collect_prompt_fragments", priority=10)
def add_review_constraints(fragments, context, rag2f):
    """Append lower-priority constraints after the writer prompt."""
    if context.purpose == "draft":
        fragments.append(
            PromptFragment(
                text="Beta constraint: add risks, edge cases, and a review checklist.",
                plugin_id="a_team_beta_plugin",
            )
        )
    elif context.purpose == "review":
        fragments.append(
            PromptFragment(
                text="Beta review focus: critique correctness, gaps, and operational risk.",
                plugin_id="a_team_beta_plugin",
            )
        )
    return fragments


@hook("agent_finalize_prompt", priority=5)
def finalize_prompt(resolved_prompt, context, rag2f):
    """Finalize the prompt text after all fragments are collected."""
    resolved_prompt.text = resolved_prompt.text.strip()
    if context.purpose == "review":
        resolved_prompt.text = f"{resolved_prompt.text}\n\nFinal mode: review"
    return resolved_prompt
