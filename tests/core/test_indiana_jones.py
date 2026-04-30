"""Contract and regression tests for IndianaJones.

Tests verify the Result pattern: expected states (empty query) return
Result with status="error", success returns Result with status="success".
System errors (backend crash) raise RetrievalError.
"""

from unittest.mock import MagicMock

import pytest

from rag2f.core.dto.indiana_jones_dto import (
    MultiStepSearchResult,
    RetrievedItem,
    RetrieveResult,
    ReturnMode,
    SearchResult,
    SubQuestionResult,
)
from rag2f.core.dto.result_dto import StatusCode
from rag2f.core.indiana_jones.exceptions import RetrievalError
from rag2f.core.indiana_jones.indiana_jones import IndianaJones


def test_retrieve_returns_error_on_empty_query():
    """Retrieve returns RetrieveResult with error when query is empty."""
    indiana = IndianaJones()

    result = indiana.execute_retrieve("")
    assert result.is_error()
    assert result.detail.code == StatusCode.EMPTY

    result = indiana.execute_retrieve(None)
    assert result.is_error()
    assert result.detail.code == StatusCode.EMPTY


def test_search_returns_error_on_empty_query():
    """Search returns SearchResult with error when query is empty."""
    indiana = IndianaJones()

    result = indiana.execute_search("")
    assert result.is_error()
    assert result.detail.code == StatusCode.EMPTY

    result = indiana.execute_search(None)
    assert result.is_error()
    assert result.detail.code == StatusCode.EMPTY


def test_retrieve_returns_success_result():
    """Retrieve returns RetrieveResult with status success."""
    mock_rag2f = MagicMock()
    mock_rag2f.morpheus.execute_hook.return_value = RetrieveResult.success(query="test query")

    indiana = IndianaJones(rag2f_instance=mock_rag2f)
    result = indiana.execute_retrieve("test query", k=5)

    assert result.is_ok()
    assert isinstance(result, RetrieveResult)
    assert result.query == "test query"


def test_retrieve_receives_return_mode_and_for_synthesize():
    """Retrieve hook receives return_mode and for_synthesize arguments."""
    mock_rag2f = MagicMock()
    mock_rag2f.morpheus.execute_hook.return_value = RetrieveResult.success(query="test")

    indiana = IndianaJones(rag2f_instance=mock_rag2f)
    indiana.execute_retrieve("test", k=5, return_mode=ReturnMode.MINIMAL, for_synthesize=True)

    call_args = mock_rag2f.morpheus.execute_hook.call_args
    assert call_args[0][0] == "indiana_jones_retrieve"
    assert call_args[0][4] == ReturnMode.MINIMAL  # return_mode
    assert call_args[0][5] is True  # for_synthesize


def test_search_calls_retrieve_then_synthesize():
    """Search calls execute_retrieve internally then indiana_jones_synthesize hook."""
    mock_rag2f = MagicMock()

    # Track hook calls
    calls = []

    def track_hooks(hook_name, *args, **kwargs):
        calls.append(hook_name)
        if hook_name == "indiana_jones_retrieve":
            return RetrieveResult.success(
                query="test",
                items=[RetrievedItem(id="item-1", text="content", score=0.9)],
            )
        if hook_name == "indiana_jones_synthesize":
            result = args[0]  # SearchResult passed as first arg
            result.response = "synthesized response"
            result.used_source_ids = ["item-1"]
            return result
        return args[0]

    mock_rag2f.morpheus.execute_hook.side_effect = track_hooks

    indiana = IndianaJones(rag2f_instance=mock_rag2f)
    result = indiana.execute_search("test", k=5, return_mode=ReturnMode.WITH_ITEMS)

    assert calls == ["indiana_jones_retrieve", "indiana_jones_synthesize"]
    assert result.is_ok()
    assert result.response == "synthesized response"
    assert result.items is not None  # WITH_ITEMS keeps items


def test_search_drops_items_when_minimal():
    """Search drops items from result when return_mode is MINIMAL."""
    mock_rag2f = MagicMock()

    def mock_hook(hook_name, *args, **kwargs):
        if hook_name == "indiana_jones_retrieve":
            return RetrieveResult.success(
                query="test",
                items=[RetrievedItem(id="item-1", text="content", score=0.9)],
            )
        if hook_name == "indiana_jones_synthesize":
            result = args[0]
            result.response = "answer"
            result.used_source_ids = ["item-1"]
            return result
        return args[0]

    mock_rag2f.morpheus.execute_hook.side_effect = mock_hook

    indiana = IndianaJones(rag2f_instance=mock_rag2f)
    result = indiana.execute_search("test", return_mode=ReturnMode.MINIMAL)

    assert result.is_ok()
    assert result.items is None  # MINIMAL drops items


