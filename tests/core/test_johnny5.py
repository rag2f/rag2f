import pytest

from rag2f.core.johnny5.johnny5 import Johnny5


def test_handle_text_basic():
    j = Johnny5()
    assert j.handle_text_foreground("  Hello ").status == "success"
    assert j.handle_text_foreground("").status == "failure"
    assert j.handle_text_foreground(" \n ").status == "failure"
    assert j.handle_text_foreground("\n\n").status == "failure"
    assert j.handle_text_foreground(None).status == "failure"

