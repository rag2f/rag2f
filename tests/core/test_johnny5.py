"""Contract and regression tests for Johnny5 foreground text handler."""

import pytest

from rag2f.core.johnny5.exceptions import DuplicateInputError, InsertError
from rag2f.core.johnny5.johnny5 import Johnny5


def test_handle_text_empty_raises_insert_error():
    """Empty or whitespace-only input should raise InsertError."""
    j = Johnny5()

    with pytest.raises(InsertError, match="Input text is empty"):
        j.handle_text_foreground("")

    with pytest.raises(InsertError, match="Input text is empty"):
        j.handle_text_foreground("   ")

    with pytest.raises(InsertError, match="Input text is empty"):
        j.handle_text_foreground(None)


def test_handle_text_returns_insert_result():
    """Successful insert must return InsertResult with track_id."""
    from unittest.mock import MagicMock

    mock_rag2f = MagicMock()

    def mock_hook(hook_name, *args, **kw):
        if hook_name == "get_id_input_text":
            return "test-id"
        if hook_name == "check_duplicated_input_text":
            return False
        if hook_name == "handle_text_foreground":
            return True
        return None

    mock_rag2f.morpheus.execute_hook.side_effect = mock_hook

    johnny5 = Johnny5(rag2f_instance=mock_rag2f)
    result = johnny5.handle_text_foreground("test input")

    assert result.status == "success"
    assert result.track_id == "test-id"


def test_handle_text_duplicate_raises_duplicate_error():
    """Duplicate text should raise DuplicateInputError."""
    from unittest.mock import MagicMock

    mock_rag2f = MagicMock()

    def mock_hook(hook_name, *args, **kw):
        if hook_name == "get_id_input_text":
            return "dup-id"
        if hook_name == "check_duplicated_input_text":
            return True  # Mark as duplicate
        raise AssertionError("Should not reach handle_text_foreground hook")

    mock_rag2f.morpheus.execute_hook.side_effect = mock_hook

    johnny5 = Johnny5(rag2f_instance=mock_rag2f)

    with pytest.raises(DuplicateInputError, match="Input text is duplicated"):
        johnny5.handle_text_foreground("duplicate text")


def test_handle_text_not_handled_raises_insert_error():
    """Text not handled by hooks should raise InsertError."""
    from unittest.mock import MagicMock

    mock_rag2f = MagicMock()

    def mock_hook(hook_name, *args, **kw):
        if hook_name == "get_id_input_text":
            return "test-id"
        if hook_name == "check_duplicated_input_text":
            return False
        if hook_name == "handle_text_foreground":
            return False  # Not handled
        return None

    mock_rag2f.morpheus.execute_hook.side_effect = mock_hook

    johnny5 = Johnny5(rag2f_instance=mock_rag2f)

    with pytest.raises(InsertError, match="Input text not handled"):
        johnny5.handle_text_foreground("unhandled text")


def test_handle_text_invokes_hooks_in_order():
    """Hooks must be invoked in correct order: id → duplicate → handle."""
    from unittest.mock import MagicMock

    mock_rag2f = MagicMock()
    call_order = []

    def mock_hook(hook_name, *args, **kw):
        call_order.append(hook_name)
        if hook_name == "get_id_input_text":
            return "order-test-id"
        if hook_name == "check_duplicated_input_text":
            return False
        if hook_name == "handle_text_foreground":
            return True
        return None

    mock_rag2f.morpheus.execute_hook.side_effect = mock_hook

    johnny5 = Johnny5(rag2f_instance=mock_rag2f)
    johnny5.handle_text_foreground("test")

    assert call_order == [
        "get_id_input_text",
        "check_duplicated_input_text",
        "handle_text_foreground",
    ]


def test_handle_text_without_rag2f():
    """Without rag2f, text should raise InsertError when hooks not available."""
    johnny5 = Johnny5()  # No rag2f instance

    # Empty text still raises
    with pytest.raises(InsertError, match="Input text is empty"):
        johnny5.handle_text_foreground("")

    # Non-empty text without hooks should raise
    with pytest.raises(InsertError, match="Input text not handled"):
        johnny5.handle_text_foreground("test")
