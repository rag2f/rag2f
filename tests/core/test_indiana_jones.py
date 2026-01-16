"""Contract and regression tests for IndianaJones.

Focuses on:
- Correct exceptions for invalid input
- Hook invocation with correct parameters
- Return type contracts
"""

import pytest

from rag2f.core.dto.indiana_jones_dto import RetrieveResult, ReturnMode, SearchResult
from rag2f.core.indiana_jones.exceptions import RetrievalError
from rag2f.core.indiana_jones.indiana_jones import IndianaJones


def test_retrieve_raises_on_empty_query():
    """Retrieve must raise RetrievalError when query is empty."""
    indiana = IndianaJones()

    with pytest.raises(RetrievalError, match="query is empty"):
        indiana.retrieve("")

    with pytest.raises(RetrievalError, match="query is empty"):
        indiana.retrieve(None)


def test_search_raises_on_empty_query():
    """Search must raise RetrievalError when query is empty."""
    indiana = IndianaJones()

    with pytest.raises(RetrievalError, match="query is empty"):
        indiana.search("")

    with pytest.raises(RetrievalError, match="query is empty"):
        indiana.search(None)


def test_retrieve_returns_retrieve_result():
    """Retrieve must return a RetrieveResult instance."""
    from unittest.mock import MagicMock

    mock_rag2f = MagicMock()
    mock_rag2f.morpheus.execute_hook.return_value = RetrieveResult(query="test query")

    indiana = IndianaJones(rag2f_instance=mock_rag2f)
    result = indiana.retrieve("test query", k=5)

    assert isinstance(result, RetrieveResult)
    assert result.query == "test query"


def test_search_returns_search_result():
    """Search must return a SearchResult instance."""
    from unittest.mock import MagicMock

    mock_rag2f = MagicMock()
    mock_rag2f.morpheus.execute_hook.return_value = SearchResult(query="test query")

    indiana = IndianaJones(rag2f_instance=mock_rag2f)
    result = indiana.search("test query", k=5)

    assert isinstance(result, SearchResult)
    assert result.query == "test query"


def test_search_respects_return_mode():
    """Search result structure must match return_mode."""
    from unittest.mock import MagicMock

    mock_rag2f = MagicMock()

    def mock_search(*args, **kw):
        # Extract return_mode from positional args
        return_mode = args[4] if len(args) > 4 else ReturnMode.MINIMAL
        result = SearchResult(query="test")
        # Simulate plugin behavior based on return_mode
        if return_mode == ReturnMode.WITH_ITEMS:
            result.items = []
        return result

    mock_rag2f.morpheus.execute_hook.side_effect = mock_search

    indiana = IndianaJones(rag2f_instance=mock_rag2f)

    # MINIMAL: items should be None
    result_min = indiana.search("test", return_mode=ReturnMode.MINIMAL)
    assert result_min.items is None

    # WITH_ITEMS: items should be present
    result_items = indiana.search("test", return_mode=ReturnMode.WITH_ITEMS)
    assert result_items.items is not None


def test_retrieve_invokes_hook():
    """Retrieve must invoke indiana_jones_retrieve hook."""
    from unittest.mock import MagicMock

    mock_rag2f = MagicMock()
    mock_rag2f.morpheus.execute_hook.return_value = RetrieveResult(query="test query")

    indiana = IndianaJones(rag2f_instance=mock_rag2f)
    indiana.retrieve("test query", k=5)

    mock_rag2f.morpheus.execute_hook.assert_called_once()
    call_args = mock_rag2f.morpheus.execute_hook.call_args
    assert call_args[0][0] == "indiana_jones_retrieve"
    assert isinstance(call_args[0][1], RetrieveResult)
    assert call_args[0][2] == "test query"
    assert call_args[0][3] == 5
    assert call_args[1]["rag2f"] is mock_rag2f


def test_search_invokes_hook():
    """Search must invoke indiana_jones_search hook."""
    from unittest.mock import MagicMock

    mock_rag2f = MagicMock()
    mock_rag2f.morpheus.execute_hook.return_value = SearchResult(query="test query")

    indiana = IndianaJones(rag2f_instance=mock_rag2f)
    indiana.search("test query", k=5, return_mode=ReturnMode.WITH_ITEMS)

    mock_rag2f.morpheus.execute_hook.assert_called_once()
    call_args = mock_rag2f.morpheus.execute_hook.call_args
    assert call_args[0][0] == "indiana_jones_search"
    assert isinstance(call_args[0][1], SearchResult)
    assert call_args[0][2] == "test query"
    assert call_args[0][3] == 5
    assert call_args[0][4] == ReturnMode.WITH_ITEMS
    assert call_args[1]["rag2f"] is mock_rag2f


def test_retrieve_without_rag2f():
    """Retrieve must work without rag2f instance (no hooks)."""
    indiana = IndianaJones()
    result = indiana.retrieve("test query")

    assert isinstance(result, RetrieveResult)
    assert result.query == "test query"
    assert result.items == []


def test_search_without_rag2f():
    """Search must work without rag2f instance (no hooks)."""
    indiana = IndianaJones()
    result = indiana.search("test query")

    assert isinstance(result, SearchResult)
    assert result.query == "test query"
    assert result.response == ""
