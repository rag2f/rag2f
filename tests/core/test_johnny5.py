"""Unit tests for the Johnny5 foreground text handler."""

import uuid
from types import SimpleNamespace
from unittest.mock import Mock

import rag2f.core.johnny5.johnny5 as johnny5_module
from rag2f.core.johnny5.johnny5 import Johnny5


def test_handle_text_basic():
    """Empty or whitespace-only input should fail."""
    j = Johnny5()
    assert j.handle_text_foreground("").status == "failure"
    assert j.handle_text_foreground(" \n ").status == "failure"
    assert j.handle_text_foreground("\n\n").status == "failure"
    assert j.handle_text_foreground(None).status == "failure"


def _build_johnny5(side_effect):
    """Build a Johnny5 wired with a mocked Morpheus hook executor."""
    morpheus = Mock()
    morpheus.execute_hook = Mock(side_effect=side_effect)
    rag2f = SimpleNamespace(morpheus=morpheus)
    return Johnny5(rag2f_instance=rag2f), morpheus, rag2f


def test_handle_text_uses_hook_id():
    """The hook-provided id should be used throughout the flow."""
    expected_id = "from-hook"

    def side_effect(hook_name, *args, **kwargs):
        if hook_name == "get_id_input_text":
            return expected_id
        if hook_name == "check_duplicated_input_text":
            assert args[1] == expected_id
            return False
        if hook_name == "handle_text_foreground":
            assert args[1] == expected_id
            return True

    johnny5, morpheus, rag2f = _build_johnny5(side_effect)
    response = johnny5.handle_text_foreground("hello world")

    assert response.status == "success"
    morpheus.execute_hook.assert_any_call("get_id_input_text", None, "hello world", rag2f=rag2f)


def test_handle_text_generates_uuid_when_hook_returns_none(monkeypatch):
    """If id hook returns None, Johnny5 should generate a UUID."""
    fake_uuid = uuid.UUID("00000000-0000-0000-0000-00000000abcd")
    monkeypatch.setattr(johnny5_module.uuid, "uuid4", lambda: fake_uuid)

    def side_effect(hook_name, *args, **kwargs):
        if hook_name == "get_id_input_text":
            return None
        if hook_name == "check_duplicated_input_text":
            assert args[1] == fake_uuid.hex
            return False
        if hook_name == "handle_text_foreground":
            assert args[1] == fake_uuid.hex
            return True

    johnny5, morpheus, _ = _build_johnny5(side_effect)
    response = johnny5.handle_text_foreground("ciao")

    assert response.status == "success"
    assert morpheus.execute_hook.call_args_list[0].args[0] == "get_id_input_text"


def test_handle_text_respects_duplicated_hook():
    """If duplicated hook returns True, handler should stop early."""
    expected_id = "dup-id"

    def side_effect(hook_name, *args, **kwargs):
        if hook_name == "get_id_input_text":
            return expected_id
        if hook_name == "check_duplicated_input_text":
            assert args[1] == expected_id
            return True
        raise AssertionError("handle_text_foreground hook should not be called when duplicated")

    johnny5, morpheus, _ = _build_johnny5(side_effect)
    response = johnny5.handle_text_foreground("hello again")

    assert response.status == "duplicated"
    assert morpheus.execute_hook.call_count == 2


def test_handle_text_handles_done_flag_from_hook():
    """If the handler hook returns False, the overall status should be failure."""
    expected_id = "done-id"

    def side_effect(hook_name, *args, **kwargs):
        if hook_name == "get_id_input_text":
            return expected_id
        if hook_name == "check_duplicated_input_text":
            assert args[1] == expected_id
            return False
        if hook_name == "handle_text_foreground":
            assert args[1] == expected_id
            return False

    johnny5, morpheus, _ = _build_johnny5(side_effect)
    response = johnny5.handle_text_foreground("not handled")

    assert response.status == "failure"
    assert response.message == "Input text not handled"
    assert morpheus.execute_hook.call_args_list[-1].args[0] == "handle_text_foreground"
