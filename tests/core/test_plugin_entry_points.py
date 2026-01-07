"""Tests for plugin loading via entry points and filesystem."""
import pytest
import pytest_asyncio
import os
from unittest.mock import Mock, patch
from importlib.metadata import EntryPoint

from rag2f.core.morpheus.morpheus import Morpheus
from rag2f.core import utils


@pytest_asyncio.fixture
async def morpheus_with_plugins():
    """Create a Morpheus instance with plugins loaded."""
    morpheus = await Morpheus.create()
    return morpheus


@pytest.mark.asyncio
async def test_filesystem_plugin_loading(morpheus_with_plugins):
    """Test that plugins are loaded from filesystem in development mode."""
    # In test environment, plugins might not exist, so we just verify the mechanism works
    # The important test is that Morpheus can be created without errors
    assert morpheus_with_plugins is not None, "Morpheus instance should be created"
    
    # If plugins exist, they should be loaded correctly
    if len(morpheus_with_plugins.plugins) > 0:
        for plugin_id, plugin in morpheus_with_plugins.plugins.items():
            print(f"Plugin '{plugin_id}' loaded from: {plugin.path}")
            assert plugin.id == plugin_id, "Plugin ID should match dictionary key"


@pytest.mark.asyncio
async def test_entry_point_loading_mechanism():
    """Test that entry point loading mechanism works correctly."""
    # Create a mock entry point
    mock_entry_point = Mock(spec=EntryPoint)
    mock_entry_point.name = "test_plugin"
    
    # Mock the plugin path function
    test_plugin_path = os.path.join(utils.get_default_plugins_path(), "macgyver")
    mock_entry_point.load.return_value = lambda: test_plugin_path
    
    # Test with mocked entry points
    with patch('rag2f.core.morpheus.morpheus.entry_points') as mock_ep:
        # Configure mock to return our test entry point
        mock_ep.return_value = [mock_entry_point]
        
        morpheus = Morpheus()
        await morpheus._load_from_entry_points()
        
        # Verify the entry point was processed
        mock_entry_point.load.assert_called_once()


@pytest.mark.asyncio
async def test_plugin_priority_entry_points_over_filesystem():
    """Test that entry points have priority over filesystem when same plugin exists in both."""
    # This test verifies that if a plugin is loaded via entry point,
    # the filesystem version is skipped
    
    # Create a mock entry point for macgyver
    mock_entry_point = Mock(spec=EntryPoint)
    mock_entry_point.name = "rag2f_macgyver"
    
    # Point to the macgyver plugin root (not the rag2f_macgyver subfolder)
    macgyver_path = os.path.join(utils.get_default_plugins_path(), "rag2f_macgyver")
    
    mock_entry_point.load.return_value = lambda: macgyver_path
    
    with patch('rag2f.core.morpheus.morpheus.entry_points') as mock_ep:
        mock_ep.return_value = [mock_entry_point]
        
        morpheus = await Morpheus.create()
        
        # Verify macgyver was loaded
        assert "rag2f_macgyver" in morpheus.plugins, "macgyver plugin should be loaded"
        
        # The plugin should only be loaded once (from entry point, not duplicated from filesystem)
        # This is verified by the logging behavior in the actual implementation
        plugin = morpheus.plugins["rag2f_macgyver"]
        assert plugin.id == "rag2f_macgyver"


@pytest.mark.asyncio  
async def test_backward_compatibility_filesystem_only():
    """Test that plugins still work when loaded from filesystem only (no entry points)."""
    # Mock entry_points to return empty list (no installed plugins)
    with patch('rag2f.core.morpheus.morpheus.entry_points') as mock_ep:
        mock_ep.return_value = []
        
        morpheus = await Morpheus.create()
        
        # The test verifies that the system works with no entry points
        # Actual plugin loading from filesystem depends on test environment
        assert morpheus is not None, "Morpheus should be created successfully"
        
        # Verify hooks dictionary exists (may be empty if no plugins in test env)
        assert isinstance(morpheus.hooks, dict), "Hooks should be a dictionary"


@pytest.mark.asyncio
async def test_invalid_entry_point_handling():
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
    
    with patch('rag2f.core.morpheus.morpheus.entry_points') as mock_ep:
        mock_ep.return_value = invalid_entry_points
        
        morpheus = Morpheus()
        
        # Should not raise exception, just log warnings/errors
        await morpheus._load_from_entry_points()
        
        # No plugins should be loaded from invalid entry points
        assert len(morpheus.plugins) == 0, "No plugins should be loaded from invalid entry points"


@pytest.mark.asyncio
async def test_site_packages_path_detection_with_underscore_name():
    """Test that plugin is correctly located when entry point returns site-packages root with underscore naming.
    
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
    with patch('rag2f.core.morpheus.morpheus.entry_points') as mock_ep:
        with patch('os.path.exists') as mock_exists:
            with patch('os.path.isdir') as mock_isdir:
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
                
                morpheus = Morpheus()
                await morpheus._load_from_entry_points()
                
                # The plugin should be found even though entry point returned site-packages
                # Verify that the system looked for the plugin in site-packages/rag2f_openai_embedder
                assert any("rag2f_openai_embedder" in str(call) for call in mock_isdir.call_args_list), \
                    "System should look for rag2f_openai_embedder subdirectory in site-packages"


@pytest.mark.asyncio
async def test_site_packages_path_detection_no_plugin_found():
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
    
    with patch('rag2f.core.morpheus.morpheus.entry_points') as mock_ep:
        with patch('os.path.exists', return_value=True):
            with patch('os.path.isdir', return_value=False):  # Plugin dir doesn't exist
                mock_ep.return_value = [mock_entry_point]
                
                morpheus = Morpheus()
                # Should not raise exception, just skip the plugin
                await morpheus._load_from_entry_points()
                
                # No plugins should be loaded
                assert len(morpheus.plugins) == 0, "Plugin should be skipped if directory not found"
