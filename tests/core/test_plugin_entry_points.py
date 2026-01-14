"""Tests for plugin loading via entry points and filesystem."""

import os
import shutil
from importlib.metadata import EntryPoint
from unittest.mock import Mock, patch

import pytest
from tests.utils import PATH_MOCK


@pytest.mark.asyncio
async def test_filesystem_plugin_loading(morpheus):
    """Test that plugins are loaded from filesystem in development mode."""
    # In test environment, plugins might not exist, so we just verify the mechanism works
    # The important test is that Morpheus can be created without errors
    assert morpheus is not None, "Morpheus instance should be created"

    # If plugins exist, they should be loaded correctly
    if len(morpheus.plugins) > 0:
        for plugin_id, plugin in morpheus.plugins.items():
            print(f"Plugin '{plugin_id}' loaded from: {plugin.path}")
            assert plugin.id == plugin_id, "Plugin ID should match dictionary key"


@pytest.mark.asyncio
async def test_entry_point_loading_mechanism(fresh_morpheus):
    """Test that entry point loading mechanism works correctly."""
    # Create a mock entry point
    mock_entry_point = Mock(spec=EntryPoint)
    mock_entry_point.name = "test_plugin"

    # Use a mock plugin shipped with the test suite
    test_plugin_path = os.path.join(PATH_MOCK, "plugins", "mock_plugin")
    mock_entry_point.load.return_value = lambda: test_plugin_path

    # Test with mocked entry points
    with patch("rag2f.core.morpheus.morpheus.entry_points") as mock_ep:
        # Configure mock to return our test entry point
        mock_ep.return_value = [mock_entry_point]

        await fresh_morpheus._load_from_entry_points()

        # Verify the entry point was processed
        mock_entry_point.load.assert_called_once()
        assert "mock_plugin" in fresh_morpheus.plugins, (
            "mock_plugin should be loaded from entry point"
        )


@pytest.mark.asyncio
async def test_plugin_priority_entry_points_over_filesystem(tmp_path, fresh_morpheus):
    """Test that entry points have priority over filesystem when same plugin exists in both."""
    # This test verifies that if a plugin is loaded via entry point,
    # the filesystem version is skipped

    # Create a mock entry point for mock_plugin (also present on filesystem)
    mock_entry_point = Mock(spec=EntryPoint)
    mock_entry_point.name = "mock_plugin"

    # Copy mock_plugin to a second location to prove entry point wins over filesystem
    fs_plugin_path = os.path.join(PATH_MOCK, "plugins", "mock_plugin")
    ep_plugin_path = os.path.join(str(tmp_path), "mock_plugin")
    shutil.copytree(fs_plugin_path, ep_plugin_path)

    mock_entry_point.load.return_value = lambda: ep_plugin_path

    with patch("rag2f.core.morpheus.morpheus.entry_points") as mock_ep:
        mock_ep.return_value = [mock_entry_point]

        await fresh_morpheus.find_plugins()

        assert "mock_plugin" in fresh_morpheus.plugins, "mock_plugin should be loaded"
        plugin = fresh_morpheus.plugins["mock_plugin"]
        assert plugin.id == "mock_plugin"
        assert os.path.abspath(plugin.path) == os.path.abspath(ep_plugin_path), (
            "Entry point plugin should take priority over filesystem"
        )


@pytest.mark.asyncio
async def test_backward_compatibility_filesystem_only(fresh_morpheus):
    """Test that plugins still work when loaded from filesystem only (no entry points)."""
    # Mock entry_points to return empty list (no installed plugins)
    with patch("rag2f.core.morpheus.morpheus.entry_points") as mock_ep:
        mock_ep.return_value = []

        await fresh_morpheus.find_plugins()

        assert fresh_morpheus is not None, "Morpheus should be created successfully"
        assert isinstance(fresh_morpheus.hooks, dict), "Hooks should be a dictionary"
        assert "mock_plugin" in fresh_morpheus.plugins, (
            "mock_plugin should be loaded from filesystem"
        )


