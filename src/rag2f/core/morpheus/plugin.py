import os
import sys
import json
import glob
import tempfile
import importlib
import importlib.util
import subprocess
import shutil
from typing import Dict, List
from inspect import getmembers
from pydantic import BaseModel, ValidationError
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

        # Try to create setting.json
        if not os.path.isfile(self.settings_file_path):
            self._create_settings_from_model()

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

    # load plugin settings
    def load_settings(self):
        # is "settings_load" hook defined in the plugin?
        if "load_settings" in self.overrides:
            return self.overrides["load_settings"].function()

        if not os.path.isfile(self.settings_file_path):
            if not self._create_settings_from_model():
                return {}

        # load settings.json if exists
        if os.path.isfile(self.settings_file_path):
            try:
                with open(self.settings_file_path, "r") as json_file:
                    settings = json.load(json_file)
                    return settings

            except Exception as e:
                logger.error(f"Unable to load plugin {self._id} settings.")
                logger.warning(self.plugin_specific_error_message())
                raise e

    # save plugin settings
    def save_settings(self, settings: Dict):
        # is "settings_save" hook defined in the plugin?
        if "save_settings" in self.overrides:
            return self.overrides["save_settings"].function(settings)

        # load already saved settings
        old_settings = self.load_settings()

        # overwrite settings over old ones
        updated_settings = {**old_settings, **settings}

        # write settings.json in plugin folder
        try:
            with open(self.settings_file_path, "w") as json_file:
                json.dump(updated_settings, json_file, indent=4)
            return updated_settings
        except Exception:
            logger.error(f"Unable to save plugin {self._id} settings.")
            logger.warning(self.plugin_specific_error_message())
            return {}

    def _create_settings_from_model(self) -> bool:

        try:
            model = self.settings_model()
            # if some settings have no default value this will raise a ValidationError
            settings = model().model_dump_json(indent=4)

            # If each field have a default value and the model is correct,
            # create the settings.json with default values
            with open(self.settings_file_path, "x") as json_file:
                json_file.write(settings)
                logger.debug(
                    f"{self.id} have no settings.json, created with settings model default values"
                )

            return True

        except ValidationError:
            logger.debug(
                f"{self.id} settings model have missing defaut values, no settings.json created"
            )
            return False

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
        req_file = os.path.join(self.path, "requirements.txt")


         # Early return if no requirements file exists
        if not os.path.exists(req_file):
            logger.debug(f"No requirements.txt found for plugin {self.id}")
            return

        # Detect available package managers
        uv_available = shutil.which("uv") is not None
        pip_available = shutil.which("pip3") is not None or shutil.which("pip") is not None
        
        if not uv_available and not pip_available:
            logger.warning(f"No package manager found (uv or pip). Skipping requirements installation for plugin {self.id}")
            return

        # Get installed packages
        try:
            installed_packages = {pkg.name.lower() for pkg in importlib.metadata.distributions()}
        except Exception as e:
            logger.error(f"Error getting installed packages: {e}")
            installed_packages = set()

        # Parse and filter requirements
        filtered_requirements = []

        logger.info(f"Checking requirements for plugin {self.id}")
        
        try:
            with open(req_file, "r") as read_file:
                requirements = read_file.readlines()

            for req in requirements:
                req = req.strip()
                
                # Skip empty lines and comments
                if not req or req.startswith("#"):
                    continue
                
                try:
                    # Parse requirement
                    parsed_req = Requirement(req)
                    package_name = parsed_req.name.lower()
                    
                    # Check if package is already installed
                    if package_name not in installed_packages:
                        logger.debug(f"\t {package_name} needs to be installed")
                        filtered_requirements.append(req)
                    else:
                        logger.debug(f"\t {package_name} is already installed")
                        
                except Exception as e:
                    logger.warning(f"Invalid requirement '{req}': {e}")
                    continue

        except Exception as e:
            logger.error(f"Error reading requirements file for plugin {self.id}: {e}")
            return

        # No requirements to install
        if len(filtered_requirements) == 0:
            logger.debug(f"All requirements already satisfied for plugin {self.id}")
            return

        # Create temporary requirements file
        tmp_file = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as tmp:
                tmp.write("\n".join(filtered_requirements))
                tmp.flush()
                tmp_file = tmp.name

            # Check if we're in a virtual environment
            in_venv = (
                hasattr(sys, 'real_prefix') or  # virtualenv
                (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix) or  # venv
                os.environ.get('VIRTUAL_ENV') is not None  # environment variable
            )
            
            # Choose package manager and build command
            if uv_available:
                install_cmd = ["uv", "pip", "install", "--no-cache-dir", "-r", tmp_file]
                # If not in a virtual environment, add --system flag for uv
                if not in_venv:
                    install_cmd.insert(3, "--system")  # Insert after 'install'
                    logger.debug(f"Using uv with --system flag (no virtual environment detected) for plugin {self.id}")
                else:
                    logger.debug(f"Using uv to install requirements for plugin {self.id}")
            else:
                pip_cmd = "pip3" if shutil.which("pip3") else "pip"
                install_cmd = [pip_cmd, "install", "--no-cache-dir", "-r", tmp_file]
                logger.debug(f"Using {pip_cmd} to install requirements for plugin {self.id}")

            # Install requirements
            logger.info(f"Installing requirements for plugin {self.id}")
            result = subprocess.run(
                install_cmd,
                check=True,
                capture_output=True,
                text=True
            )
            logger.debug(f"Installation output: {result.stdout}")
            logger.info(f"Successfully installed requirements for plugin {self.id}")

        except subprocess.CalledProcessError as e:
            logger.error(f"Error while installing plugin {self.id} requirements: {e}")
            logger.error(f"stderr: {e.stderr if hasattr(e, 'stderr') else 'N/A'}")
            raise           
            
            
        except Exception as e:
            logger.error(f"Unexpected error during requirements installation for plugin {self.id}: {e}")
            raise
            
        finally:
            # Clean up temporary file
            if tmp_file and os.path.exists(tmp_file):
                try:
                    os.unlink(tmp_file)
                except Exception as e:
                    logger.warning(f"Failed to remove temporary file {tmp_file}: {e}")

    # lists of hooks
    def _load_decorated_functions(self):
        hooks = []
        plugin_overrides = []

        for py_file in self.py_files:
            module_name = py_file.replace(".py", "").replace("/", ".")

            logger.debug(f"Import module {module_name} from {py_file}")

            # save a reference to decorated functions
            try:
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
        self._hooks = list(map(self._clean_hook, hooks))
        self._plugin_overrides = {override.name: override for override in list(map(self._clean_plugin_override, plugin_overrides))}

        

    def plugin_specific_error_message(self):
        name = self.manifest.name
        url = self.manifest.plugin_url

        if url:
            return f"To resolve any problem related to {name} plugin, contact the creator using github issue at the link {url}"
        return f"Error in {name} plugin, contact the creator"


    def _clean_hook(self, hook: PillHook):
        # getmembers returns a tuple
        h = hook[1]
        h.plugin_id = self._id
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
