"""Contract and regression tests for IndianaJones.

Tests verify the Result pattern: expected states (empty query) return
Result with status="error", success returns Result with status="success".
System errors (backend crash) raise RetrievalError.
"""

from unittest.mock import MagicMock

import pytest

from rag2f.core.dto.indiana_jones_dto import (
    RetrievedItem,
    RetrieveResult,
    ReturnMode,
    SearchResult,
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
