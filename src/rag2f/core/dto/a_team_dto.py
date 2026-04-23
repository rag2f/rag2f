"""ATeam DTOs.

Defines lightweight prompt and execution DTOs used by the ATeam manager.
"""

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field

from rag2f.core.dto.result_dto import BaseResult


@dataclass(slots=True)
class PromptContext:
    """Context passed through prompt-building hooks."""

    agent_key: str | None = None
    plugin_id: str | None = None
    caller: str | None = None
    caller_plugin_id: str | None = None
    caller_hook: str | None = None
    purpose: str | None = None
    prompt_version: str | None = None
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PromptFragment:
    """Single prompt fragment contributed by a plugin hook."""

    text: str
    plugin_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ResolvedPrompt:
    """Final prompt resolved before agent execution."""

    text: str = ""
    fragments: list[PromptFragment] = field(default_factory=list)
    context: PromptContext | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentRunRequest(BaseModel):
    """Minimal request object for ATeam agent execution."""

    input: str | None = Field(default=None, description="Base user input for prompt assembly")
    agent_key: str | None = Field(default=None, description="Explicit agent key override")
    plugin_id: str | None = Field(default=None, description="Plugin scope for default resolution")
    caller: str | None = Field(default=None, description="Caller identity for hooks")
    caller_plugin_id: str | None = Field(
        default=None,
        description="Calling plugin id when execution originates from plugin code",
    )
    caller_hook: str | None = Field(
        default=None,
        description="Calling hook name when execution originates from a Morpheus hook",
    )
    purpose: str | None = Field(default=None, description="Purpose used to resolve prompts")
    prompt_version: str | None = Field(default=None, description="Prompt variant identifier")
    params: dict[str, Any] = Field(default_factory=dict, description="Hook-visible parameters")
    prompt: ResolvedPrompt | None = Field(default=None, description="Pre-resolved prompt")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Opaque request metadata")

    model_config = {"extra": "forbid"}


class AgentRunResult(BaseResult):
    """Result of executing an ATeam agent."""

    agent_key: str = Field(default="", description="Resolved agent key")
    plugin_id: str = Field(default="", description="Owner plugin id")
    output: Any = Field(default=None, description="Normalized adapter output")
    prompt: ResolvedPrompt | None = Field(default=None, description="Resolved prompt used")
    raw_response: Any = Field(default=None, description="Original adapter/provider response")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Execution metadata")


__all__ = [
    "AgentRunRequest",
    "AgentRunResult",
    "PromptContext",
    "PromptFragment",
    "ResolvedPrompt",
]
