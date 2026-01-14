"""Tests for Spock configuration system."""

import json
import os
import tempfile

import pytest

from rag2f.core.spock.spock import ConfigManager, Spock


class TestSpockBasics:
    """Test basic Spock functionality."""

    def test_spock_initialization(self):
        """Test that Spock can be initialized with and without config path."""
        # Without config path
        spock = ConfigManager()
        assert spock is not None
        assert not spock.is_loaded
        assert spock.config_path is None

        # With config path
        spock_with_path = ConfigManager(config_path="/path/to/config.json")
        assert spock_with_path.config_path == "/path/to/config.json"
        assert not spock_with_path.is_loaded


class TestSpockJSONConfiguration:
    """Test JSON configuration loading."""

    def test_load_valid_json(self):
        """Test loading valid JSON configuration."""
        config_data = {
            "rag2f": {
                "embedder_default": "test_embedder",
            },
            "plugins": {"test_plugin": {"api_key": "test-key", "timeout": 30.0}},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_path = f.name

        try:
            spock = Spock(config_path=config_path)
            spock.load()

            assert spock.is_loaded
            assert spock.get_rag2f_config("embedder_default") == "test_embedder"
            assert spock.get_plugin_config("test_plugin", "api_key") == "test-key"
            assert spock.get_plugin_config("test_plugin", "timeout") == 30.0
        finally:
            os.unlink(config_path)

    def test_load_missing_file(self):
        """Test that missing config file doesn't crash."""
        spock = Spock(config_path="/nonexistent/config.json")
        spock.load()  # Should not raise

        assert spock.is_loaded
        assert spock.get_rag2f_config() == {}
        assert spock.get_plugin_config("any_plugin") == {}

    def test_load_invalid_json(self):
        """Test that invalid JSON raises error."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{ invalid json }")
            config_path = f.name

        try:
            spock = Spock(config_path=config_path)
            with pytest.raises(ValueError, match="Invalid JSON"):
                spock.load()
        finally:
            os.unlink(config_path)


class TestSpockEnvironmentVariables:
    """Test environment variable configuration."""

    def test_load_from_env_rag2f_section(self):
        """Test loading RAG2F settings from environment."""
        os.environ["RAG2F__RAG2F__EMBEDDER_DEFAULT"] = "test_embedder"
        os.environ["RAG2F__RAG2F__MAX_RETRIES"] = "5"

        try:
            spock = Spock()
            spock.load()

            assert spock.get_rag2f_config("embedder_default") == "test_embedder"
            assert spock.get_rag2f_config("max_retries") == 5  # Should be parsed as int
        finally:
            del os.environ["RAG2F__RAG2F__EMBEDDER_DEFAULT"]
            del os.environ["RAG2F__RAG2F__MAX_RETRIES"]

    def test_load_from_env_plugins_section(self):
        """Test loading plugin settings from environment."""
        os.environ["RAG2F__PLUGINS__MY_PLUGIN__API_KEY"] = "secret-key"
        os.environ["RAG2F__PLUGINS__MY_PLUGIN__TIMEOUT"] = "45.5"
        os.environ["RAG2F__PLUGINS__MY_PLUGIN__ENABLED"] = "true"

        try:
            spock = Spock()
            spock.load()

            assert spock.get_plugin_config("my_plugin", "api_key") == "secret-key"
            assert spock.get_plugin_config("my_plugin", "timeout") == 45.5  # Float
            assert spock.get_plugin_config("my_plugin", "enabled") is True  # Boolean
        finally:
            del os.environ["RAG2F__PLUGINS__MY_PLUGIN__API_KEY"]
            del os.environ["RAG2F__PLUGINS__MY_PLUGIN__TIMEOUT"]
            del os.environ["RAG2F__PLUGINS__MY_PLUGIN__ENABLED"]

    def test_env_overrides_json(self):
        """Test that environment variables override JSON values."""
        config_data = {
            "rag2f": {"embedder_default": "json_embedder"},
            "plugins": {"test_plugin": {"api_key": "json-key"}},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_path = f.name

        os.environ["RAG2F__RAG2F__EMBEDDER_DEFAULT"] = "env_embedder"
        os.environ["RAG2F__PLUGINS__TEST_PLUGIN__API_KEY"] = "env-key"

        try:
            spock = Spock(config_path=config_path)
            spock.load()

            # Environment should override JSON
            assert spock.get_rag2f_config("embedder_default") == "env_embedder"
            assert spock.get_plugin_config("test_plugin", "api_key") == "env-key"
        finally:
            os.unlink(config_path)
            del os.environ["RAG2F__RAG2F__EMBEDDER_DEFAULT"]
            del os.environ["RAG2F__PLUGINS__TEST_PLUGIN__API_KEY"]

    def test_parse_json_in_env_value(self):
        """Test parsing JSON arrays and objects in env values."""
        os.environ["RAG2F__PLUGINS__TEST__TAGS"] = '["tag1", "tag2", "tag3"]'
        os.environ["RAG2F__PLUGINS__TEST__META"] = '{"key": "value", "num": 42}'

        try:
            spock = Spock()
            spock.load()

            tags = spock.get_plugin_config("test", "tags")
            assert tags == ["tag1", "tag2", "tag3"]

            meta = spock.get_plugin_config("test", "meta")
            assert meta == {"key": "value", "num": 42}
        finally:
            del os.environ["RAG2F__PLUGINS__TEST__TAGS"]
            del os.environ["RAG2F__PLUGINS__TEST__META"]


class TestSpockGetters:
    """Test configuration getter methods."""

    import pytest

    @pytest.mark.parametrize(
        "section, config_data, getter, key, expected, default_key, default_value",
        [
            (
                "rag2f",
                {"rag2f": {"key1": "value1", "key2": "value2"}},
                "get_rag2f_config",
                "key1",
                "value1",
                "nonexistent",
                "default_value",
            ),
            (
                "plugins",
                {"plugins": {"my_plugin": {"setting1": "value1", "setting2": 42}}},
                "get_plugin_config",
                "my_plugin",
                {"setting1": "value1", "setting2": 42},
                "nonexistent_plugin",
                "default",
            ),
        ],
    )
    def test_get_config(
        self, section, config_data, getter, key, expected, default_key, default_value
    ):
        """Getter methods should return expected values and defaults."""
        import json
        import os
        import tempfile

        from rag2f.core.spock.spock import Spock

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_path = f.name
        try:
            spock = Spock(config_path=config_path)
            spock.load()
            if section == "rag2f":
                all_config = spock.get_rag2f_config()
                assert all_config == config_data["rag2f"]
                assert getattr(spock, getter)(key) == expected
                assert getattr(spock, getter)(default_key, default=default_value) == default_value
            else:
                plugin_config = spock.get_plugin_config(key)
                assert plugin_config == expected
                assert spock.get_plugin_config(key, "setting1") == "value1"
                assert spock.get_plugin_config(key, "setting2") == 42
                assert (
                    spock.get_plugin_config(default_key, "key", default=default_value)
                    == default_value
                )
        finally:
            os.unlink(config_path)


class TestSpockSetters:
    """Test configuration setter methods."""

    def test_set_config_at_runtime(self):
        """Test setting RAG2F and plugin config at runtime."""
        spock = Spock()
        spock.load()

        # Set RAG2F config
        spock.set_rag2f_config("new_key", "new_value")
        assert spock.get_rag2f_config("new_key") == "new_value"

        # Set plugin config
        spock.set_plugin_config("my_plugin", "setting_key", "setting_value")
        assert spock.get_plugin_config("my_plugin", "setting_key") == "setting_value"


class TestSpockReload:
    """Test configuration reload functionality."""

    def test_reload(self):
        """Test reloading configuration."""
        spock = Spock()
        spock.load()
        assert spock.is_loaded

        spock.reload()
        assert spock.is_loaded

    def test_reload_picks_up_env_changes(self):
        """Test that reload picks up new environment variables."""
        spock = Spock()
        spock.load()

        # Add new env var after initial load
        os.environ["RAG2F__RAG2F__NEW_KEY"] = "new_value"

        try:
            # Should not see it before reload
            spock.reload()

            assert spock.get_rag2f_config("new_key") == "new_value"
        finally:
            del os.environ["RAG2F__RAG2F__NEW_KEY"]


class TestSpockGetAllConfig:
    """Test getting complete configuration."""

    def test_get_all_config(self):
        """Test getting entire configuration snapshot."""
        config_data = {"rag2f": {"key1": "value1"}, "plugins": {"plugin1": {"setting1": "value1"}}}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_path = f.name

        try:
            spock = Spock(config_path=config_path)
            spock.load()

            all_config = spock.get_all_config()
            assert "rag2f" in all_config
            assert "plugins" in all_config
            assert all_config["rag2f"]["key1"] == "value1"
            assert all_config["plugins"]["plugin1"]["setting1"] == "value1"
        finally:
            os.unlink(config_path)
