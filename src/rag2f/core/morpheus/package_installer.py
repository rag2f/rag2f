"""Dependency installation helpers for plugins.

This module provides a thin wrapper around `uv`/`pip` to install plugin
dependencies from either `pyproject.toml` or `requirements.txt`.
"""

import importlib
import logging
import os
import shutil
import subprocess
import sys
import tempfile

from packaging.requirements import Requirement

from rag2f.core.observability import (
    debug_event,
    exception_event,
    info_event,
    observation_scope,
    warning_event,
)

logger = logging.getLogger(__name__)


# Helper class to handle dependency installation logic
class PackageInstaller:
    """Handles package installation from requirements.txt or pyproject.toml."""

    def __init__(self, plugin_id: str, plugin_path: str):
        """Create a PackageInstaller.

        Args:
            plugin_id: The plugin identifier (used for logs).
            plugin_path: Filesystem path to the plugin folder.
        """
        self.plugin_id = plugin_id
        self.plugin_path = plugin_path
        self._installed_packages: set[str] | None = None
        self._package_manager: tuple[list, bool] | None = None  # (base_cmd, is_uv)

    @property
    def installed_packages(self) -> set[str]:
        """Return the set of currently installed package names (lowercased)."""
        if self._installed_packages is None:
            try:
                self._installed_packages = {
                    pkg.name.lower() for pkg in importlib.metadata.distributions()
                }
            except Exception as e:
                logger.error(f"Error getting installed packages: {e}")
                self._installed_packages = set()
        return self._installed_packages

    @property
    def package_manager(self) -> tuple[list, bool] | None:
        """Return the detected package manager command.

        Returns:
            A tuple of (base_command, is_uv) when a manager is available.
            Returns None when neither `uv` nor `pip` is found.
        """
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
                self._package_manager = None
        return self._package_manager

    @property
    def in_virtual_env(self) -> bool:
        """Return True when running inside a virtual environment."""
        # Check if running in a virtual environment
        return (
            hasattr(sys, "real_prefix")
            or (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix)
            or os.environ.get("VIRTUAL_ENV") is not None
        )

    @property
    def pyproject_path(self) -> str:
        """Return the path to the plugin's `pyproject.toml`."""
        return os.path.join(self.plugin_path, "pyproject.toml")

    @property
    def requirements_path(self) -> str:
        """Return the path to the plugin's `requirements.txt`."""
        return os.path.join(self.plugin_path, "requirements.txt")

    def install(self) -> None:
        """Install plugin dependencies if a manifest file is present."""
        with observation_scope(plugin_id=self.plugin_id, plugin_path=self.plugin_path):
            base_cmd, is_uv = self.package_manager
            if base_cmd is None:
                warning_event(logger, "plugin_requirements_tool_missing")
                return

            if os.path.exists(self.pyproject_path):
                self._install_from_pyproject(base_cmd, is_uv)
            elif os.path.exists(self.requirements_path):
                self._install_from_requirements(base_cmd, is_uv)
            else:
                debug_event(logger, "plugin_requirements_manifest_missing")

    def _install_from_pyproject(self, base_cmd: list, is_uv: bool) -> None:
        info_event(logger, "plugin_requirements_install_from_pyproject", tool=base_cmd[0])
        install_cmd = self._build_install_command(base_cmd, is_uv, editable_path=self.plugin_path)
        self._run_install(install_cmd)

    def _install_from_requirements(self, base_cmd: list, is_uv: bool) -> None:
        info_event(logger, "plugin_requirements_check_start", tool=base_cmd[0])
        filtered_requirements = self._filter_requirements()
        if not filtered_requirements:
            debug_event(logger, "plugin_requirements_already_satisfied")
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
                    warning_event(
                        logger,
                        "plugin_requirements_tempfile_cleanup_failed",
                        error_type=type(e).__name__,
                    )

    def _filter_requirements(self) -> list[str]:
        """Filter requirements by excluding already-installed packages."""
        # Parse requirements.txt and filter out already installed packages
        filtered = []
        try:
            with open(self.requirements_path) as f:
                for line in f:
                    req = line.strip()
                    if not req or req.startswith("#"):
                        continue
                    try:
                        parsed = Requirement(req)
                        package_name = parsed.name.lower()
                        if package_name not in self.installed_packages:
                            filtered.append(req)
                    except Exception as e:
                        warning_event(
                            logger,
                            "plugin_requirements_invalid_entry",
                            error_type=type(e).__name__,
                        )
        except Exception as e:
            exception_event(
                logger,
                "plugin_requirements_read_failed",
                error_type=type(e).__name__,
            )
        debug_event(logger, "plugin_requirements_filtered", requirement_count=len(filtered))
        return filtered

    def _create_temp_requirements(self, requirements: list[str]) -> str:
        """Create a temporary requirements file and return its path."""
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
        editable_path: str | None = None,
        requirements_file: str | None = None,
    ) -> list:
        cmd = base_cmd.copy()
        cmd.append("install")
        if is_uv and not self.in_virtual_env:
            cmd.append("--system")
            debug_event(logger, "plugin_requirements_using_uv_system")
        cmd.append("--no-cache-dir")
        if editable_path:
            cmd.extend(["-e", editable_path])
        elif requirements_file:
            cmd.extend(["-r", requirements_file])
        return cmd

    def _run_install(self, cmd: list) -> None:
        info_event(
            logger,
            "plugin_requirements_install_start",
            tool=cmd[0],
            editable="-e" in cmd,
            uses_requirements="-r" in cmd,
        )
        try:
            result = subprocess.run(  # noqa: S603
                cmd, check=True, capture_output=True, text=True
            )
            debug_event(
                logger,
                "plugin_requirements_install_complete",
                return_code=result.returncode,
                stdout_length=len(result.stdout),
                stderr_length=len(result.stderr),
            )
            info_event(logger, "plugin_requirements_install_succeeded")
        except subprocess.CalledProcessError as e:
            exception_event(
                logger,
                "plugin_requirements_install_failed",
                return_code=e.returncode,
                stderr_length=len(e.stderr or ""),
            )
            raise
        except Exception as e:
            exception_event(
                logger,
                "plugin_requirements_install_crashed",
                error_type=type(e).__name__,
            )
            raise
