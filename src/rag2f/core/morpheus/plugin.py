
import os
import sys
import json
import glob
import tempfile
import importlib
import importlib.util
import subprocess
import shutil
from typing import Dict, List, Optional, Set
from inspect import getmembers
from pydantic import BaseModel
from packaging.requirements import Requirement
import inflection

from rag2f.core.morpheus.decorators import PillHook
from rag2f.core.morpheus.decorators.plugin_decorator import PillPluginDecorator
from rag2f.core.morpheus.plugin_manifest import PluginManifest
import logging

logger = logging.getLogger(__name__)

# Empty class to represent basic plugin Settings model
class PluginSettingsModel(BaseModel):
    pass


# this class represents a plugin in memory
# the plugin itsefl is managed as much as possible unix style
#      (i.e. by saving information in the folder itself)



# Helper class to handle dependency installation logic
class PackageInstaller:
    """Handles package installation from requirements.txt or pyproject.toml."""
    def __init__(self, plugin_id: str, plugin_path: str):
        self.plugin_id = plugin_id
        self.plugin_path = plugin_path
        self._installed_packages: Optional[Set[str]] = None
        self._package_manager: Optional[tuple[list, bool]] = None  # (base_cmd, is_uv)

    @property
    def installed_packages(self) -> Set[str]:
        if self._installed_packages is None:
            try:
                self._installed_packages = {pkg.name.lower() for pkg in importlib.metadata.distributions()}
            except Exception as e:
                logger.error(f"Error getting installed packages: {e}")
                self._installed_packages = set()
        return self._installed_packages

    @property
    def package_manager(self) -> Optional[tuple[list, bool]]:
        # Detect and cache available package manager. Returns (base_cmd, is_uv).
        if self._package_manager is None:
            uv_available = shutil.which("uv") is not None
            if uv_available:
                self._package_manager = (["uv", "pip"], True)
            elif shutil.which("pip3"):
                self._package_manager = (["pip3"], False)
            elif shutil.which("pip"):
                self._package_manager = (["pip"], False)
            else:
                self._package_manager = (None, False)
        return self._package_manager

    @property
    def in_virtual_env(self) -> bool:
        # Check if running in a virtual environment
        return (
            hasattr(sys, 'real_prefix') or
            (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix) or
            os.environ.get('VIRTUAL_ENV') is not None
        )

    @property
    def pyproject_path(self) -> str:
        return os.path.join(self.plugin_path, "pyproject.toml")

    @property
    def requirements_path(self) -> str:
        return os.path.join(self.plugin_path, "requirements.txt")

    def install(self) -> None:
        # Prefer pyproject.toml over requirements.txt
        base_cmd, is_uv = self.package_manager
        if base_cmd is None:
            logger.warning(
                f"No package manager found (uv or pip). Skipping requirements installation for plugin {self.plugin_id}"
            )
            return

        if os.path.exists(self.pyproject_path):
            self._install_from_pyproject(base_cmd, is_uv)
        elif os.path.exists(self.requirements_path):
            self._install_from_requirements(base_cmd, is_uv)
        else:
            logger.debug(
                f"No pyproject.toml or requirements.txt found for plugin {self.plugin_id}"
            )

    def _install_from_pyproject(self, base_cmd: list, is_uv: bool) -> None:
        # Install dependencies from pyproject.toml using pip install -e or uv pip install -e
        logger.info(f"Installing plugin {self.plugin_id} from pyproject.toml")
        install_cmd = self._build_install_command(base_cmd, is_uv, editable_path=self.plugin_path)
        self._run_install(install_cmd)

    def _install_from_requirements(self, base_cmd: list, is_uv: bool) -> None:
        # Install dependencies from requirements.txt, filtering already installed packages
        logger.info(f"Checking requirements for plugin {self.plugin_id}")
        filtered_requirements = self._filter_requirements()
        if not filtered_requirements:
            logger.debug(f"All requirements already satisfied for plugin {self.plugin_id}")
            return
        tmp_file = None
        try:
            tmp_file = self._create_temp_requirements(filtered_requirements)
            install_cmd = self._build_install_command(base_cmd, is_uv, requirements_file=tmp_file)
            self._run_install(install_cmd)
        finally:
            if tmp_file and os.path.exists(tmp_file):
                try:
                    os.unlink(tmp_file)
                except Exception as e:
                    logger.warning(f"Failed to remove temporary file {tmp_file}: {e}")

    def _filter_requirements(self) -> List[str]:
        # Parse requirements.txt and filter out already installed packages
        filtered = []
        try:
            with open(self.requirements_path, "r") as f:
                for line in f:
                    req = line.strip()
                    # Skip empty lines and comments
                    if not req or req.startswith("#"):
                        continue
                    try:
                        parsed = Requirement(req)
                        package_name = parsed.name.lower()
                        if package_name not in self.installed_packages:
                            logger.debug(f"\t{package_name} needs to be installed")
                            filtered.append(req)
                        else:
                            logger.debug(f"\t{package_name} is already installed")
                    except Exception as e:
                        logger.warning(f"Invalid requirement '{req}': {e}")
        except Exception as e:
            logger.error(f"Error reading requirements file for plugin {self.plugin_id}: {e}")
        return filtered

    def _create_temp_requirements(self, requirements: List[str]) -> str:
        # Create a temporary requirements file
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as tmp:
            tmp.write("\n".join(requirements))
            tmp.flush()
            return tmp.name

    def _build_install_command(
        self,
        base_cmd: list,
        is_uv: bool,
        *,
        editable_path: Optional[str] = None,
        requirements_file: Optional[str] = None
    ) -> list:
        # Build the install command based on package manager and options
        cmd = base_cmd.copy()
        cmd.append("install")
        # Add --system flag for uv when not in virtual environment
        if is_uv and not self.in_virtual_env:
            cmd.append("--system")
            logger.debug(
                f"Using uv with --system flag (no virtual environment detected) for plugin {self.plugin_id}"
            )
        cmd.append("--no-cache-dir")
        if editable_path:
            cmd.extend(["-e", editable_path])
        elif requirements_file:
            cmd.extend(["-r", requirements_file])
        return cmd

    def _run_install(self, cmd: list) -> None:
        # Execute the installation command
        logger.info(f"Installing requirements for plugin {self.plugin_id}")
        logger.debug(f"Running command: {' '.join(cmd)}")
        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True
            )
            logger.debug(f"Installation output: {result.stdout}")
            logger.info(f"Successfully installed requirements for plugin {self.plugin_id}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Error while installing plugin {self.plugin_id} requirements: {e}")
            logger.error(f"stderr: {e.stderr if hasattr(e, 'stderr') else 'N/A'}")
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error during requirements installation for plugin {self.plugin_id}: {e}"
            )
            raise


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
        # Filter out eventual `tests` folder
        self.py_files = [f for f in self.py_files if "/tests/" not in f]

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
