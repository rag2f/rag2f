"""Morpheus plugin manager.

Morpheus discovers plugins, loads hooks/overrides, and executes hooks.
"""

import glob
import inspect
import logging
import os
from collections.abc import Callable
from copy import deepcopy
from importlib.metadata import entry_points
from typing import TYPE_CHECKING, Any

from rag2f.core import utils
from rag2f.core.morpheus.decorators.hook import PillHook

from .plugin import Plugin

if TYPE_CHECKING:
    from rag2f.core.rag2f import RAG2F

logger = logging.getLogger(__name__)


class Morpheus:
    """Core class for managing RAG2F transformations and operations.

    Famous quote from Morpheus in Matrix:
    "What is real? How do you define 'real'? If you're talking about what you can
    feel, what you can smell, what you can taste and see, then 'real' is simply
    electrical signals interpreted by your brain."
    """

    def __init__(self, rag2f_instance: "RAG2F", plugins_folder: str | None = None):
        """Create a Morpheus instance.

        Args:
            rag2f_instance: Owning RAG2F instance.
            plugins_folder: Optional plugins folder path.
        """
        self._rag2f_instance = rag2f_instance  # Store reference to RAG2F instance
        self.plugins: dict[str, Plugin] = {}  # plugins dictionary
        self.hooks: dict[str, list[PillHook]] = {}  # hooks registered in the system
        self.plugins_folder = (
            plugins_folder if plugins_folder is not None else utils.get_default_plugins_path()
        )

        # callback out of the hook system to notify other components about a refresh
        self.on_refresh_callbacks: list[Callable] = []

        logger.debug("Morpheus instance created with plugins_folder: %s", self.plugins_folder)

    # discover all plugins from both entry points and filesystem
    async def find_plugins(self):
        """Discover plugins from both filesystem and entry points.

        Priority order:
        1. Entry points (installed packages via pip/uv)
        2. Filesystem (local development in plugins_folder)

        Entry points take precedence to allow installed versions to override local ones.
        """
        self.plugins = {}

        # 1. Load from entry points (installed packages)
        await self._load_from_entry_points()

        # 2. Load from filesystem (local development/path-based)
        await self._load_from_filesystem()

        await self.refresh_caches()

    async def _load_from_entry_points(self):
        """Load plugins from installed packages via entry points."""
        try:
            # Python 3.10+ syntax
            discovered = entry_points(group="rag2f.plugins")
        except TypeError:
            # Python 3.9 fallback
            discovered = entry_points().get("rag2f.plugins", [])

        for ep in discovered:
            try:
                plugin_factory = ep.load()

                # The factory should return the plugin path
                if not callable(plugin_factory):
                    logger.warning(f"Entry point '{ep.name}' is not callable")
                    continue

                plugin_path = plugin_factory()

                if not isinstance(plugin_path, str):
                    logger.warning(
                        f"Entry point '{ep.name}' did not return a string path, got: {type(plugin_path)}"
                    )
                    continue

                # FIX: If the plugin path points to site-packages directory itself,
                # this is likely a bug in the plugin's get_plugin_path() function.
                # Try to find the actual plugin directory based on the entry point name.
                if (
                    "site-packages" in plugin_path
                    and os.path.basename(plugin_path.rstrip("/")) == "site-packages"
                ):
                    logger.warning(
                        f"Entry point '{ep.name}' returned site-packages directory, attempting to locate actual plugin"
                    )

                    # Try to find plugin directory using entry point name.
                    # Try both with hyphens and underscores (pkg names use hyphens,
                    # module names use underscores).
                    potential_names = [
                        ep.name,  # rag2f-openai-embedder
                        ep.name.replace("-", "_"),  # rag2f_openai_embedder
                    ]

                    found = False
                    for name in potential_names:
                        potential_plugin_dir = os.path.join(plugin_path, name)
                        if os.path.isdir(potential_plugin_dir):
                            logger.info(f"Found plugin directory: {potential_plugin_dir}")
                            plugin_path = potential_plugin_dir
                            found = True
                            break

                    if not found:
                        logger.error(
                            f"Could not locate plugin directory for '{ep.name}' in {plugin_path}"
                        )
                        continue

                # Create plugin from the returned path
                plugin = Plugin(self._rag2f_instance, plugin_path)

                # Register plugin (entry points have priority over filesystem)
                if plugin.id not in self.plugins:
                    self.plugins[plugin.id] = plugin
                    plugin.activate()
                    logger.info(f"✅ Loaded plugin '{plugin.id}' from entry point '{ep.name}'")
                else:
                    logger.debug(
                        f"Plugin '{plugin.id}' already loaded, skipping entry point '{ep.name}'"
                    )

            except Exception as e:
                logger.error(
                    f"Failed to load plugin from entry point '{ep.name}': {e}", exc_info=True
                )

    async def _load_from_filesystem(self):
        """Load plugins from filesystem (existing behavior for local development)."""
        if not os.path.exists(self.plugins_folder):
            logger.warning(f"Plugins folder does not exist: {self.plugins_folder}")
            return

        all_plugin_folders = glob.glob(f"{self.plugins_folder}*/")

        # Filter out the plugins folder itself
        plugins_folder_abs = os.path.abspath(self.plugins_folder)
        all_plugin_folders = [
            f for f in all_plugin_folders if os.path.abspath(f.rstrip("/")) != plugins_folder_abs
        ]

        # Convert plugin folders to absolute paths
        for folder in all_plugin_folders:
            try:
                plugin = Plugin(self._rag2f_instance, folder)

                # Avoid duplicates (entry points have priority)
                if plugin.id not in self.plugins:
                    self.plugins[plugin.id] = plugin
                    plugin.activate()
                    logger.info(f"📁 Loaded plugin '{plugin.id}' from filesystem: {folder}")
                else:
                    logger.debug(
                        f"Plugin '{plugin.id}' already loaded from entry point, skipping filesystem version"
                    )

            except Exception:
                logger.error(f"Could not load plugin in {folder}", exc_info=True)
        await self.refresh_caches()

    # Load hooks, tools and forms of the active plugins into Morpheus
    async def refresh_caches(self):
        """Rebuild hook caches from currently loaded plugins."""
        # emptying hooks
        self.hooks = {}

        for _, plugin in self.plugins.items():
            # cache hooks (indexed by hook name)
            for h in plugin.hooks:
                if h.name not in self.hooks:
                    self.hooks[h.name] = []
                self.hooks[h.name].append(h)

        # sort each hooks list by priority
        for hook_name in self.hooks:
            self.hooks[hook_name].sort(key=lambda x: x.priority, reverse=True)

        # Notify subscribers about finished refresh
        for callback in self.on_refresh_callbacks:
            await utils.run_sync_or_async(callback)

    def plugin_exists(self, plugin_id) -> bool:
        """Check if a plugin exists locally."""
        return plugin_id in self.plugins

    # execute requested hook
    def execute_hook(self, hook_name, *args, rag2f) -> Any:
        """Execute a hook pipeline.

        Args:
            hook_name: Name of the hook pipeline.
            *args: Pipeline arguments (first arg is piped through hooks).
            rag2f: The RAG2F instance passed to hooks.

        Returns:
            The piped value (or None when the hook takes no args).
        """
        # check if hook is supported
        if hook_name not in self.hooks:
            logger.debug(f"Hook {hook_name} not present in any plugin")
            if len(args) == 0:
                return
            else:
                return args[0]

        # Hook has no arguments (aside rag2f)
        #  no need to pipe
        if len(args) == 0:
            for hook in self.hooks[hook_name]:
                try:
                    logger.debug(
                        f"Executing {hook.plugin_id}::{hook.name} with priority {hook.priority}"
                    )
                    hook.function(rag2f=rag2f)
                except Exception:
                    logger.error(f"Error in plugin {hook.plugin_id}::{hook.name}")
                    plugin_obj = self.plugins[hook.plugin_id]
                    logger.warning(plugin_obj.plugin_specific_error_message())
            return

        # Hook with arguments.
        #  First argument is passed to `execute_hook` is the pipeable one.
        #  We call it `phone` as every hook called will receive it as an input,
        # can dial in new features, connect to different behaviors, and return it
        # for the next hook.
        phone = deepcopy(args[0])

        # run hooks
        for hook in self.hooks[hook_name]:
            try:
                # pass phone to the hooks, along other args
                # hook has at least one argument, and it will be piped
                logger.debug(
                    f"Executing {hook.plugin_id}::{hook.name} with priority {hook.priority}"
                )
                dial_pad = hook.function(deepcopy(phone), *deepcopy(args[1:]), rag2f=rag2f)
                if dial_pad is not None:
                    phone = dial_pad
            except Exception:
                logger.error(f"Error in plugin {hook.plugin_id}::{hook.name}")
                plugin_obj = self.plugins[hook.plugin_id]
                logger.warning(plugin_obj.plugin_specific_error_message())

        # phone has passed through all hooks. Return final output
        return phone

    def self_plugin_id(self):
        """Get plugin_id (used from within a plugin).

        This method is meant to be called from within hook functions decorated with @hook.
        It inspects the calling stack to determine which plugin is executing and returns
        the corresponding Plugin_id.


        Returns:
            Plugin_id: The Plugin_id of the calling hook function.

        Raises:
            RuntimeError: If called from a non-hook context or from outside a valid plugin.
        """
        try:
            stack = inspect.stack()

            # Walk the stack from caller upwards (skip frame 0)
            # to find the first frame containing a function decorated with @hook
            for frame_info in stack[1:]:
                module = inspect.getmodule(frame_info.frame)
                if module is None:
                    continue

                func_name = frame_info.function
                plugin_id = self._extract_plugin_id_from_hook(module, func_name)
                logger.debug(
                    f"Found plugin_id '{plugin_id}' in function '{func_name}' of module '{module.__name__}'"
                )
                if plugin_id is not None:
                    return plugin_id

            # No @hook found in the entire call stack
            raise RuntimeError(
                "No @hook decorated function found in the call stack. "
                "For @plugin decorated functions, use plugin.id instead. "
                "This method must be called from within or through a @hook decorated function in a plugin."
            )

        except RuntimeError:
            raise
        except Exception as e:
            logger.error(f"Error in self_plugin_id: {type(e).__name__}: {e}", exc_info=True)
            raise RuntimeError(f"Failed to determine plugin: {e}") from e

    def get_plugin(self, plugin_id) -> Plugin:
        """Get plugin by id."""
        try:
            if self.plugin_exists(plugin_id):
                return self.plugins[plugin_id]
            raise RuntimeError(
                f"Plugin '{plugin_id}' not found in loaded plugins. "
                f"Available plugins: {list(self.plugins.keys())}"
            )
        except RuntimeError:
            raise
        except Exception as e:
            logger.error(f"Error in get_plugin: {type(e).__name__}: {e}", exc_info=True)
            raise RuntimeError(f"Failed to determine plugin: {e}") from e

    def _extract_plugin_id_from_hook(self, module, hook_name: str) -> str | None:
        """Extract plugin_id from a specific hook in a module.

        Looks up a specific hook by name and retrieves its plugin_id.
        This is more efficient than searching all attributes since we know
        exactly which hook we're looking for.

        Args:
            module: The module object to inspect.
            hook_name: The name of the hook function to find.

        Returns:
            str: The plugin_id if the hook is found and is a valid PillHook, None otherwise.
        """
        try:
            # Try to get the attribute directly by name
            attr = getattr(module, hook_name, None)

            if attr is None:
                logger.debug(f"Attribute '{hook_name}' not found in module {module.__name__}")
                return None

            # Check if this attribute is a PillHook instance
            if isinstance(attr, PillHook):
                # Verify it has a valid plugin_id set
                if attr.plugin_id is not None and isinstance(attr.plugin_id, str):
                    logger.debug(
                        f"Found hook '{attr.name}' with plugin_id '{attr.plugin_id}' in module {module.__name__}"
                    )
                    return attr.plugin_id
                else:
                    logger.warning(
                        f"Hook '{hook_name}' in module {module.__name__} has invalid plugin_id: {attr.plugin_id}"
                    )
                    return None
            else:
                logger.debug(
                    f"Attribute '{hook_name}' in module {module.__name__} is not a PillHook, "
                    f"it's a {type(attr).__name__}"
                )
                return None

        except Exception as e:
            logger.debug(f"Error accessing hook '{hook_name}' in module {module.__name__}: {e}")
            return None


PluginManager = Morpheus
