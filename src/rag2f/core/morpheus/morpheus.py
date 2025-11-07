import os
import glob
import shutil
import inspect
from copy import deepcopy
from typing import Any, Callable, Dict, List

from rag2f.core import utils
from rag2f.core.morpheus.decorators.hook import PillHook
from .plugin import Plugin
import logging

logger = logging.getLogger(__name__)


class Morpheus:
    """Core class for managing RAG2F transformations and operations.

    Famous quote from Morpheus in Matrix:
    "What is real? How do you define 'real'? If you're talking about what you can feel, what you can smell, what you can taste and see, then 'real' is simply electrical signals interpreted by your brain"
    """

    def __init__(self, plugins_folder: str | None = None):
        self.plugins: Dict[str, Plugin] = {}  # plugins dictionary
        self.hooks: Dict[str, List[PillHook]] = {}  # hooks registered in the system
        self.plugins_folder = plugins_folder if plugins_folder is not None else utils.get_plugins_path()
        
        # callback out of the hook system to notify other components about a refresh
        self.on_refresh_callbacks: List[Callable] = []
        
        logger.debug("Morpheus instance created with plugins_folder: %s", self.plugins_folder)

    @classmethod
    async def create(cls, plugins_folder: str | None = None):
        instance = cls(plugins_folder=plugins_folder)
        await instance.find_plugins()
        return instance
    
    # discover all plugins
    async def find_plugins(self):
        # emptying plugin dictionary, plugins will be discovered from disk
        # and stored in a dictionary plugin_id -> plugin_obj
        self.plugins = {}
        if not os.path.exists(self.plugins_folder):
            logger.error(f"Plugins folder does not exist: {self.plugins_folder}")
            return
        all_plugin_folders = glob.glob(f"{self.plugins_folder}*/")
        logger.info(f"Find Plugins in: {all_plugin_folders}")  
        for folder in all_plugin_folders:
            try:
                plugin = Plugin(folder)
                # if plugin is valid, keep a reference                
                self.plugins[plugin.id] = plugin
                plugin.activate()
            except Exception as e:
                logger.error(f"Could not load plugin in {folder}", exc_info=True)
        await self.refresh_caches()

    # Load hooks, tools and forms of the active plugins into Morpheus
    async def refresh_caches(self):
        # emptying hooks
        self.hooks = {}

        for _, plugin in self.plugins.items():            
            # cache hooks (indexed by hook name)
            for h in plugin.hooks:
                if h.name not in self.hooks.keys():
                    self.hooks[h.name] = []
                self.hooks[h.name].append(h)

        # sort each hooks list by priority
        for hook_name in self.hooks.keys():
            self.hooks[hook_name].sort(key=lambda x: x.priority, reverse=True)

        # Notify subscribers about finished refresh
        for callback in self.on_refresh_callbacks:
            await utils.run_sync_or_async(callback)

    def plugin_exists(self, plugin_id) -> bool:
        """Check if a plugin exists locally."""
        return plugin_id in self.plugins.keys()

    # execute requested hook
    def execute_hook(self, hook_name, *args, rag2f) -> Any:
        # check if hook is supported
        if hook_name not in self.hooks.keys():
            logger.debug(f"Hook {hook_name} not present in any plugin")
            if len(args)==0:
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
        # can dial in new features, connect to different behaviors, and return it for the next hook.
        phone = deepcopy(args[0])

        # run hooks
        for hook in self.hooks[hook_name]:
            try:
                # pass phone to the hooks, along other args
                # hook has at least one argument, and it will be piped
                logger.debug(
                    f"Executing {hook.plugin_id}::{hook.name} with priority {hook.priority}"
                )
                dial_pad = hook.function(
                    deepcopy(phone), *deepcopy(args[1:]), rag2f=rag2f
                )
                if dial_pad is not None:
                    phone = dial_pad
            except Exception:
                logger.error(f"Error in plugin {hook.plugin_id}::{hook.name}")
                plugin_obj = self.plugins[hook.plugin_id]
                logger.warning(plugin_obj.plugin_specific_error_message())

        # phone has passed through all hooks. Return final output
        return phone
