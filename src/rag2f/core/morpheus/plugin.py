"""Plugin loader and runtime representation.

This module defines the `Plugin` class used by Morpheus to discover plugin
metadata, load decorated hooks/overrides, and manage activation lifecycle.
"""

import glob
import importlib
import importlib.metadata
import importlib.util
import json
import logging
import os
import re
import sys
from inspect import getmembers
from pathlib import Path
from typing import TYPE_CHECKING

import inflection

from rag2f.core.morpheus.decorators import PillHook
from rag2f.core.morpheus.decorators.plugin_decorator import PillPluginDecorator
from rag2f.core.morpheus.package_installer import PackageInstaller
from rag2f.core.morpheus.plugin_manifest import PluginManifest

if TYPE_CHECKING:
    from rag2f.core.rag2f import RAG2F

logger = logging.getLogger(__name__)


# this class represents a plugin in memory
# the plugin itsefl is managed as much as possible unix style
#      (i.e. by saving information in the folder itself)
class Plugin:
    """In-memory representation of a plugin.

    A plugin is backed by a folder on disk and may expose:
    - Hook functions decorated with `@hook`
    - Lifecycle overrides decorated with `@plugin`
    - Metadata in `plugin.json` and/or `pyproject.toml`
    """

    def __init__(self, rag2f_instance: "RAG2F", plugin_path: str):
        """Create a Plugin from a filesystem path.

        Args:
            rag2f_instance: The owning RAG2F instance.
            plugin_path: Path to the plugin folder.

        Raises:
            Exception: If the folder does not exist or has no Python files.
        """
        self._rag2f_instance = rag2f_instance  # Store reference to RAG2F instance

        # does folder exist?
        if not os.path.exists(plugin_path) or not os.path.isdir(plugin_path):
            raise Exception(
                f"{plugin_path} does not exist or is not a folder. Cannot create Plugin."
            )

        # ----------------------------
        # Source type detection
        # ----------------------------
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
        self.py_files = [
            f
            for f in self.py_files
            if "/tests/" not in f
            and "/rag2f/src/rag2f/" not in f
            and (is_inside_plugins_folder or "/plugins/" not in f)
        ]

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
        self._hooks: list[PillHook] = []  # list of plugin hooks

        # list of @plugin decorated functions overriding default plugin behaviour
        self._plugin_overrides = {}

        # plugin starts deactivated
        self._active = False

    def activate(self):
        """Activate the plugin: install deps, load hooks/overrides, run activation."""
        # install plugin requirements on activation
        try:
            self._install_requirements()
        except Exception as e:
            raise e

        # Load of hook and ovverided functions
        self._load_decorated_functions()

        # run custom activation from @plugin
        if "activated" in self.overrides:
            self.overrides["activated"].function(self, self._rag2f_instance)

        self._active = True

    def deactivate(self):
        """Deactivate the plugin: run deactivation and unload hooks/overrides."""
        # run custom deactivation from @plugin
        if "deactivated" in self.overrides:
            self.overrides["deactivated"].function(self, self._rag2f_instance)

        # UnLoad of hook and ovverided functions
        self._unload_decorated_functions()
        self._active = False

    def _module_name_for_file(self, py_file: str) -> str:
        rel = os.path.relpath(py_file, start=self._path)
        rel_mod = rel.replace(os.sep, ".").replace(".py", "")
        return f"plugins.{self._id}.{rel_mod}"

    def _load_manifest(self) -> PluginManifest:
        plugin_path = Path(self._path)
        path_str = str(plugin_path)
        is_pip_like = "site-packages" in path_str or "dist-packages" in path_str
        logger.info(
            "Loading plugin manifest for '%s' (source=%s)",
            self._id,
            "pip" if is_pip_like else "fs",
        )

        plugin_json_paths = self._discover_metadata_files(plugin_path, "plugin.json")
        pyproject_paths = self._discover_metadata_files(plugin_path, "pyproject.toml")

        plugin_json_path = plugin_json_paths[0] if plugin_json_paths else None
        pyproject_path = pyproject_paths[0] if pyproject_paths else None

        logger.info(
            "Discovered metadata for '%s': plugin.json=%s, pyproject.toml=%s",
            self._id,
            str(plugin_json_path) if plugin_json_path else "<missing>",
            str(pyproject_path) if pyproject_path else "<missing>",
        )

        base: dict = {}
        override: dict = {}
        fallback: dict = {}
        requirements: list[str] = []
        rag2f_bounds_origin: str = "Unknown"

        if plugin_json_path is not None:
            data = self._read_json_file(plugin_json_path)
            base = self._map_plugin_json_to_manifest(data)

        if pyproject_path is not None:
            data = self._read_toml_file(pyproject_path)
            override = self._map_pyproject_to_manifest(data)
            requirements.extend(self._extract_pyproject_dependencies(data))

        if base:
            json_min = PluginManifest.normalize_str(base.get("min_rag2f_version"))
            json_max = PluginManifest.normalize_str(base.get("max_rag2f_version"))
            json_bounds_set = bool(json_min or json_max)
            if json_bounds_set:
                rag2f_bounds_origin = "JSON"
        else:
            json_bounds_set = False

        distribution = None
        if is_pip_like:
            distribution = self._resolve_distribution_for_plugin(plugin_path)
            if distribution is not None:
                dist_name = distribution.metadata.get("Name", "<unknown>")
                logger.info("Resolved distribution for '%s': %s", self._id, dist_name)

                dist_plugin_json = self._find_dist_file(distribution, "plugin.json")
                if plugin_json_path is None and dist_plugin_json is not None:
                    logger.info(
                        "Using plugin.json from distribution (FS missing): %s", dist_plugin_json
                    )
                    data = self._read_json_file(Path(dist_plugin_json))
                    base = self._map_plugin_json_to_manifest(data)
                    json_min = PluginManifest.normalize_str(base.get("min_rag2f_version"))
                    json_max = PluginManifest.normalize_str(base.get("max_rag2f_version"))
                    json_bounds_set = bool(json_min or json_max)
                    if json_bounds_set:
                        rag2f_bounds_origin = "JSON"

                dist_pyproject = self._find_dist_file(distribution, "pyproject.toml")
                if pyproject_path is None and dist_pyproject is not None:
                    logger.info(
                        "Using pyproject.toml from distribution (FS missing): %s", dist_pyproject
                    )
                    data = self._read_toml_file(Path(dist_pyproject))
                    override = self._map_pyproject_to_manifest(data)
                    requirements.extend(self._extract_pyproject_dependencies(data))

                fallback = self._map_distribution_metadata_to_manifest(distribution)
                dist_requires = [r for r in (distribution.requires or []) if isinstance(r, str)]
                requirements.extend(dist_requires)
            else:
                logger.warning("No distribution metadata found for '%s'", self._id)

        merged = PluginManifest.override_if_non_empty(
            base,
            override,
            exclude=("min_rag2f_version", "max_rag2f_version"),
        )

        overridden_by_pyproject = sorted(
            {
                key
                for key, value in override.items()
                if PluginManifest.normalize_str(value) is not None
                and PluginManifest.normalize_str(base.get(key))
                != PluginManifest.normalize_str(value)
            }
        )
        if overridden_by_pyproject:
            logger.info(
                "Pyproject overrides for '%s': %s",
                self._id,
                ", ".join(overridden_by_pyproject),
            )

        if is_pip_like and fallback:
            before_fallback = dict(merged)
            merged = PluginManifest.apply_fallback_defaults(merged, fallback)
            filled = sorted(
                {
                    k
                    for k, v in merged.items()
                    if PluginManifest.normalize_str(v)
                    != PluginManifest.normalize_str(before_fallback.get(k))
                    and k in fallback
                }
            )
            if filled:
                logger.info(
                    "Distribution metadata fallback filled for '%s': %s",
                    self._id,
                    ", ".join(filled),
                )

        # name resolution: try sources, else humanize id
        normalized_name = PluginManifest.normalize_str(merged.get("name"))
        if normalized_name is None:
            merged["name"] = inflection.humanize(self.id)
            logger.warning(
                "Manifest name missing for '%s'; defaulting to humanized id '%s'",
                self._id,
                merged["name"],
            )

        if not json_bounds_set:
            min_v, max_v, origin = self._derive_rag2f_bounds_from_requirements(requirements)
            if origin != "Unknown":
                rag2f_bounds_origin = origin
            if (
                PluginManifest.normalize_str(merged.get("min_rag2f_version")) is None
                and min_v is not None
            ):
                merged["min_rag2f_version"] = min_v
            if (
                PluginManifest.normalize_str(merged.get("max_rag2f_version")) is None
                and max_v is not None
            ):
                merged["max_rag2f_version"] = max_v

        logger.info(
            "rag2f bounds for '%s': origin=%s min=%s max=%s",
            self._id,
            rag2f_bounds_origin,
            merged.get("min_rag2f_version", "Unknown"),
            merged.get("max_rag2f_version", "Unknown"),
        )

        return PluginManifest(**merged)

    # ----------------------------
    # Helpers (no new dependencies)
    # ----------------------------
    def _read_json_file(self, path: Path) -> dict:
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            raise ValueError(f"Invalid JSON in {path}: {type(e).__name__}: {e}") from e

    def _read_toml_file(self, path: Path) -> dict:
        try:
            try:
                import tomllib  # py3.11+
            except ModuleNotFoundError:  # pragma: no cover
                import tomli as tomllib  # type: ignore

            with open(path, "rb") as f:
                return tomllib.load(f)
        except Exception as e:
            raise ValueError(f"Invalid TOML in {path}: {type(e).__name__}: {e}") from e

    def _map_plugin_json_to_manifest(self, data: dict) -> dict:
        out: dict = {}

        out["name"] = PluginManifest.normalize_str(data.get("name"))
        out["version"] = PluginManifest.normalize_str(data.get("version"))
        out["keywords"] = PluginManifest.join_keywords(data.get("keywords"))
        out["description"] = PluginManifest.normalize_str(data.get("description"))
        out["license"] = PluginManifest.normalize_str(data.get("license"))
        out["urls"] = PluginManifest.serialize_urls(data.get("urls"))
        out["min_rag2f_version"] = PluginManifest.normalize_str(data.get("min_rag2f_version"))
        out["max_rag2f_version"] = PluginManifest.normalize_str(data.get("max_rag2f_version"))

        # author mapping (supports legacy author object)
        out["author_name"] = PluginManifest.normalize_str(data.get("author_name"))
        out["author_email"] = PluginManifest.normalize_str(data.get("author_email"))

        author_obj = data.get("author")
        if (out.get("author_name") is None or out.get("author_email") is None) and isinstance(
            author_obj, dict
        ):
            if out.get("author_name") is None:
                out["author_name"] = PluginManifest.normalize_str(author_obj.get("name"))
            if out.get("author_email") is None:
                out["author_email"] = PluginManifest.normalize_str(author_obj.get("email"))

        # Remove unset fields so defaults apply cleanly
        return {k: v for k, v in out.items() if v is not None}

    def _map_pyproject_to_manifest(self, data: dict) -> dict:
        project = data.get("project") if isinstance(data, dict) else None
        if not isinstance(project, dict):
            return {}

        out: dict = {}
        out["name"] = PluginManifest.normalize_str(project.get("name"))

        # version may be dynamic; if not a string, skip
        version = project.get("version")
        out["version"] = (
            PluginManifest.normalize_str(version) if isinstance(version, str) else None
        )

        out["description"] = PluginManifest.normalize_str(project.get("description"))
        out["keywords"] = PluginManifest.join_keywords(project.get("keywords"))

        # authors: first element
        authors = project.get("authors")
        if isinstance(authors, list) and authors:
            first = authors[0]
            if isinstance(first, dict):
                out["author_name"] = PluginManifest.normalize_str(first.get("name"))
                out["author_email"] = PluginManifest.normalize_str(first.get("email"))

        # license: string or table
        lic = project.get("license")
        if isinstance(lic, str):
            out["license"] = PluginManifest.normalize_str(lic)
        elif isinstance(lic, dict):
            out["license"] = PluginManifest.normalize_str(
                lic.get("text")
            ) or PluginManifest.normalize_str(lic.get("file"))

        out["urls"] = PluginManifest.serialize_urls(project.get("urls"))

        return {k: v for k, v in out.items() if v is not None}

    def _extract_pyproject_dependencies(self, data: dict) -> list[str]:
        project = data.get("project") if isinstance(data, dict) else None
        if not isinstance(project, dict):
            return []
        deps = project.get("dependencies")
        if not isinstance(deps, list):
            return []
        return [d for d in deps if isinstance(d, str)]

    def _map_distribution_metadata_to_manifest(
        self, dist: importlib.metadata.Distribution
    ) -> dict:
        md = dist.metadata
        out: dict = {}

        out["name"] = PluginManifest.normalize_str(md.get("Name"))
        out["version"] = PluginManifest.normalize_str(
            getattr(dist, "version", None) or md.get("Version")
        )
        out["description"] = PluginManifest.normalize_str(md.get("Summary"))
        out["author_name"] = PluginManifest.normalize_str(md.get("Author"))
        out["author_email"] = PluginManifest.normalize_str(md.get("Author-email"))
        out["license"] = PluginManifest.normalize_str(md.get("License"))
        out["keywords"] = PluginManifest.normalize_str(md.get("Keywords"))

        # URLs: Home-page + Project-URL (may repeat)
        urls_parts: list[str] = []
        home = PluginManifest.normalize_str(md.get("Home-page"))
        if home:
            urls_parts.append(f"Homepage={home}")
        project_urls = []
        try:
            project_urls = md.get_all("Project-URL") or []
        except Exception:
            project_urls = []
        for entry in project_urls:
            s = PluginManifest.normalize_str(entry)
            if s:
                urls_parts.append(s)
        out["urls"] = ", ".join(urls_parts) if urls_parts else None

        return {k: v for k, v in out.items() if v is not None}

    def _discover_metadata_files(self, plugin_path: Path, name: str) -> list[Path]:
        root_file = plugin_path / name
        if root_file.is_file():
            return [root_file]

        candidates = [p for p in plugin_path.glob(f"**/{name}") if p.is_file()]
        candidates.sort(key=lambda p: (len(p.relative_to(plugin_path).parents), str(p)))
        return candidates

    def _resolve_distribution_for_plugin(self, plugin_path: Path):
        # Try by folder name and common normalizations
        folder = plugin_path.name
        candidates = {
            folder,
            folder.replace("_", "-"),
            folder.replace("-", "_"),
        }
        if folder.startswith("rag2f_"):
            candidates.add("rag2f-" + folder[len("rag2f_") :].replace("_", "-"))
        if folder.startswith("rag2f-"):
            candidates.add("rag2f_" + folder[len("rag2f-") :].replace("-", "_"))

        for name in [c for c in candidates if c]:
            try:
                return importlib.metadata.distribution(name)
            except importlib.metadata.PackageNotFoundError:
                continue
            except Exception as e:
                logger.debug("Error resolving distribution for '%s': %s", name, e, exc_info=True)
                continue

        # Fallback: scan distributions and match files against package dir
        try:
            for dist in importlib.metadata.distributions():
                files = dist.files or []
                for f in files:
                    p = str(f)
                    # Match typical package layout
                    if p.startswith(folder + "/"):
                        return dist
        except Exception as e:
            logger.debug(
                "Error scanning distributions while resolving plugin '%s': %s",
                plugin_path,
                e,
                exc_info=True,
            )
            return None
        return None

    def _find_dist_file(self, dist: importlib.metadata.Distribution, filename: str) -> str | None:
        files = dist.files or []
        matches: list[str] = []
        for f in files:
            p = str(f)
            if p.endswith("/" + filename) or p == filename:
                try:
                    matches.append(str(dist.locate_file(f)))
                except Exception as e:
                    logger.debug(
                        "Error locating dist file '%s' for '%s': %s",
                        filename,
                        dist,
                        e,
                        exc_info=True,
                    )
                    continue
        return sorted(matches)[0] if matches else None

    def _normalize_pkg_name(self, name: str) -> str:
        return re.sub(r"[-_.]+", "", name).lower().strip()

    def _derive_rag2f_bounds_from_requirements(
        self, requirements: list[str]
    ) -> tuple[str | None, str | None, str]:
        if not requirements:
            return None, None, "Unknown"

        min_v: str | None = None
        max_v: str | None = None

        matched_any = False

        for req in requirements:
            if not isinstance(req, str):
                continue
            raw = req.split(";", 1)[0].strip()
            if not raw:
                continue
            m = re.match(r"^\s*([A-Za-z0-9][A-Za-z0-9_.-]*)(\[[^\]]+\])?\s*(.*)$", raw)
            if not m:
                continue
            name = m.group(1)
            if self._normalize_pkg_name(name) != self._normalize_pkg_name("rag2f"):
                continue

            matched_any = True

            spec_part = (m.group(3) or "").strip()
            if not spec_part:
                continue

            # Split on commas, parse simple operators
            parts = [p.strip() for p in spec_part.split(",") if p.strip()]

            # If '==' is present in this requirement, it must set max only.
            has_eq = any(re.match(r"^==\s*[^\s]+\s*$", p) for p in parts)

            temp_min: str | None = None
            temp_max: str | None = None
            temp_eq: str | None = None

            for part in parts:
                mm = re.match(r"^(==|>=|>|<=|<|~=)\s*([^\s]+)\s*$", part)
                if not mm:
                    logger.warning("Unparseable rag2f requirement specifier: %s", part)
                    continue
                op, ver = mm.group(1), mm.group(2)
                if op in (">=", ">"):
                    if not has_eq:
                        temp_min = ver  # policy: last declared wins
                elif op in ("<=", "<"):
                    temp_max = ver
                elif op == "==":
                    temp_eq = ver  # REQUIRED: max takes == (and min unchanged)
                else:
                    # ~= and others: do not infer max to avoid semantics
                    continue

            # Merge this requirement into running bounds
            if temp_min is not None:
                min_v = temp_min
            if temp_eq is not None:
                max_v = temp_eq
            elif temp_max is not None:
                max_v = temp_max

        if not matched_any:
            return None, None, "Unknown"
        return min_v, max_v, "Dependency"

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
        # we assign them module names like:
        #   'plugins.rag2f_azure_openai_embedder.src.bootstrap_hook'.
        #
        # However, if those files contain relative imports
        # (e.g., "from .plugin_context import ..."),
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
        if "plugins" not in sys.modules:
            import types

            plugins_pkg = types.ModuleType("plugins")
            plugins_pkg.__path__ = []  # Empty path list makes it a namespace package
            plugins_pkg.__package__ = "plugins"
            sys.modules["plugins"] = plugins_pkg
            logger.debug("Created dummy 'plugins' package in sys.modules for relative imports")

        # Create 'plugins.<plugin_id>' package if it doesn't exist
        # This represents the root of this specific plugin
        plugin_pkg_name = f"plugins.{self._id}"
        if plugin_pkg_name not in sys.modules:
            import types

            plugin_pkg = types.ModuleType(plugin_pkg_name)
            plugin_pkg.__path__ = [self._path]  # Point to the actual plugin directory
            plugin_pkg.__package__ = plugin_pkg_name
            plugin_pkg.__file__ = os.path.join(self._path, "__init__.py")
            sys.modules[plugin_pkg_name] = plugin_pkg
            logger.debug(
                f"Created dummy '{plugin_pkg_name}' package in sys.modules for relative imports"
            )

        for py_file in self.py_files:
            # Normalize the module name to a stable namespace (plugins.<plugin_id>.<relative_path>)
            # This avoids issues where the same file is imported with different module names
            # (e.g., 'plugins.rag2f_azure_openai_embedder.src.bootstrap_hook' vs
            # '.workspaces.rag2f.plugins.rag2f_azure_openai_embedder.src.bootstrap_hook')
            # which would cause Python to treat them as different modules, leading to
            # duplicate imports, decorator side effects, and overwritten hook metadata.
            # By using a consistent module name, we ensure each plugin file is loaded only once.
            # Hook metadata (like plugin_id) is not accidentally overwritten by duplicate imports.
            module_name = self._module_name_for_file(py_file)

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
                    try:
                        spec.loader.exec_module(plugin_module)
                    except Exception:
                        # If execution fails, remove the partially-loaded module so
                        # a subsequent load attempt isn't stuck reusing a broken module.
                        if sys.modules.get(module_name) is plugin_module:
                            del sys.modules[module_name]
                        raise

                hooks += getmembers(plugin_module, self._is_rag2f_hook)
                plugin_overrides += getmembers(plugin_module, self._is_rag2f_plugin_override)

            except Exception as e:
                logger.error(
                    f"Error in {py_file}. Unable to load plugin {self._id}: {type(e).__name__}: {e}",
                    exc_info=True,
                )
                logger.warning(self.plugin_specific_error_message())

        # clean and enrich instances
        self._hooks = list(map(self._clean_and_enrich_hook, hooks))
        self._plugin_overrides = {
            override.name: override
            for override in list(map(self._clean_plugin_override, plugin_overrides))
        }

    def _unload_decorated_functions(self) -> None:
        """Unload previously loaded plugin modules from sys.modules.

        This mirrors the stable module naming used by _load_decorated_functions
        (plugins.<plugin_id>.<relative_path>), and removes any submodules created
        via relative imports under that namespace.
        """
        plugin_pkg_name = f"plugins.{self._id}"
        to_remove = [
            name
            for name in list(sys.modules.keys())
            if name == plugin_pkg_name or name.startswith(plugin_pkg_name + ".")
        ]

        for name in to_remove:
            logger.debug(f"Remove module {name}")
            sys.modules.pop(name, None)

        self._hooks = []
        self._plugin_overrides = {}

    #
    def plugin_specific_error_message(self):
        """Return a user-facing message to help report plugin load failures."""
        name = getattr(self.manifest, "name", None) or self._id

        url = None
        # Backward/forward compatibility: some manifests may expose plugin_url,
        # current model exposes a generic 'urls' field.
        if hasattr(self.manifest, "plugin_url"):
            url = self.manifest.plugin_url
        else:
            url = getattr(self.manifest, "urls", None)

        if isinstance(url, str):
            url = url.strip()
            if not url or url.lower() == "unknown":
                url = None

        if url:
            return (
                f"To resolve any problem related to {name} plugin, contact the creator using "
                f"issue system ( es: github issue ) at the link {url}"
            )
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
            logger.debug(
                f"Hook '{h.name}' already has plugin_id '{h.plugin_id}', skipping (current plugin: '{self._id}')"
            )
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
        """Install plugin requirements using the default installer.

        Args:
            plugin_id: The plugin identifier (used for logs).
            plugin_path: Filesystem path to the plugin folder.
        """
        # Static method for backward compatibility, uses PackageInstaller
        installer = PackageInstaller(plugin_id, plugin_path)
        installer.install()

    @property
    def path(self):
        """Return the plugin filesystem path."""
        return self._path

    @property
    def id(self):
        """Return the plugin id (folder name)."""
        return self._id

    @property
    def manifest(self):
        """Return the loaded plugin manifest."""
        return self._manifest

    @property
    def hooks(self):
        """Return the list of hooks discovered in this plugin."""
        return self._hooks

    @property
    def overrides(self):
        """Return lifecycle overrides discovered in this plugin."""
        return self._plugin_overrides

    @property
    def active(self):
        """Return True when the plugin is currently active."""
        return self._active
