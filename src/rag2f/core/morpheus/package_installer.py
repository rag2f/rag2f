import os
import sys
import tempfile
import importlib
import subprocess
import shutil
from typing import List, Optional, Set
from pydantic import BaseModel
from packaging.requirements import Requirement
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