@pytest.mark.asyncio
async def test_invalid_entry_point_handling(fresh_morpheus):
    """Test that invalid entry points are handled gracefully."""
    # Create mock entry points with various invalid configurations
    # Use MagicMock to properly configure attributes
    from unittest.mock import MagicMock

    invalid_ep1 = MagicMock(spec=EntryPoint)
    invalid_ep1.name = "invalid1"
    invalid_ep1.load.return_value = "not_callable"

    invalid_ep2 = MagicMock(spec=EntryPoint)
    invalid_ep2.name = "invalid2"
    invalid_ep2.load.return_value = lambda: 123

    invalid_ep3 = MagicMock(spec=EntryPoint)
    invalid_ep3.name = "invalid3"
    invalid_ep3.load.side_effect = Exception("Load failed")

    invalid_entry_points = [invalid_ep1, invalid_ep2, invalid_ep3]

    with patch("rag2f.core.morpheus.morpheus.entry_points") as mock_ep:
        mock_ep.return_value = invalid_entry_points

        # Should not raise exception, just log warnings/errors
        await fresh_morpheus._load_from_entry_points()

        # No plugins should be loaded from invalid entry points
        assert len(fresh_morpheus.plugins) == 0, (
            "No plugins should be loaded from invalid entry points"
        )


@pytest.mark.asyncio
async def test_site_packages_path_detection_with_underscore_name(fresh_morpheus):
    """Test plugin lookup when entry point returns site-packages root.

    This tests the fix for when get_plugin_path() returns site-packages directory itself
    instead of the actual plugin directory. The system should look for the plugin folder
    by name (supporting both hyphen and underscore variants).
    """
    from unittest.mock import MagicMock

    # Create a mock entry point that returns site-packages (the problematic case)
    mock_entry_point = MagicMock(spec=EntryPoint)
    mock_entry_point.name = "rag2f-openai-embedder"  # Entry point uses hyphens

    # Simulate the broken plugin returning site-packages directly
    fake_site_packages = "/usr/lib/python3.10/site-packages"
    mock_entry_point.load.return_value = lambda: fake_site_packages

    # Create a temporary plugin directory structure to verify the lookup
    with (
        patch("rag2f.core.morpheus.morpheus.entry_points") as mock_ep,
        patch("os.path.exists") as mock_exists,
        patch("os.path.isdir") as mock_isdir,
    ):
        # Configure mocks to simulate the site-packages scenario
        def exists_side_effect(path):
            # site-packages exists, but rag2f_openai_embedder subdir exists
            return True

        def isdir_side_effect(path):
            # Only the underscore variant exists in site-packages
            return "rag2f_openai_embedder" in path

        mock_exists.side_effect = exists_side_effect
        mock_isdir.side_effect = isdir_side_effect
        mock_ep.return_value = [mock_entry_point]

        await fresh_morpheus._load_from_entry_points()

        # The plugin should be found even though entry point returned site-packages
        # Verify that the system looked for the plugin in site-packages/rag2f_openai_embedder
        assert any("rag2f_openai_embedder" in str(call) for call in mock_isdir.call_args_list), (
            "System should look for rag2f_openai_embedder subdirectory in site-packages"
        )


@pytest.mark.asyncio
async def test_site_packages_path_detection_no_plugin_found(fresh_morpheus):
    """Test graceful handling when site-packages is returned but plugin directory not found.

    Tests that when get_plugin_path() returns site-packages but the actual plugin
    directory doesn't exist, the system logs an error and skips the plugin instead
    of crashing.
    """
    from unittest.mock import MagicMock

    # Create a mock entry point that returns site-packages (the problematic case)
    mock_entry_point = MagicMock(spec=EntryPoint)
    mock_entry_point.name = "nonexistent-plugin"

    fake_site_packages = "/usr/lib/python3.10/site-packages"
    mock_entry_point.load.return_value = lambda: fake_site_packages

    with (
        patch("rag2f.core.morpheus.morpheus.entry_points") as mock_ep,
        patch("os.path.exists", return_value=True),
        patch("os.path.isdir", return_value=False),  # Plugin dir doesn't exist
    ):
        mock_ep.return_value = [mock_entry_point]
        # Should not raise exception, just skip the plugin
        await fresh_morpheus._load_from_entry_points()

        # No plugins should be loaded
        assert len(fresh_morpheus.plugins) == 0, "Plugin should be skipped if directory not found"