def test_search_returns_success_result():
    """Search returns SearchResult with status success."""
    mock_rag2f = MagicMock()

    def mock_hook(hook_name, *args, **kwargs):
        if hook_name == "indiana_jones_retrieve":
            return RetrieveResult.success(query="test query")
        if hook_name == "indiana_jones_synthesize":
            return args[0]  # Return the SearchResult as-is
        return args[0]

    mock_rag2f.morpheus.execute_hook.side_effect = mock_hook

    indiana = IndianaJones(rag2f_instance=mock_rag2f)
    result = indiana.execute_search("test query", k=5)

    assert result.is_ok()
    assert isinstance(result, SearchResult)
    assert result.query == "test query"


def test_retrieve_raises_on_system_error():
    """Retrieve raises RetrievalError when backend crashes."""
    mock_rag2f = MagicMock()
    mock_rag2f.morpheus.execute_hook.side_effect = RuntimeError("Backend crashed")

    indiana = IndianaJones(rag2f_instance=mock_rag2f)

    with pytest.raises(RetrievalError, match="Retrieval failed"):
        indiana.execute_retrieve("test query")


def test_search_raises_on_retrieve_system_error():
    """Search raises RetrievalError when retrieve backend crashes."""
    mock_rag2f = MagicMock()
    mock_rag2f.morpheus.execute_hook.side_effect = RuntimeError("Backend crashed")

    indiana = IndianaJones(rag2f_instance=mock_rag2f)

    with pytest.raises(RetrievalError, match="Retrieval failed"):
        indiana.execute_search("test query")


def test_search_raises_on_synthesize_system_error():
    """Search raises RetrievalError when synthesize hook crashes."""
    mock_rag2f = MagicMock()

    def mock_hook(hook_name, *args, **kwargs):
        if hook_name == "indiana_jones_retrieve":
            return RetrieveResult.success(query="test")
        if hook_name == "indiana_jones_synthesize":
            raise RuntimeError("LLM crashed")
        return args[0]

    mock_rag2f.morpheus.execute_hook.side_effect = mock_hook

    indiana = IndianaJones(rag2f_instance=mock_rag2f)

    with pytest.raises(RetrievalError, match="Search failed"):
        indiana.execute_search("test query")


def test_retrieve_without_rag2f():
    """Retrieve works without rag2f instance (no hooks)."""
    indiana = IndianaJones()
    result = indiana.execute_retrieve("test query")

    assert result.is_ok()
    assert isinstance(result, RetrieveResult)
    assert result.query == "test query"
    assert result.items == []


def test_search_without_rag2f():
    """Search works without rag2f instance (no hooks)."""
    indiana = IndianaJones()
    result = indiana.execute_search("test query")

    assert result.is_ok()
    assert isinstance(result, SearchResult)
    assert result.query == "test query"
    assert result.response == ""


# ---------------------------------------------------------------------------
# Multi-step search tests
# ---------------------------------------------------------------------------


def test_multi_step_search_returns_error_on_empty_query():
    """Multi-step search returns error when query is empty or whitespace."""
    indiana = IndianaJones()

    for bad_query in ("", "   ", None):
        result = indiana.execute_multi_step_search(bad_query)
        assert result.is_error()
        assert result.detail.code == StatusCode.EMPTY


def test_multi_step_search_without_rag2f_falls_back_to_single_sub_question():
    """Without rag2f, multi-step search runs a single retrieve on the original query."""
    indiana = IndianaJones()
    result = indiana.execute_multi_step_search("test query")

    assert result.is_ok()
    assert isinstance(result, MultiStepSearchResult)
    assert result.query == "test query"
    assert len(result.sub_question_results) == 1
    assert result.sub_question_results[0].sub_question == "test query"


def test_multi_step_search_calls_plan_hook():
    """Plan hook receives initial list [query] and the query string."""
    mock_rag2f = MagicMock()

    captured = {}

    def mock_hook(hook_name, *args, **kwargs):
        if hook_name == "indiana_jones_plan_subquestions":
            captured["initial"] = args[0]
            captured["query"] = args[1]
            return ["sub-q1", "sub-q2"]
        if hook_name == "indiana_jones_retrieve":
            return RetrieveResult.success(query=args[1])
        if hook_name == "indiana_jones_multi_step_synthesize":
            return args[0]
        return args[0]

    mock_rag2f.morpheus.execute_hook.side_effect = mock_hook

    indiana = IndianaJones(rag2f_instance=mock_rag2f)
    indiana.execute_multi_step_search("compound query", k=5)

    assert captured["initial"] == ["compound query"]
    assert captured["query"] == "compound query"


