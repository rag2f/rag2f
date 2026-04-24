"""Hook integration tests for Morpheus and mock plugins."""

from rag2f.core.dto import PromptContext, ResolvedPrompt
from rag2f.core.dto.indiana_jones_dto import RetrieveResult, ReturnMode, SearchResult


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


def test_indiana_jones_retrieve_hook_enriches_result(rag2f):
    """indiana_jones_retrieve hook must enrich RetrieveResult with mock items."""
    result = RetrieveResult(query="test query")

    output = rag2f.morpheus.execute_hook(
        "indiana_jones_retrieve",
        result,
        "test query",
        10,
        ReturnMode.WITH_ITEMS,
        False,  # for_synthesize
        rag2f=rag2f,
    )

    assert isinstance(output, RetrieveResult)
    assert output.query == "test query"
    assert len(output.items) > 0
    assert all(item.id.startswith("mock-item-") for item in output.items)


def test_indiana_jones_synthesize_hook_creates_response(rag2f):
    """indiana_jones_synthesize hook must create SearchResult response from retrieve."""
    from rag2f.core.dto.indiana_jones_dto import RetrievedItem

    retrieve_result = RetrieveResult(
        query="test query",
        items=[
            RetrievedItem(id="item-1", text="content 1", score=0.9),
            RetrievedItem(id="item-2", text="content 2", score=0.8),
        ],
    )
    search_result = SearchResult(query="test query", items=retrieve_result.items)

    output = rag2f.morpheus.execute_hook(
        "indiana_jones_synthesize",
        search_result,
        retrieve_result,
        ReturnMode.WITH_ITEMS,
        {},
        rag2f=rag2f,
    )

    assert isinstance(output, SearchResult)
    assert output.query == "test query"
    assert output.response.startswith("Mock response")
    assert len(output.used_source_ids) > 0


def test_agent_collect_prompt_fragments_hook_keeps_passthrough_context(rag2f):
    """agent_collect_prompt_fragments should support a no-op passthrough context."""
    context = PromptContext(agent_key="demo.agent", plugin_id="demo_plugin", purpose="noop")

    output = rag2f.morpheus.execute_hook(
        "agent_collect_prompt_fragments",
        [],
        context,
        rag2f=rag2f,
    )

    assert isinstance(output, list)
    assert output == []


def test_agent_finalize_prompt_hook_keeps_passthrough_prompt(rag2f):
    """agent_finalize_prompt should keep an already-final prompt stable when no rule applies."""
    context = PromptContext(agent_key="demo.agent", plugin_id="demo_plugin", purpose="noop")
    prompt = ResolvedPrompt(text="steady prompt", context=context)

    output = rag2f.morpheus.execute_hook(
        "agent_finalize_prompt",
        prompt,
        context,
        rag2f=rag2f,
    )

    assert isinstance(output, ResolvedPrompt)
    assert output.text == "steady prompt"
