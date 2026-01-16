"""Tests for the Plugin class and activation lifecycle."""

import os
import shutil
import subprocess
import sys
from inspect import isfunction

import pytest
from tests.utils import PATH_MOCK, get_mock_plugin_info

from rag2f.core.morpheus.decorators import PillHook
from rag2f.core.morpheus.plugin import Plugin
from rag2f.core.morpheus.plugin_manifest import PluginManifest


# this fixture will give test functions a ready instantiated plugin
# (and having the `client` fixture, a clean setup every unit)
@pytest.fixture(scope="function")
def plugin(morpheus, rag2f):
    """Provide a ready-to-use mock plugin instance for tests."""
    # Ensure plugin config is clean for each test
    rag2f.spock._config.setdefault("plugins", {}).pop("mock_plugin", None)
    p = morpheus.plugins["mock_plugin"]
    yield p


def test_create_plugin_wrong_folder(rag2f):
    """Creating a plugin from a missing folder should raise."""
    with pytest.raises(Exception) as e:
        Plugin(rag2f, "/non/existent/folder")

    assert "Cannot create" in str(e.value)


def test_not_create_plugin_with_empty_folder(rag2f):
    """Creating a plugin from an empty folder should raise."""
    path = f"{PATH_MOCK}/empty_folder"

    with pytest.raises(Exception) as e:
        Plugin(rag2f, path)

    assert "Cannot create" in str(e.value)


def test_create_plugin(plugin):
    """Plugin should expose path, id, manifest, hooks, and overrides."""
    assert plugin.path == f"{PATH_MOCK}/plugins/mock_plugin/"
    assert plugin.id == "mock_plugin"

    # manifest
    assert isinstance(plugin.manifest, PluginManifest)
    assert plugin.manifest.name == "Mock plugin"
    assert plugin.manifest.version == "0.0.0"

    # hooks
    assert len(plugin.hooks) == get_mock_plugin_info()["hooks"]
    assert len(plugin.overrides) == 2
    assert set(plugin.overrides.keys()) == {"activated", "deactivated"}

    assert not hasattr(plugin, "custom_deactivation_executed")


def test_activate_plugin(plugin):
    """Activation should load hooks and plugin overrides."""
    # hooks
    assert len(plugin.hooks) == get_mock_plugin_info()["hooks"]
    # Check that plugin._id is set and matches plugin.id
    assert hasattr(plugin, "_id")
    assert plugin._id == plugin.id
    hook_names = {hook.name for hook in plugin.hooks}
    expected_hook_names = {
        "morpheus_test_hook_message",
        "get_id_input_text",
        "check_duplicated_input_text",
        "handle_text_foreground",
        "indiana_jones_retrieve",
        "indiana_jones_search",
    }
    assert hook_names == expected_hook_names
    for hook in plugin.hooks:
        assert isinstance(hook, PillHook)
        # Check that hook.plugin_id is set and matches plugin._id
        assert hasattr(hook, "plugin_id")
        assert hook.plugin_id == plugin._id
        assert isfunction(hook.function)

        if hook.name == "morpheus_test_hook_message":
            assert hook.priority > 1
        else:
            assert hook.priority == 1  # default priority

    # overrides by @plugin decorator
    assert len(plugin.overrides) == 2
    assert plugin.custom_id == plugin.id
    assert set(plugin.overrides.keys()) == {"activated", "deactivated"}
    assert not hasattr(plugin, "custom_deactivation_executed")


def _is_running_in_virtualenv() -> bool:
    """Detect whether the current Python interpreter runs inside a virtualenv."""
    return (
        hasattr(sys, "real_prefix")
        or (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix)
        or os.environ.get("VIRTUAL_ENV") is not None
    )


def _build_pip_command(action: str, args: list[str] | None = None) -> list[str]:
    """Return a pip command that only adds --system when outside a virtualenv."""
    uv = _get_uv_executable()
    cmd = [uv, "pip", action]
    if not _is_running_in_virtualenv():
        cmd.append("--system")
    if args:
        cmd.extend(args)
    return cmd


def _get_uv_executable() -> str:
    """Return uv executable path or skip if missing."""
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv is required for this test")
    return uv


def list_packages():
    """Return a textual list of installed packages (via uv pip list)."""
    result = subprocess.run(  # noqa: S603
        _build_pip_command("list"),
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout


@pytest.mark.parametrize(
    "plugin_folder,package_name,install_method",
    [
        ("mock_plugin", "pip-install-test", "requirements.txt"),
        ("mock_plugin_pyproject", "pip-install-test", "pyproject.toml"),
    ],
)
def test_install_plugin_dependencies_methods(plugin_folder, package_name, install_method, rag2f):
    """Test that plugin dependencies are installed during activation.

    This test verifies both installation methods work:
    - requirements.txt (mock_plugin)
    - pyproject.toml (mock_plugin_pyproject)
    """
    # Ensure the test package is not installed before the plugin activates
    subprocess.run(  # noqa: S603
        _build_pip_command("uninstall", [package_name]),
        capture_output=True,
        text=True,
        check=False,
    )

    # Verify it's actually gone
    result_before = list_packages()
    assert package_name not in result_before, (
        f"Package {package_name} should not be installed before plugin activation (method: {install_method})"
    )

    # Create a new plugin instance, which will trigger activation and dependency installation
    from rag2f.core.morpheus.plugin import Plugin

    fresh_plugin = Plugin(rag2f, f"{PATH_MOCK}/plugins/{plugin_folder}/")
    fresh_plugin.activate()

    # Verify the package was installed during activation
    result_after = list_packages()
    assert package_name in result_after, (
        f"Package {package_name} should be installed after plugin activation (method: {install_method})"
    )


# Keep the old test for backward compatibility if needed
def test_install_plugin_dependencies(plugin, rag2f):
    """Test that plugin dependencies from requirements.txt are installed (legacy test)."""
    subprocess.run(  # noqa: S603
        _build_pip_command("uninstall", ["pip-install-test"]),
        capture_output=True,
        text=True,
        check=False,
    )

    result_before = list_packages()
    assert "pip-install-test" not in result_before

    from rag2f.core.morpheus.plugin import Plugin

    fresh_plugin = Plugin(rag2f, f"{PATH_MOCK}/plugins/mock_plugin/")
    fresh_plugin.activate()

    result_after = list_packages()
    assert "pip-install-test" in result_after
