import os
import pytest
import subprocess
import shutil

from inspect import isfunction

from rag2f.core.morpheus.plugin_manifest import PluginManifest
from tests.utils import get_mock_plugin_info


from rag2f.core.morpheus.plugin import Plugin
from rag2f.core.morpheus.decorators import PillHook
from rag2f.core.utils import get_plugins_path
from tests.utils import PATH_MOCK 


# this fixture will give test functions a ready instantiated plugin
# (and having the `client` fixture, a clean setup every unit)
@pytest.fixture(scope="function")
def plugin(morpheus):   
    p = morpheus.plugins["mock_plugin"]
    yield p


def test_create_plugin_wrong_folder():
    with pytest.raises(Exception) as e:
        Plugin("/non/existent/folder")

    assert "Cannot create" in str(e.value)


def test_not_create_plugin_with_empty_folder():
    path = f"{PATH_MOCK}/empty_folder"

    with pytest.raises(Exception) as e:
        Plugin(path)

    assert "Cannot create" in str(e.value)
    


def test_create_plugin(plugin):
    
    assert plugin.path == f"{PATH_MOCK}/plugins/mock_plugin/"
    assert plugin.id == "mock_plugin"

    # manifest
    assert isinstance(plugin.manifest, PluginManifest)
    assert plugin.manifest.name == "Mock plugin"
    assert "Description not found" in plugin.manifest.description

    # hooks
    assert len(plugin.hooks) == get_mock_plugin_info()["hooks"]
    assert len(plugin.overrides) == 1

    assert not hasattr(plugin, "custom_deactivation_executed")


def test_activate_plugin(plugin):
    # hooks
    assert len(plugin.hooks) == get_mock_plugin_info()["hooks"]
    for hook in plugin.hooks:
        assert isinstance(hook, PillHook)
        assert hook.plugin_id == "mock_plugin"
        assert hook.name in [
            "morpheus_test_hook_message",
            "rag2f_bootstrap_embedders"
        ]
        assert isfunction(hook.function)

        if hook.name == "morpheus_test_hook_message":
            assert hook.priority > 1
        else:
            assert hook.priority == 1  # default priority


    # overrides by @plugin decorator
    assert len(plugin.overrides) == 1
    assert plugin.custom_id == plugin.id
    assert set(plugin.overrides.keys()) == {"activated"}
    assert not hasattr(plugin, "custom_deactivation_executed")


def test_settings_schema(plugin):
    settings_schema = plugin.settings_schema()
    assert isinstance(settings_schema, dict)
    assert settings_schema["properties"] == {}
    assert settings_schema["title"] == "PluginSettingsModel"
    assert settings_schema["type"] == "object"


def test_load_settings(plugin):
    settings = plugin.load_settings()
    assert settings == {}


def test_save_settings(plugin):
    fake_settings = {"a": 42}
    plugin.save_settings(fake_settings)

    settings = plugin.load_settings()
    assert settings["a"] == fake_settings["a"]
    # Try to delete the file, if it fails the test should fail because the file must exist
    try:
        os.remove(plugin.settings_file_path)
    except FileNotFoundError:
        pytest.fail(f"File {plugin.settings_file_path} not found, but it should exist")


# utility ot obtain installed python packages
def list_packages():
    result = subprocess.run(["uv", "pip", "list"], stdout=subprocess.PIPE)
    return str(result.stdout.decode()) 


# Check if plugin requirements have been installed
def test_install_plugin_dependencies(plugin):

    result = list_packages()
    assert "pip-install-test" in result



