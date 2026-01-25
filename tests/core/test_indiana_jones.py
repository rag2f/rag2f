"""Contract and regression tests for IndianaJones.

Tests verify the Result pattern: expected states (empty query) return
Result with status="error", success returns Result with status="success".
System errors (backend crash) raise RetrievalError.
"""

from unittest.mock import MagicMock

import pytest

from rag2f.core.dto.indiana_jones_dto import RetrieveResult, SearchResult
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


def test_search_returns_success_result():
    """Search returns SearchResult with status success."""
    mock_rag2f = MagicMock()
    mock_rag2f.morpheus.execute_hook.return_value = SearchResult.success(query="test query")

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


def test_search_raises_on_system_error():
    """Search raises RetrievalError when backend crashes."""
    mock_rag2f = MagicMock()
    mock_rag2f.morpheus.execute_hook.side_effect = RuntimeError("Backend crashed")

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