def test_multi_step_search_retrieves_for_each_sub_question():
    """Retrieve is called once per sub-question returned by the plan hook."""
    mock_rag2f = MagicMock()
    retrieve_queries: list[str] = []

    def mock_hook(hook_name, *args, **kwargs):
        if hook_name == "indiana_jones_plan_subquestions":
            return ["What is X?", "How does Y work?"]
        if hook_name == "indiana_jones_retrieve":
            retrieve_queries.append(args[1])
            return RetrieveResult.success(query=args[1])
        if hook_name == "indiana_jones_multi_step_synthesize":
            return args[0]
        return args[0]

    mock_rag2f.morpheus.execute_hook.side_effect = mock_hook

    indiana = IndianaJones(rag2f_instance=mock_rag2f)
    result = indiana.execute_multi_step_search("What is X and how does Y work?")

    assert result.is_ok()
    assert retrieve_queries == ["What is X?", "How does Y work?"]
    assert len(result.sub_question_results) == 2


def test_multi_step_search_synthesize_hook_receives_sub_question_results():
    """Synthesize hook receives the list of SubQuestionResult objects."""
    mock_rag2f = MagicMock()
    captured_sqrs: list | None = None

    items = [RetrievedItem(id="doc1", text="evidence", score=0.9)]

    def mock_hook(hook_name, *args, **kwargs):
        nonlocal captured_sqrs
        if hook_name == "indiana_jones_plan_subquestions":
            return ["sub-q1"]
        if hook_name == "indiana_jones_retrieve":
            return RetrieveResult.success(query=args[1], items=items)
        if hook_name == "indiana_jones_multi_step_synthesize":
            captured_sqrs = args[1]  # sub_question_results arg
            result = args[0]
            result.response = "final answer"
            result.used_source_ids = ["doc1"]
            return result
        return args[0]

    mock_rag2f.morpheus.execute_hook.side_effect = mock_hook

    indiana = IndianaJones(rag2f_instance=mock_rag2f)
    result = indiana.execute_multi_step_search("query")

    assert result.is_ok()
    assert result.response == "final answer"
    assert result.used_source_ids == ["doc1"]
    assert captured_sqrs is not None
    assert len(captured_sqrs) == 1
    assert isinstance(captured_sqrs[0], SubQuestionResult)
    assert captured_sqrs[0].sub_question == "sub-q1"


def test_multi_step_search_with_items_collects_all_retrieved_items():
    """WITH_ITEMS mode collects items from all sub-question retrieve results."""
    mock_rag2f = MagicMock()

    def mock_hook(hook_name, *args, **kwargs):
        if hook_name == "indiana_jones_plan_subquestions":
            return ["sub-q1", "sub-q2"]
        if hook_name == "indiana_jones_retrieve":
            q = args[1]
            return RetrieveResult.success(
                query=q,
                items=[RetrievedItem(id=f"{q}-doc", text="text", score=0.8)],
            )
        if hook_name == "indiana_jones_multi_step_synthesize":
            return args[0]
        return args[0]

    mock_rag2f.morpheus.execute_hook.side_effect = mock_hook

    indiana = IndianaJones(rag2f_instance=mock_rag2f)
    result = indiana.execute_multi_step_search("query", return_mode=ReturnMode.WITH_ITEMS)

    assert result.is_ok()
    assert result.items is not None
    assert len(result.items) == 2
    assert {i.id for i in result.items} == {"sub-q1-doc", "sub-q2-doc"}


def test_multi_step_search_minimal_mode_drops_items():
    """MINIMAL mode sets items to None in the result."""
    mock_rag2f = MagicMock()

    def mock_hook(hook_name, *args, **kwargs):
        if hook_name == "indiana_jones_plan_subquestions":
            return ["sub-q1"]
        if hook_name == "indiana_jones_retrieve":
            return RetrieveResult.success(
                query=args[1],
                items=[RetrievedItem(id="doc1", text="text", score=0.9)],
            )
        if hook_name == "indiana_jones_multi_step_synthesize":
            return args[0]
        return args[0]

    mock_rag2f.morpheus.execute_hook.side_effect = mock_hook

    indiana = IndianaJones(rag2f_instance=mock_rag2f)
    result = indiana.execute_multi_step_search("query", return_mode=ReturnMode.MINIMAL)

    assert result.is_ok()
    assert result.items is None


def test_multi_step_search_raises_on_synthesize_crash():
    """Multi-step search raises RetrievalError when synthesize hook crashes."""
    mock_rag2f = MagicMock()

    def mock_hook(hook_name, *args, **kwargs):
        if hook_name == "indiana_jones_plan_subquestions":
            return ["sub-q1"]
        if hook_name == "indiana_jones_retrieve":
            return RetrieveResult.success(query=args[1])
        if hook_name == "indiana_jones_multi_step_synthesize":
            raise RuntimeError("LLM crashed")
        return args[0]

    mock_rag2f.morpheus.execute_hook.side_effect = mock_hook

    indiana = IndianaJones(rag2f_instance=mock_rag2f)

    with pytest.raises(RetrievalError, match="Multi-step search failed"):
        indiana.execute_multi_step_search("query")
