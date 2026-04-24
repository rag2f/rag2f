"""ATeam - Agent registry and execution manager for RAG2F."""

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from rag2f.core.a_team.exceptions import (
    AgentExecutionError,
    AgentPromptError,
    AgentRegistrationError,
    AgentResolutionError,
    ATeamError,
)
from rag2f.core.dto.a_team_dto import (
    AgentRunRequest,
    AgentRunResult,
    PromptContext,
    PromptFragment,
    ResolvedPrompt,
)
from rag2f.core.protocols import AgentAdapter

if TYPE_CHECKING:
    from rag2f.core.rag2f import RAG2F
    from rag2f.core.spock.spock import Spock


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AgentEntry:
    """Internal registry entry for an agent adapter."""

    key: str
    plugin_id: str
    adapter: AgentAdapter
    raw: Any
    metadata: dict[str, Any] = field(default_factory=dict)


class ATeam:
    """Plugin-first agent registry and execution manager."""

    def __init__(self, *, rag2f_instance: "RAG2F", spock: "Spock | None" = None):
        """Initialize the agent manager."""
        self._rag2f_instance = rag2f_instance
        self._registry: dict[str, AgentEntry] = {}
        self._plugin_defaults: dict[str, str] = {}
        self._spock = spock
        logger.debug("ATeam instance created.")

    def register(
        self,
        key: str,
        adapter: AgentAdapter,
        *,
        plugin_id: str,
        raw: Any = None,
        metadata: dict[str, Any] | None = None,
        is_default: bool = False,
    ) -> None:
        """Register an agent adapter with ownership metadata."""
        if not isinstance(key, str) or not key.strip():
            raise AgentRegistrationError(
                f"Invalid agent key: {key!r}",
                context={"key": key, "plugin_id": plugin_id},
            )
        if not isinstance(plugin_id, str) or not plugin_id.strip():
            raise AgentRegistrationError(
                f"Invalid plugin_id for agent registration: {plugin_id!r}",
                context={"key": key, "plugin_id": plugin_id},
            )
        if not isinstance(adapter, AgentAdapter):
            raise AgentRegistrationError(
                f"Agent '{key}' does not implement the AgentAdapter protocol",
                context={"key": key, "plugin_id": plugin_id, "type": type(adapter).__name__},
            )

        if key in self._registry:
            if self._registry[key].adapter is adapter:
                logger.warning(
                    "Agent '%s' already registered with the same instance; skipping duplicate registration.",
                    key,
                )
                return
            raise AgentRegistrationError(
                f"Override not allowed for already registered agent: {key!r}",
                context={"key": key, "plugin_id": plugin_id},
            )

        entry_metadata = dict(metadata or {})
        adapter_metadata = getattr(adapter, "metadata", None)
        if isinstance(adapter_metadata, dict):
            entry_metadata = {**adapter_metadata, **entry_metadata}

        entry = AgentEntry(
            key=key,
            plugin_id=plugin_id,
            adapter=adapter,
            raw=raw if raw is not None else adapter.raw,
            metadata=entry_metadata,
        )
        self._registry[key] = entry

        if is_default:
            current_default = self._plugin_defaults.get(plugin_id)
            if current_default is not None and current_default != key:
                raise AgentRegistrationError(
                    f"Plugin '{plugin_id}' already has default agent '{current_default}'.",
                    context={
                        "key": key,
                        "plugin_id": plugin_id,
                        "current_default": current_default,
                    },
                )
            self._plugin_defaults[plugin_id] = key

        logger.debug("Agent '%s' registered for plugin '%s'.", key, plugin_id)

    def get(self, key: str) -> AgentAdapter | None:
        """Return a registered adapter by key."""
        entry = self._registry.get(key)
        return None if entry is None else entry.adapter

    def get_raw(self, key: str) -> Any:
        """Return the raw object registered for the given key."""
        entry = self._registry.get(key)
        return None if entry is None else entry.raw

    def get_default(self, plugin_id: str | None = None) -> AgentAdapter:
        """Return the default adapter for a plugin or for the whole instance."""
        key = self._resolve_default_key(plugin_id=plugin_id)
        adapter = self.get(key)
        if adapter is None:
            raise AgentResolutionError(
                f"Default agent '{key}' is not registered.",
                context={"key": key, "plugin_id": plugin_id},
            )
        return adapter

    def list_keys(self) -> list[str]:
        """Return registered agent keys."""
        return list(self._registry.keys())

    def has(self, key: str) -> bool:
        """Return whether an agent key exists."""
        return key in self._registry

    def unregister(self, key: str) -> bool:
        """Unregister an agent by key."""
        entry = self._registry.get(key)
        if entry is None:
            return False

        del self._registry[key]
        if self._plugin_defaults.get(entry.plugin_id) == key:
            del self._plugin_defaults[entry.plugin_id]
        logger.debug("Agent '%s' unregistered.", key)
        return True

    def execute_run(
        self,
        request: AgentRunRequest,
        *,
        agent_key: str | None = None,
    ) -> AgentRunResult:
        """Execute an agent synchronously."""
        entry = self._resolve_entry(request=request, explicit_agent_key=agent_key)
        resolved_prompt = self._resolve_prompt(request=request, entry=entry)
        bound_request = request.model_copy(
            update={
                "agent_key": entry.key,
                "plugin_id": request.plugin_id or entry.plugin_id,
                "prompt": resolved_prompt,
            }
        )

        logger.debug(
            "Executing agent '%s' for plugin='%s' purpose='%s' caller='%s' caller_hook='%s'.",
            entry.key,
            entry.plugin_id,
            request.purpose,
            request.caller,
            request.caller_hook,
        )
        try:
            response = entry.adapter.run(bound_request, rag2f=self._rag2f_instance)
        except Exception as exc:
            logger.error("ATeam execution failed for agent '%s': %s", entry.key, exc)
            raise AgentExecutionError(
                f"Agent execution failed for '{entry.key}': {exc}",
                context={
                    "agent_key": entry.key,
                    "plugin_id": entry.plugin_id,
                    "purpose": request.purpose,
                    "caller": request.caller,
                    "caller_hook": request.caller_hook,
                },
            ) from exc
        return self._normalize_result(entry=entry, prompt=resolved_prompt, response=response)

    async def execute_run_async(
        self,
        request: AgentRunRequest,
        *,
        agent_key: str | None = None,
    ) -> AgentRunResult:
        """Execute an agent asynchronously."""
        entry = self._resolve_entry(request=request, explicit_agent_key=agent_key)
        resolved_prompt = self._resolve_prompt(request=request, entry=entry)
        bound_request = request.model_copy(
            update={
                "agent_key": entry.key,
                "plugin_id": request.plugin_id or entry.plugin_id,
                "prompt": resolved_prompt,
            }
        )

        logger.debug(
            "Executing async agent '%s' for plugin='%s' purpose='%s' caller='%s' caller_hook='%s'.",
            entry.key,
            entry.plugin_id,
            request.purpose,
            request.caller,
            request.caller_hook,
        )
        try:
            response = await entry.adapter.run_async(bound_request, rag2f=self._rag2f_instance)
        except Exception as exc:
            logger.error("ATeam async execution failed for agent '%s': %s", entry.key, exc)
            raise AgentExecutionError(
                f"Agent async execution failed for '{entry.key}': {exc}",
                context={
                    "agent_key": entry.key,
                    "plugin_id": entry.plugin_id,
                    "purpose": request.purpose,
                    "caller": request.caller,
                    "caller_hook": request.caller_hook,
                },
            ) from exc
        return self._normalize_result(entry=entry, prompt=resolved_prompt, response=response)

    def _resolve_entry(
        self,
        *,
        request: AgentRunRequest,
        explicit_agent_key: str | None,
    ) -> AgentEntry:
        key = (
            explicit_agent_key or request.agent_key or self._resolve_default_key(request.plugin_id)
        )
        entry = self._registry.get(key)
        if entry is None:
            raise AgentResolutionError(
                f"Agent '{key}' is not registered.",
                context={"key": key, "plugin_id": request.plugin_id},
            )
        return entry

    def _resolve_default_key(self, plugin_id: str | None = None) -> str:
        if plugin_id:
            plugin_value = self._resolve_plugin_default(plugin_id)
            if plugin_value:
                return plugin_value

        global_value = self._resolve_global_default()
        if global_value:
            return global_value

        if plugin_id:
            raise AgentResolutionError(
                f"No default agent configured for plugin '{plugin_id}' and no global default set.",
                context={"plugin_id": plugin_id},
            )
        raise AgentResolutionError(
            "No default agent configured. Set 'plugins.<plugin_id>.default_agent' or 'rag2f.a_team_default'.",
            context={},
        )

    def _resolve_plugin_default(self, plugin_id: str) -> str | None:
        configured = None
        if self._spock is not None:
            configured = self._spock.get_plugin_config(plugin_id, "default_agent")
        if isinstance(configured, str) and configured.strip():
            return configured.strip()

        fallback = self._plugin_defaults.get(plugin_id)
        return fallback.strip() if isinstance(fallback, str) and fallback.strip() else None

    def _resolve_global_default(self) -> str | None:
        if self._spock is None:
            return None

        value = self._spock.get_rag2f_config("a_team_default")
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    def _resolve_prompt(self, *, request: AgentRunRequest, entry: AgentEntry) -> ResolvedPrompt:
        try:
            if request.prompt is not None:
                fragments = list(request.prompt.fragments)
                metadata = dict(request.prompt.metadata)
                prompt_text = request.prompt.text
            else:
                fragments = []
                metadata = {}
                prompt_text = ""

            if request.input:
                fragments.append(
                    PromptFragment(
                        text=request.input,
                        plugin_id=request.plugin_id or entry.plugin_id,
                        metadata={"source": "request.input"},
                    )
                )

            context = PromptContext(
                agent_key=entry.key,
                plugin_id=request.plugin_id or entry.plugin_id,
                caller=request.caller,
                caller_plugin_id=request.caller_plugin_id,
                caller_hook=request.caller_hook,
                purpose=request.purpose,
                prompt_version=request.prompt_version,
                params=dict(request.params),
            )
            fragments = self._rag2f_instance.morpheus.execute_hook(
                "agent_collect_prompt_fragments",
                fragments,
                context,
                rag2f=self._rag2f_instance,
            )

            if not isinstance(fragments, list):
                raise AgentPromptError(
                    "Prompt fragment hooks must return a list of PromptFragment objects.",
                    context={
                        "agent_key": entry.key,
                        "plugin_id": entry.plugin_id,
                        "purpose": request.purpose,
                    },
                )

            if not prompt_text:
                prompt_text = self._join_fragments(fragments)

            resolved = ResolvedPrompt(
                text=prompt_text,
                fragments=fragments,
                context=context,
                metadata={**metadata, **request.metadata},
            )
            finalized = self._rag2f_instance.morpheus.execute_hook(
                "agent_finalize_prompt",
                resolved,
                context,
                rag2f=self._rag2f_instance,
            )
            if isinstance(finalized, ResolvedPrompt):
                return finalized
            if isinstance(finalized, str):
                resolved.text = finalized
                return resolved
            if finalized is resolved or finalized is None:
                return resolved
            raise AgentPromptError(
                "Prompt finalizer hooks must return a ResolvedPrompt or a string.",
                context={
                    "agent_key": entry.key,
                    "plugin_id": entry.plugin_id,
                    "purpose": request.purpose,
                },
            )
        except ATeamError:
            raise
        except Exception as exc:
            logger.error("ATeam prompt resolution failed for agent '%s': %s", entry.key, exc)
            raise AgentPromptError(
                f"Prompt resolution failed for '{entry.key}': {exc}",
                context={
                    "agent_key": entry.key,
                    "plugin_id": entry.plugin_id,
                    "purpose": request.purpose,
                    "caller": request.caller,
                    "caller_hook": request.caller_hook,
                },
            ) from exc

    def _join_fragments(self, fragments: list[PromptFragment]) -> str:
        return "\n\n".join(
            fragment.text.strip() for fragment in fragments if fragment.text.strip()
        )

    def _normalize_result(
        self,
        *,
        entry: AgentEntry,
        prompt: ResolvedPrompt,
        response: Any,
    ) -> AgentRunResult:
        if isinstance(response, AgentRunResult):
            return response.model_copy(
                update={
                    "agent_key": response.agent_key or entry.key,
                    "plugin_id": response.plugin_id or entry.plugin_id,
                    "prompt": response.prompt or prompt,
                    "metadata": {**entry.metadata, **response.metadata},
                }
            )

        return AgentRunResult.success(
            agent_key=entry.key,
            plugin_id=entry.plugin_id,
            output=response,
            prompt=prompt,
            raw_response=response,
            metadata=dict(entry.metadata),
        )


AgentManager = ATeam
