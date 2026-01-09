import os
import pytest
import subprocess
import shutil

from inspect import isfunction

from rag2f.core.morpheus.plugin_manifest import PluginManifest
from tests.utils import get_mock_plugin_info
from rag2f.core.morpheus.plugin import Plugin
from rag2f.core.morpheus.decorators import PillHook
from tests.utils import PATH_MOCK 


# this fixture will give test functions a ready instantiated plugin
# (and having the `client` fixture, a clean setup every unit)
@pytest.fixture(scope="function")
def plugin(morpheus, rag2f):
    # Ensure plugin config is clean for each test
    rag2f.spock._config.setdefault("plugins", {}).pop("mock_plugin", None)
    p = morpheus.plugins["mock_plugin"]
    yield p


def test_create_plugin_wrong_folder(rag2f):
    with pytest.raises(Exception) as e:
        Plugin(rag2f, "/non/existent/folder")

    assert "Cannot create" in str(e.value)


def test_not_create_plugin_with_empty_folder(rag2f):
    path = f"{PATH_MOCK}/empty_folder"

    with pytest.raises(Exception) as e:
        Plugin(rag2f, path)

    assert "Cannot create" in str(e.value)
    


def test_create_plugin(plugin):
    
    assert plugin.path == f"{PATH_MOCK}/plugins/mock_plugin/"
    assert plugin.id == "mock_plugin"

    # manifest
    assert isinstance(plugin.manifest, PluginManifest)
    assert plugin.manifest.name == "Mock plugin"
    assert plugin.manifest.version == "0.0.0"

    # hooks
    assert len(plugin.hooks) == get_mock_plugin_info()["hooks"]
    assert len(plugin.overrides) == 1

    assert not hasattr(plugin, "custom_deactivation_executed")


def test_activate_plugin(plugin):
    # hooks
    assert len(plugin.hooks) == get_mock_plugin_info()["hooks"]
    # Check that plugin._id is set and matches plugin.id
    assert hasattr(plugin, "_id")
    assert plugin._id == plugin.id
    for hook in plugin.hooks:
        assert isinstance(hook, PillHook)
        # Check that hook.plugin_id is set and matches plugin._id
        assert hasattr(hook, "plugin_id")
        assert hook.plugin_id == plugin._id
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


# utility to obtain installed python packages
def list_packages():
    result = subprocess.run(["uv", "pip", "list", "--system"], stdout=subprocess.PIPE)
    return str(result.stdout.decode()) 


@pytest.mark.parametrize("plugin_folder,package_name,install_method", [
    ("mock_plugin", "pip-install-test", "requirements.txt"),
    ("mock_plugin_pyproject", "pip-install-test", "pyproject.toml"),
])
def test_install_plugin_dependencies_methods(plugin_folder, package_name, install_method, rag2f):
    """Test that plugin dependencies are installed during activation.
    
    This test verifies both installation methods work:
    - requirements.txt (mock_plugin)
    - pyproject.toml (mock_plugin_pyproject)
    """
    # Ensure the test package is not installed before the plugin activates
    subprocess.run(
        ["uv", "pip", "uninstall", "--system", package_name], 
        stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE
    )
    
    # Verify it's actually gone
    result_before = list_packages()
    assert package_name not in result_before, \
        f"Package {package_name} should not be installed before plugin activation (method: {install_method})"
    
    # Create a new plugin instance, which will trigger activation and dependency installation
    from rag2f.core.morpheus.plugin import Plugin
    fresh_plugin = Plugin(rag2f, f"{PATH_MOCK}/plugins/{plugin_folder}/")
    fresh_plugin.activate()
    
    # Verify the package was installed during activation
    result_after = list_packages()
    assert package_name in result_after, \
        f"Package {package_name} should be installed after plugin activation (method: {install_method})"


# Keep the old test for backward compatibility if needed
def test_install_plugin_dependencies(plugin, rag2f):
    """Test that plugin dependencies from requirements.txt are installed (legacy test)."""
    subprocess.run(
        ["uv", "pip", "uninstall", "--system", "pip-install-test"], 
        stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE
    )
    
    result_before = list_packages()
    assert "pip-install-test" not in result_before
    
    from rag2f.core.morpheus.plugin import Plugin
    fresh_plugin = Plugin(rag2f, f"{PATH_MOCK}/plugins/mock_plugin/")
    fresh_plugin.activate()
    
    result_after = list_packages()
    assert "pip-install-test" in result_after



