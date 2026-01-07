
import os
import sys
import json
import glob
import importlib
import importlib.util
from typing import Dict, List
from inspect import getmembers
from pydantic import BaseModel, ValidationError
from packaging.requirements import Requirement
import inflection
from rag2f.core.morpheus.package_installer import PackageInstaller, PluginSettingsModel
from rag2f.core.morpheus.decorators import PillHook
from rag2f.core.morpheus.decorators.plugin_decorator import PillPluginDecorator
from rag2f.core.morpheus.plugin_manifest import PluginManifest
import logging

logger = logging.getLogger(__name__)

# this class represents a plugin in memory
# the plugin itsefl is managed as much as possible unix style
#      (i.e. by saving information in the folder itself)
class Plugin:
    def __init__(self, plugin_path: str):
        # does folder exist?
        if not os.path.exists(plugin_path) or not os.path.isdir(plugin_path):
            raise Exception(
                f"{plugin_path} does not exist or is not a folder. Cannot create Plugin."
            )

        # where the plugin is on disk
        self._path: str = plugin_path

        # search for .py files in folder
        py_files_path = os.path.join(self._path, "**/*.py")
        self.py_files = glob.glob(py_files_path, recursive=True)
        # Filter out:
        # - /tests/ folder (test files)
        # - /rag2f/src/rag2f/ (framework folder when nested as submodule)
        # - /plugins/ folder (sub-plugins loaded separately by Morpheus, but only when
        #   the current plugin path is NOT inside plugins/ - to avoid filtering out
        #   the plugin's own files when loaded from the plugins folder)
        is_inside_plugins_folder = "/plugins/" in self._path
        self.py_files = [f for f in self.py_files 
                         if "/tests/" not in f 
                         and "/rag2f/src/rag2f/" not in f
                         and (is_inside_plugins_folder or "/plugins/" not in f)]

        if len(self.py_files) == 0:
            raise Exception(
                f"{plugin_path} does not contain any python files. Cannot create Plugin."
            )

        # plugin id is just the folder name
        self._id: str = os.path.basename(os.path.normpath(plugin_path))
        logger.debug(f"Plugin created with path '{plugin_path}' -> id '{self._id}'")

        # plugin manifest (name, decription, thumb, etc.)
        self._manifest: PluginManifest = self._load_manifest()

        # list of hooks contained in the plugin.
        #   The Morpheus will cache them for easier access,
        #   but they are created and stored in each plugin instance
        self._hooks: List[PillHook] = []  # list of plugin hooks

        # list of @plugin decorated functions overriding default plugin behaviour
        self._plugin_overrides = {}

    def activate(self):
        # install plugin requirements on activation
        try:
            self._install_requirements()
        except Exception as e:
            raise e

        # Load of hook
        self._load_decorated_functions()

        # run custom activation from @plugin
        if "activated" in self.overrides:
            self.overrides["activated"].function(self)

    # get plugin settings JSON schema
    def settings_schema(self):
        # is "settings_schema" hook defined in the plugin?
        if "settings_schema" in self.overrides:
            return self.overrides["settings_schema"].function()
        else:
            # if the "settings_schema" is not defined but
            # "settings_model" is it gets the schema from the model
            if "settings_model" in self.overrides:
                return self.overrides["settings_model"].function().model_json_schema()

        # default schema (empty)
        return PluginSettingsModel.model_json_schema()

    # get plugin settings Pydantic model
    def settings_model(self):
        # is "settings_model" hook defined in the plugin?
        if "settings_model" in self.overrides:
            return self.overrides["settings_model"].function()

        # default schema (empty)
        return PluginSettingsModel

    def _resolve_config_manager(self, *, rag2f=None, spock=None):
        """Resolve the Spock config manager from either an explicit argument or a rag2f instance."""
        if spock is not None:
            return spock
        if rag2f is not None and hasattr(rag2f, "spock"):
            return rag2f.spock
        return None

    # load plugin settings
    def load_settings(self, *, rag2f=None, spock=None):
        # is "settings_load" hook defined in the plugin?
        if "load_settings" in self.overrides:
            return self.overrides["load_settings"].function()

        config_manager = self._resolve_config_manager(rag2f=rag2f, spock=spock)
        if config_manager is not None:
            settings = config_manager.get_plugin_config(self._id)
            logger.debug(
                "Loaded settings for plugin %s from Spock (%d keys)",
                self._id,
                len(settings),
            )
            return settings

        # default behaviour: no settings persistence handled here
        logger.debug(
            "Plugin %s skipping settings.json management; returning empty settings",
            self._id,
        )
        return {}

    # save plugin settings
    def save_settings(self, settings: Dict, *, rag2f=None, spock=None):
        # is "settings_save" hook defined in the plugin?
        if "save_settings" in self.overrides:
            return self.overrides["save_settings"].function(settings)

        config_manager = self._resolve_config_manager(rag2f=rag2f, spock=spock)
        if config_manager is not None:
            for key, value in settings.items():
                config_manager.set_plugin_config(self._id, key, value)
            updated_settings = config_manager.get_plugin_config(self._id)
            logger.debug(
                "Saved settings for plugin %s via Spock (%d keys)",
                self._id,
                len(updated_settings),
            )
            return updated_settings

        # default behaviour: in-memory merge only, no file persistence
        merged_settings = {**self.load_settings(), **settings}
        logger.debug(
            "Plugin %s settings persistence disabled; returning merged settings only",
            self._id,
        )
        return merged_settings

    def _load_manifest(self) -> PluginManifest:
        
        plugin_json_metadata_file_name = "plugin.json"
        plugin_json_metadata_file_path = os.path.join(
            self._path, plugin_json_metadata_file_name
        )
        json_file_data = {}

        if os.path.isfile(plugin_json_metadata_file_path):
            try:
                json_file = open(plugin_json_metadata_file_path)
                json_file_data = json.load(json_file)
                json_file.close()
            except Exception:
                logger.debug(
                    f"Loading plugin {self._path} metadata, defaulting to generated values"
                )

        if "name" not in json_file_data:
            json_file_data["name"] = inflection.humanize(self.id)
        return PluginManifest(**json_file_data)


    def _install_requirements(self):
        # Instance method that uses the new PackageInstaller logic
        installer = PackageInstaller(self.id, self.path)
        installer.install()
     
    # lists of hooks
    def _load_decorated_functions(self):
        hooks = []
        plugin_overrides = []

        # ====================================================================
        # SETUP DUMMY PACKAGES FOR RELATIVE IMPORTS
        # ====================================================================
        # When we load plugin files using importlib.util.spec_from_file_location,
        # we assign them module names like 'plugins.rag2f_azure_openai_embedder.src.bootstrap_hook'.
        # 
        # However, if those files contain relative imports (e.g., "from .plugin_context import ..."),
        # Python needs to resolve the parent package to understand what "." refers to.
        # 
        # Problem: The parent packages ('plugins' and 'plugins.rag2f_azure_openai_embedder')
        # don't actually exist as installed Python packages - they're just naming conventions
        # we use for organizing the modules in sys.modules.
        # 
        # Solution: Create "dummy" package modules in sys.modules before loading plugin files.
        # These dummy packages tell Python's import system:
        # - "Yes, 'plugins' is a valid package"
        # - "Yes, 'plugins.rag2f_azure_openai_embedder' is a valid package"
        # - "Here's where to find submodules (__path__)"
        # 
        # This allows Python to successfully resolve relative imports like:
        #   from .src.plugin_context import set_plugin_id
        # by understanding that "." means "plugins.rag2f_azure_openai_embedder"
        # ====================================================================
        
        # Create top-level 'plugins' namespace package if it doesn't exist
        if 'plugins' not in sys.modules:
            import types
            plugins_pkg = types.ModuleType('plugins')
            plugins_pkg.__path__ = []  # Empty path list makes it a namespace package
            plugins_pkg.__package__ = 'plugins'
            sys.modules['plugins'] = plugins_pkg
            logger.debug("Created dummy 'plugins' package in sys.modules for relative imports")
        
        # Create 'plugins.<plugin_id>' package if it doesn't exist
        # This represents the root of this specific plugin
        plugin_pkg_name = f'plugins.{self._id}'
        if plugin_pkg_name not in sys.modules:
            import types
            plugin_pkg = types.ModuleType(plugin_pkg_name)
            plugin_pkg.__path__ = [self._path]  # Point to the actual plugin directory
            plugin_pkg.__package__ = plugin_pkg_name
            plugin_pkg.__file__ = os.path.join(self._path, '__init__.py')
            sys.modules[plugin_pkg_name] = plugin_pkg
            logger.debug(f"Created dummy '{plugin_pkg_name}' package in sys.modules for relative imports")

        for py_file in self.py_files:
            # Normalize the module name to a stable namespace (plugins.<plugin_id>.<relative_path>)
            # This avoids issues where the same file is imported with different module names
            # (e.g., 'plugins.rag2f_azure_openai_embedder.src.bootstrap_hook' vs
            # '.workspaces.rag2f.plugins.rag2f_azure_openai_embedder.src.bootstrap_hook')
            # which would cause Python to treat them as different modules, leading to
            # duplicate imports, decorator side effects, and overwritten hook metadata.
            # By using a consistent module name, we ensure each plugin file is loaded only once,
            # and hook metadata (like plugin_id) is not accidentally overwritten by duplicate imports.
            rel = os.path.relpath(py_file, start=self._path)  
            rel_mod = rel.replace(os.sep, ".").replace(".py", "")
            module_name = f"plugins.{self._id}.{rel_mod}"

            logger.debug(f"Import module {module_name} from {py_file}")

            # save a reference to decorated functions
            try:
                # ====================================================================
                # AVOID DUPLICATE MODULE LOADING
                # ====================================================================
                # Check if this module has already been loaded into sys.modules.
                # This can happen when:
                # 1. A test's conftest.py imports the module directly (e.g., for reset_plugin_id)
                # 2. The plugin loader then tries to load the same file again
                # 
                # Without this check, Python would execute the module code twice:
                # - First with the import path used by conftest
                # - Second with the import path used by the plugin loader
                # 
                # This causes problems:
                # - Decorators (@hook, @plugin) run twice
                # - Hook metadata gets overwritten
                # - Duplicate hooks appear in the registry
                # 
                # Solution: Reuse the already-loaded module from sys.modules instead
                # of loading it again. This ensures decorator code runs only once.
                # ====================================================================
                if module_name in sys.modules:
                    logger.debug(f"Module {module_name} already loaded, reusing existing module")
                    plugin_module = sys.modules[module_name]
                else:
                    # Load module directly from file path
                    spec = importlib.util.spec_from_file_location(module_name, py_file)
                    plugin_module = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = plugin_module
                    spec.loader.exec_module(plugin_module)

                hooks += getmembers(plugin_module, self._is_rag2f_hook)
                plugin_overrides += getmembers(plugin_module, self._is_rag2f_plugin_override)
                
            except Exception as e:
                logger.error(f"Error in {py_file}. Unable to load plugin {self._id}: {type(e).__name__}: {e}", exc_info=True)
                logger.warning(self.plugin_specific_error_message())

        # clean and enrich instances
        self._hooks = list(map(self._clean_and_enrich_hook, hooks))
        self._plugin_overrides = {override.name: override for override in list(map(self._clean_plugin_override, plugin_overrides))}

        

    def plugin_specific_error_message(self):
        name = self.manifest.name
        url = self.manifest.plugin_url

        if url:
            return f"To resolve any problem related to {name} plugin, contact the creator using github issue at the link {url}"
        return f"Error in {name} plugin, contact the creator"


    def _clean_and_enrich_hook(self, hook: PillHook):
        # getmembers returns a tuple
        h = hook[1]
        # Only set plugin_id if not already set to avoid overwriting
        # when the same hook is loaded from different import paths
        if h.plugin_id is None:
            h.plugin_id = self._id
            logger.debug(f"Set plugin_id '{self._id}' for hook '{h.name}'")
        else:
            logger.debug(f"Hook '{h.name}' already has plugin_id '{h.plugin_id}', skipping (current plugin: '{self._id}')")
        return h

    def _clean_plugin_override(self, plugin_override):
        # getmembers returns a tuple
        return plugin_override[1]
    
    # a plugin hook function has to be decorated with @hook
    # (which returns an instance of PillHook)
    @staticmethod
    def _is_rag2f_hook(obj):
        return isinstance(obj, PillHook)

    # a plugin override function has to be decorated with @plugin
    # (which returns an instance of PillPluginDecorator)
    @staticmethod
    def _is_rag2f_plugin_override(obj):
        return isinstance(obj, PillPluginDecorator)
    
    @staticmethod
    def install_requirements(plugin_id: str, plugin_path: str):
        # Static method for backward compatibility, uses PackageInstaller
        installer = PackageInstaller(plugin_id, plugin_path)
        installer.install()
    
    @property
    def path(self):
        return self._path

    @property
    def id(self):
        return self._id

    @property
    def manifest(self):
        return self._manifest

    @property
    def hooks(self):
        return self._hooks

    @property
    def overrides(self):
        return self._plugin_overrides
    
    @property
    def settings_file_path(self):
        return os.path.join(self._path, "settings.json")
