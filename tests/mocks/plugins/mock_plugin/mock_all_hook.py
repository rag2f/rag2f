"""Mock hooks used by the test plugin."""

from rag2f.core.morpheus.decorators import hook


@hook
def get_id_input_text(current_id, text, rag2f):
    """Return a deterministic id derived from the input text when none is provided."""
    if current_id:
        return current_id
    base_text = (text or "").strip() or "input"
    return f"{base_text}-mock-id"


@hook
def check_duplicated_input_text(duplicated, item_id, text, rag2f):
    """Mark inputs containing the word 'duplicate' as duplicates."""
    normalized = (text or "").lower()
    if "duplicate" in normalized:
        return True
    return duplicated


@hook
def handle_text_foreground(done, item_id, text, rag2f):
    """Signal that any text containing 'handled' has already been processed."""
    if done:
        return done
    normalized = (text or "").lower()
    return "handled" in normalized


@hook
def indiana_jones_retrieve(result, query, k, return_mode, for_synthesize, rag2f):
    """Enrich retrieve result with mock data."""
    from rag2f.core.dto.indiana_jones_dto import RetrievedItem

    # Add mock items to demonstrate plugin enrichment
    if not result.items:
        result.items = [
            RetrievedItem(
                id=f"mock-item-{i}",
                text=f"Mock retrieved content {i} for query: {query}",
                metadata={"source": "mock", "query": query, "for_synthesize": for_synthesize},
                score=1.0 - (i * 0.1),
            )
            for i in range(min(k, 3))
        ]
    return result


@hook
def indiana_jones_synthesize(result, retrieve_result, return_mode, kwargs, rag2f):
    """Synthesize response from retrieved items."""
    # Add mock response if empty
    if not result.response:
        result.response = f"Mock response for: {result.query}"
        result.used_source_ids = [item.id for item in (retrieve_result.items or [])[:2]]

    return result
