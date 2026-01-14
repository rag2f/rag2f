"""Hook integration tests for Morpheus and mock plugins."""


def test_get_id_input_text_hook_transforms_input(rag2f):
    """get_id_input_text must derive a deterministic id from the provided text."""
    generated_id = rag2f.morpheus.execute_hook(
        "get_id_input_text", None, "alpha-beta", rag2f=rag2f
    )

    assert generated_id == "alpha-beta-mock-id"


def test_check_duplicated_input_text_hook_flags_duplicates(rag2f):
    """check_duplicated_input_text should only flag inputs containing 'duplicate'."""
    duplicate = rag2f.morpheus.execute_hook(
        "check_duplicated_input_text",
        False,
        "alpha-beta-mock-id",
        "Please duplicate this",
        rag2f=rag2f,
    )
    untouched = rag2f.morpheus.execute_hook(
        "check_duplicated_input_text", False, "alpha-beta-mock-id", "unique payload", rag2f=rag2f
    )

    assert duplicate is True
    assert untouched is False


def test_handle_text_foreground_hook_completes_flow(rag2f):
    """handle_text_foreground should return True only when the text contains 'handled'."""
    handled = rag2f.morpheus.execute_hook(
        "handle_text_foreground",
        False,
        "alpha-beta-mock-id",
        "This text is handled automatically",
        rag2f=rag2f,
    )
    pending = rag2f.morpheus.execute_hook(
        "handle_text_foreground",
        False,
        "alpha-beta-mock-id",
        "This text still needs work",
        rag2f=rag2f,
    )

    assert handled is True
    assert pending is False
