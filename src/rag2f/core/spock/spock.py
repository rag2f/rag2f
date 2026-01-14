"""Spock - Configuration Manager for RAG2F.

Spock manages configuration from JSON files and environment variables,
providing a unified interface for accessing settings throughout the application.

Configuration hierarchy:
- rag2f: Core RAG2F settings
  - embedder_default: Default embedder to use
  - ... (other core settings)
- plugins: Plugin-specific configurations
  - <plugin_id>: Configuration for each plugin
    - ... (plugin-specific settings)

Environment variables follow the naming convention:
RAG2F__<section>__<key> for nested values
Example: RAG2F__RAG2F__EMBEDDER_DEFAULT="test_embedder"
         RAG2F__PLUGINS__AZURE_OPENAI_EMBEDDER__API_KEY="..."
"""

import json
import logging
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class Spock:
    """Configuration manager for RAG2F instances.

    Each RAG2F instance has its own Spock instance to maintain
    isolated configuration state.

    Famous quote from Spock in Star Trek:
    "Logic is the beginning of wisdom, not the end."
    """

    ENV_PREFIX = "RAG2F"
    ENV_SEPARATOR = "__"

    def __init__(self, config_path: str | None = None):
        """Initialize Spock configuration manager.

        Args:
            config_path: Path to JSON configuration file. If None, only
                        environment variables will be used.
        """
        self._config_path = config_path
        self._config = self.default_config()
        self._loaded = False
        logger.debug("Spock instance created with config_path=%s", config_path)

    @staticmethod
    def default_config() -> dict[str, Any]:
        """Return a new default config dict each time."""
        return {"rag2f": {}, "plugins": {}}

    def load(self, config: dict[str, Any] | None = None) -> None:
        """Load configuration from JSON file, environment variables, or provided config.

        Args:
            config: Optional config dict to use as base. If None, uses default_config().

        Priority (highest to lowest):
        1. Environment variables
        2. JSON file
        3. Provided config (if any)
        4. Default values
        """
        if self._loaded:
            logger.debug("Configuration already loaded, skipping reload")
            return

        self._config = self.default_config()

        # Load from JSON file if provided
        if self._config_path:
            self._load_from_json()

        if config is not None:
            self._load_from_config_object(config)

        # Override/merge with environment variables
        self._load_from_env()

        self._loaded = True
        logger.info("Configuration loaded successfully")
        logger.debug(
            "Final config structure: rag2f keys=%s, plugins=%s",
            list(self._config.get("rag2f", {}).keys()),
            list(self._config.get("plugins", {}).keys()),
        )

    def _load_from_json(self) -> None:
        """Load configuration from JSON file."""
        try:
            config_file = Path(self._config_path)
            if not config_file.exists():
                logger.warning("Config file not found: %s", self._config_path)
                return

            with open(config_file, encoding="utf-8") as f:
                json_config = json.load(f)

            # Validate and merge JSON structure
            if not isinstance(json_config, dict):
                raise ValueError("Configuration must be a JSON object")

            # Merge rag2f settings
            if "rag2f" in json_config:
                if not isinstance(json_config["rag2f"], dict):
                    raise ValueError("'rag2f' section must be an object")
                self._config["rag2f"] = deepcopy(json_config["rag2f"])

            # Merge plugin settings
            if "plugins" in json_config:
                if not isinstance(json_config["plugins"], dict):
                    raise ValueError("'plugins' section must be an object")
                self._config["plugins"] = deepcopy(json_config["plugins"])

            logger.info("Loaded configuration from JSON: %s", self._config_path)

        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in config file %s: %s", self._config_path, e)
            raise ValueError(f"Invalid JSON configuration file: {e}") from e
        except Exception as e:
            logger.error("Error loading config file %s: %s", self._config_path, e)
            raise

    def _load_from_config_object(self, config: dict[str, Any]) -> None:
        """Validate and merge a config dict into self._config, like for JSON."""
        if not isinstance(config, dict):
            raise ValueError("Configuration must be a dict")

        # Merge rag2f settings
        if "rag2f" in config:
            if not isinstance(config["rag2f"], dict):
                raise ValueError("'rag2f' section must be a dict")
            self._config["rag2f"] = deepcopy(config["rag2f"])

        # Merge plugin settings
        if "plugins" in config:
            if not isinstance(config["plugins"], dict):
                raise ValueError("'plugins' section must be a dict")
            self._config["plugins"] = deepcopy(config["plugins"])

    def _load_from_env(self) -> None:
        """Load configuration from environment variables.

        Environment variables follow the pattern:
        RAG2F__<SECTION>__<KEY>__<SUBKEY>...

        Examples:
        - RAG2F__RAG2F__EMBEDDER_DEFAULT=azure_openai
        - RAG2F__PLUGINS__AZURE_OPENAI_EMBEDDER__API_KEY=sk-xxx
        - RAG2F__PLUGINS__AZURE_OPENAI_EMBEDDER__AZURE_ENDPOINT=https://...
        """
        prefix = f"{self.ENV_PREFIX}{self.ENV_SEPARATOR}"

        for env_key, env_value in os.environ.items():
            if not env_key.startswith(prefix):
                continue

            # Remove prefix and split into path components
            key_path = env_key[len(prefix) :].split(self.ENV_SEPARATOR)

            if len(key_path) < 2:
                logger.warning("Invalid env var format (too short): %s", env_key)
                continue

            section = key_path[0].lower()  # 'rag2f' or 'plugins'

            # Validate section
            if section not in ("rag2f", "plugins"):
                logger.warning("Invalid section in env var %s: %s", env_key, section)
                continue

            # Parse and set the value
            try:
                parsed_value = self._parse_env_value(env_value)
                self._set_nested_value(section, key_path[1:], parsed_value)
                logger.debug("Set from env: %s = %s", env_key, parsed_value)
            except Exception as e:
                logger.error("Error processing env var %s: %s", env_key, e)

    def _parse_env_value(self, value: str) -> Any:
        """Parse environment variable value with type inference.

        Attempts to parse as JSON first, falls back to string.
        """
        # Try to parse as JSON (handles numbers, booleans, null, arrays, objects)
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            # Return as string
            return value

    def _set_nested_value(self, section: str, path: list[str], value: Any) -> None:
        """Set a value in nested configuration structure.

        Args:
            section: Top-level section ('rag2f' or 'plugins')
            path: List of keys representing the path to the value
            value: Value to set
        """
        if section == "rag2f":
            # For rag2f section, path is direct: [EMBEDDER_DEFAULT] -> embedder_default
            target = self._config["rag2f"]
            for key in path[:-1]:
                key_lower = key.lower()
                if key_lower not in target:
                    target[key_lower] = {}
                target = target[key_lower]
            target[path[-1].lower()] = value

        elif section == "plugins":
            # For plugins section, first key is plugin_id: [PLUGIN_ID, KEY, SUBKEY]
            if len(path) < 2:
                logger.warning("Plugin env var too short: %s", path)
                return

            plugin_id = path[0].lower()
            if plugin_id not in self._config["plugins"]:
                self._config["plugins"][plugin_id] = {}

            target = self._config["plugins"][plugin_id]
            for key in path[1:-1]:
                key_lower = key.lower()
                if key_lower not in target:
                    target[key_lower] = {}
                target = target[key_lower]
            target[path[-1].lower()] = value

    def get_rag2f_config(self, key: str | None = None, default: Any = None) -> Any:
        """Get RAG2F core configuration.

        Args:
            key: Specific configuration key. If None, returns entire rag2f config.
            default: Default value if key not found.

        Returns:
            Configuration value or default.
        """
        if not self._loaded:
            self.load()

        if key is None:
            return deepcopy(self._config.get("rag2f", {}))

        return self._config.get("rag2f", {}).get(key, default)

    def get_plugin_config(
        self, plugin_id: str, key: str | None = None, default: Any = None
    ) -> Any:
        """Get plugin-specific configuration.

        Args:
            plugin_id: Plugin identifier
            key: Specific configuration key. If None, returns entire plugin config.
            default: Default value if key not found.

        Returns:
            Configuration value or default.
        """
        if not self._loaded:
            self.load()

        plugin_config = self._config.get("plugins", {}).get(plugin_id, {})

        if key is None:
            return deepcopy(plugin_config)

        return plugin_config.get(key, default)

    def set_rag2f_config(self, key: str, value: Any) -> None:
        """Set RAG2F core configuration (runtime only, not persisted).

        Args:
            key: Configuration key
            value: Configuration value
        """
        if not self._loaded:
            self.load()

        self._config["rag2f"][key] = value
        logger.debug("Set rag2f config: %s = %s", key, value)

    def set_plugin_config(self, plugin_id: str, key: str, value: Any) -> None:
        """Set plugin configuration (runtime only, not persisted).

        Args:
            plugin_id: Plugin identifier
            key: Configuration key
            value: Configuration value
        """
        if not self._loaded:
            self.load()

        if plugin_id not in self._config["plugins"]:
            self._config["plugins"][plugin_id] = {}

        self._config["plugins"][plugin_id][key] = value
        logger.debug("Set plugin config: %s.%s = %s", plugin_id, key, value)

    def get_all_config(self) -> dict[str, Any]:
        """Get complete configuration snapshot.

        Returns:
            Deep copy of entire configuration.
        """
        if not self._loaded:
            self.load()

        return deepcopy(self._config)

    def reload(self) -> None:
        """Reload configuration from sources.

        Useful for picking up configuration changes at runtime.
        """
        self._loaded = False
        self.load()
        logger.info("Configuration reloaded")

    @property
    def config_path(self) -> str | None:
        """Get the configuration file path."""
        return self._config_path

    @property
    def is_loaded(self) -> bool:
        """Check if configuration has been loaded."""
        return self._loaded


ConfigManager = Spock
