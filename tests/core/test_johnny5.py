"""Contract and regression tests for Johnny5 foreground text handler.

Tests verify the Result pattern: expected states return InsertResult with
status="error", success returns InsertResult with status="success".
"""

from unittest.mock import MagicMock

from rag2f.core.dto.result_dto import StatusCode
from rag2f.core.johnny5.johnny5 import Johnny5


def test_handle_text_empty_returns_error_result():
    """Empty or whitespace-only input returns InsertResult with error."""
    j = Johnny5()

    result = j.execute_handle_text_foreground("")
    assert result.is_error()
    assert result.detail.code == StatusCode.EMPTY

    result = j.execute_handle_text_foreground("   ")
    assert result.is_error()
    assert result.detail.code == StatusCode.EMPTY

    result = j.execute_handle_text_foreground(None)
    assert result.is_error()
    assert result.detail.code == StatusCode.EMPTY


def test_handle_text_returns_success_result():
    """Successful insert returns InsertResult with track_id."""
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
    result = johnny5.execute_handle_text_foreground("test input")

    assert result.is_ok()
    assert result.status == "success"
    assert result.track_id == "test-id"


def test_handle_text_duplicate_returns_error_result():
    """Duplicate text returns InsertResult with error."""
    mock_rag2f = MagicMock()

    def mock_hook(hook_name, *args, **kw):
        if hook_name == "get_id_input_text":
            return "dup-id"
        if hook_name == "check_duplicated_input_text":
            return True
        raise AssertionError("Should not reach handle_text_foreground hook")

    mock_rag2f.morpheus.execute_hook.side_effect = mock_hook

    johnny5 = Johnny5(rag2f_instance=mock_rag2f)
    result = johnny5.execute_handle_text_foreground("duplicate text")

    assert result.is_error()
    assert result.detail.code == StatusCode.DUPLICATE
    assert result.detail.context.get("id") == "dup-id"


def test_handle_text_not_handled_returns_error_result():
    """Text not handled by hooks returns InsertResult with error."""
    mock_rag2f = MagicMock()

    def mock_hook(hook_name, *args, **kw):
        if hook_name == "get_id_input_text":
            return "test-id"
        if hook_name == "check_duplicated_input_text":
            return False
        if hook_name == "handle_text_foreground":
            return False
        return None

    mock_rag2f.morpheus.execute_hook.side_effect = mock_hook

    johnny5 = Johnny5(rag2f_instance=mock_rag2f)
    result = johnny5.execute_handle_text_foreground("unhandled text")

    assert result.is_error()
    assert result.detail.code == StatusCode.NOT_HANDLED


def test_handle_text_without_rag2f():
    """Without rag2f, text returns appropriate error states."""
    johnny5 = Johnny5()

    # Empty text returns error
    result = johnny5.execute_handle_text_foreground("")
    assert result.is_error()
    assert result.detail.code == "empty"

    # Non-empty text without hooks returns not_handled
    result = johnny5.execute_handle_text_foreground("test")
    assert result.is_error()
    assert result.detail.code == "not_handled"
