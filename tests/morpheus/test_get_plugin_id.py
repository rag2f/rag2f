"""Tests for Morpheus.get_plugin_id() robustness and error handling.

Note: With Solution 1 (Stack Walking), these tests focus on validating
the behavior of walking the stack to find the first @hook decorated function.
"""

from unittest.mock import Mock, patch

import pytest

from rag2f.core.morpheus.decorators.hook import PillHook
from rag2f.core.morpheus.morpheus import Morpheus
from rag2f.core.morpheus.plugin import Plugin


@pytest.fixture
def morpheus_instance(fresh_morpheus):
    """Use the shared fixtures but keep state isolated per test."""
    original_plugins = dict(fresh_morpheus.plugins)
    original_hooks = dict(fresh_morpheus.hooks)
    try:
        yield fresh_morpheus
    finally:
        fresh_morpheus.plugins = original_plugins
        fresh_morpheus.hooks = original_hooks


def test_extract_plugin_id_from_hook_with_valid_hook(morpheus_instance: Morpheus):
    """Test extracting plugin_id from a real hook in a real module."""

    # Create a real PillHook with plugin_id set
    def dummy_func():
        pass

    hook = PillHook(name="test_hook", func=dummy_func, priority=1)
    hook.plugin_id = "test_plugin"

    # Create a mock module and test getattr on it
    class FakeModule:
        __name__ = "fake_module"

    module = FakeModule()
    module.test_hook = hook

    # Test the extraction
    plugin_id = morpheus_instance._extract_plugin_id_from_hook(module, "test_hook")

    assert plugin_id == "test_plugin"


def test_extract_plugin_id_from_hook_not_found(morpheus_instance: Morpheus):
    """Test extracting plugin_id when hook name doesn't exist."""

    class FakeModule:
        __name__ = "fake_module"

    module = FakeModule()
    plugin_id = morpheus_instance._extract_plugin_id_from_hook(module, "nonexistent_hook")

    assert plugin_id is None


def test_extract_plugin_id_from_hook_not_a_pill_hook(morpheus_instance: Morpheus):
    """Test extracting plugin_id when attribute is not a PillHook."""

    class FakeModule:
        __name__ = "fake_module"

        def regular_func(self):
            return None

    module = FakeModule()
    plugin_id = morpheus_instance._extract_plugin_id_from_hook(module, "regular_func")

    assert plugin_id is None


def test_extract_plugin_id_from_hook_with_invalid_plugin_id(morpheus_instance: Morpheus):
    """Test extracting plugin_id when hook.plugin_id is None or invalid."""

    def dummy_func():
        pass

    hook = PillHook(name="test_hook", func=dummy_func, priority=1)
    hook.plugin_id = None  # Not set

    class FakeModule:
        __name__ = "fake_module"

    module = FakeModule()
    module.test_hook = hook

    plugin_id = morpheus_instance._extract_plugin_id_from_hook(module, "test_hook")

    assert plugin_id is None


def test_extract_plugin_id_from_hook_with_non_string_plugin_id(morpheus_instance: Morpheus):
    """Test extracting plugin_id when hook.plugin_id is not a string."""

    def dummy_func():
        pass

    hook = PillHook(name="test_hook", func=dummy_func, priority=1)
    hook.plugin_id = 123  # Not a string

    class FakeModule:
        __name__ = "fake_module"

    module = FakeModule()
    module.test_hook = hook

    plugin_id = morpheus_instance._extract_plugin_id_from_hook(module, "test_hook")

    assert plugin_id is None


def test_get_plugin_id_with_no_hook_in_stack(morpheus_instance: Morpheus):
    """Test get_plugin_id raises RuntimeError when no @hook found in stack."""
    # Mock inspect.stack to return empty/minimal stack
    with (
        patch("inspect.stack", return_value=[]),
        pytest.raises(
            RuntimeError,
            match="No @hook decorated function found in the call stack",
        ),
    ):
        morpheus_instance.self_plugin_id()


def test_get_plugin_id_with_unknown_plugin_in_stack(morpheus_instance: Morpheus):
    """Test get_plugin_id raises RuntimeError when plugin_id from stack not in loaded plugins."""
    # Mock stack with a frame pointing to a hook with unknown plugin_id
    mock_frame_info = Mock()
    mock_frame_info.frame = Mock()
    mock_frame_info.function = "some_hook"
    mock_module = Mock()
    mock_module.__name__ = "test_module"

    with (
        patch("inspect.stack", return_value=[Mock(), mock_frame_info]),
        patch("inspect.getmodule", return_value=mock_module),
        patch.object(
            morpheus_instance,
            "_extract_plugin_id_from_hook",
            return_value="unknown_plugin",
        ),
        pytest.raises(RuntimeError, match="Plugin 'unknown_plugin' not found"),
    ):
        morpheus_instance.get_plugin("unknown_plugin")


def test_get_plugin_id_success_finds_hook_in_stack(morpheus_instance: Morpheus):
    """Test get_plugin_id successfully finds @hook in stack and returns plugin."""
    # Add a mock plugin
    mock_plugin = Mock(spec=Plugin)
    morpheus_instance.plugins["test_plugin"] = mock_plugin

    # Mock stack with a frame that has a hook
    mock_frame_info = Mock()
    mock_frame_info.frame = Mock()
    mock_frame_info.function = "my_hook"
    mock_module = Mock()
    mock_module.__name__ = "test_module"

    with (
        patch("inspect.stack", return_value=[Mock(), mock_frame_info]),
        patch("inspect.getmodule", return_value=mock_module),
        patch.object(
            morpheus_instance,
            "_extract_plugin_id_from_hook",
            return_value="test_plugin",
        ),
    ):
        result = morpheus_instance.get_plugin("test_plugin")

    assert result is mock_plugin


def test_get_plugin_id_walks_stack_until_hook_found(morpheus_instance: Morpheus):
    """Test get_plugin_id walks stack through helper functions until @hook is found.

    This tests Solution 1's key feature: supporting arbitrary call chains
    (hook -> helper1 -> helper2 -> get_plugin_id).
    """
    # Add a mock plugin
    mock_plugin = Mock(spec=Plugin)
    morpheus_instance.plugins["test_plugin"] = mock_plugin

    # Mock stack: [frame0, helper_func, another_helper, my_hook]
    # First two should return None from _extract_plugin_id_from_hook, third should return plugin_id
    frames = [Mock() for _ in range(4)]
    frames[0].frame = Mock()
    frames[0].function = "get_plugin_id"  # This frame is for get_plugin_id itself

    frames[1].frame = Mock()
    frames[1].function = "helper_func"

    frames[2].frame = Mock()
    frames[2].function = "another_helper"

    frames[3].frame = Mock()
    frames[3].function = "my_hook"

    mock_module = Mock()
    mock_module.__name__ = "test_module"

    # Track calls to _extract_plugin_id_from_hook
    extract_calls = []

    def extract_side_effect(module, func_name):
        extract_calls.append(func_name)
        if func_name == "my_hook":
            return "test_plugin"
        return None

    with (
        patch("inspect.stack", return_value=frames),
        patch("inspect.getmodule", return_value=mock_module),
        patch.object(
            morpheus_instance,
            "_extract_plugin_id_from_hook",
            side_effect=extract_side_effect,
        ),
    ):
        result = morpheus_instance.get_plugin(morpheus_instance.self_plugin_id())

    assert result is mock_plugin
    # Should have checked helper_func, another_helper, and my_hook (found at third)
    assert "helper_func" in extract_calls
    assert "another_helper" in extract_calls
    assert "my_hook" in extract_calls
