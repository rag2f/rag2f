# IndianaJones — Retrieval Manager

> "Fortune and glory, kid. Fortune and glory." — Indiana Jones

Handles RAG retrieval and search operations with extensible backends.

## Key Methods

```python
# Retrieve relevant chunks
result = indiana_jones.execute_retrieve(query: str, k: int = 10) -> RetrieveResult

# Retrieve + synthesize answer
result = indiana_jones.execute_search(
    query: str, 
    k: int = 10,
    return_mode: ReturnMode = ReturnMode.MINIMAL
) -> SearchResult
```

## Result Types

```python
class RetrievedItem(BaseModel):
    id: str                     # Chunk/document identifier
    text: str                   # Passage text
    metadata: Mapping[str, Any] # Loader/user metadata
    score: float | None         # Relevance score
    extra: dict[str, Any]       # Plugin extension point

class RetrieveResult(BaseResult):
    query: str
    items: list[RetrievedItem]
    extra: dict[str, Any]

class SearchResult(BaseResult):
    query: str
    response: str               # Synthesized answer
    used_source_ids: list[str]  # Sources used in response
    items: list[RetrievedItem] | None  # Only with ReturnMode.WITH_ITEMS
    extra: dict[str, Any]
```

## Return Modes

```python
from rag2f.core.dto.indiana_jones_dto import ReturnMode

# Minimal (default): response + used_source_ids only
result = indiana.execute_search(query, return_mode=ReturnMode.MINIMAL)

# With items: includes retrieved chunks
result = indiana.execute_search(query, return_mode=ReturnMode.WITH_ITEMS)
```

## Status Codes

| Code | Meaning |
|------|---------|
| `StatusCode.EMPTY` | Query is empty or whitespace-only |
| `StatusCode.NO_RESULTS` | Query returned no items |
| `StatusCode.DEGRADED` | Response partially degraded |

## Hooks

### Retrieve Hook

```python
@hook("indiana_jones_retrieve", priority=10)
def my_retriever(result: RetrieveResult, query: str, k: int, *, rag2f):
    # Perform retrieval
    items = my_vector_db.search(query, k)
    
    return RetrieveResult.success(
        query=query,
        items=[RetrievedItem(id=i.id, text=i.text, score=i.score) for i in items]
    )
```

### Search Hook

```python
@hook("indiana_jones_search", priority=10)
def my_search(result: SearchResult, query: str, k: int, return_mode: ReturnMode, kwargs, *, rag2f):
    # 1. Retrieve
    items = my_vector_db.search(query, k)
    
    # 2. Synthesize
    context = "\n".join(i.text for i in items)
    response = my_llm.generate(f"Answer based on:\n{context}\n\nQuestion: {query}")
    
    return SearchResult.success(
        query=query,
        response=response,
        used_source_ids=[i.id for i in items],
        items=items if return_mode == ReturnMode.WITH_ITEMS else None
    )
```

## Usage Examples

### Basic Retrieval

```python
result = rag2f.indiana_jones.execute_retrieve("How does authentication work?", k=5)

if result.is_ok():
    for item in result.items:
        print(f"[{item.score:.2f}] {item.text[:100]}...")
else:
    print(f"Error: {result.detail.message}")
```

### Search with Answer

```python
result = rag2f.indiana_jones.execute_search(
    "What are the security best practices?",
    k=10,
    return_mode=ReturnMode.WITH_ITEMS
)

if result.is_ok():
    print(f"Answer: {result.response}")
    print(f"Sources: {result.used_source_ids}")
    
    if result.items:
        print("\nRetrieved chunks:")
        for item in result.items:
            print(f"  - {item.id}: {item.text[:50]}...")
```

### Error Handling

```python
result = rag2f.indiana_jones.execute_retrieve("")

if result.is_error():
    match result.detail.code:
        case "empty":
            print("Please provide a query")
        case "no_results":
            print("No relevant documents found")
```

## Exception: RetrievalError

System errors (not expected states) raise `RetrievalError`:

```python
from rag2f.core.indiana_jones.exceptions import RetrievalError

try:
    result = rag2f.indiana_jones.execute_retrieve(query)
except RetrievalError as e:
    # Backend crash, timeout, etc.
    print(f"System error: {e}")
    print(f"Context: {e.context}")  # {"query": ..., "k": ...}
```

---

## Optional: Testing IndianaJones

See [testing.md](./testing.md) for complete testing guide.

```python
from unittest.mock import MagicMock
from rag2f.core.indiana_jones import IndianaJones
from rag2f.core.dto.indiana_jones_dto import RetrieveResult, RetrievedItem

def test_indiana_retrieve():
    mock_rag2f = MagicMock()
    
    def mock_hook(hook_name, result, *args, **kw):
        if hook_name == "indiana_jones_retrieve":
            return RetrieveResult.success(
                query=args[0],
                items=[
                    RetrievedItem(id="doc1", text="Hello world", score=0.95)
                ]
            )
        return result
    
    mock_rag2f.morpheus.execute_hook.side_effect = mock_hook
    
    indiana = IndianaJones(rag2f_instance=mock_rag2f)
    result = indiana.execute_retrieve("test query", k=5)
    
    assert result.is_ok()
    assert len(result.items) == 1
    assert result.items[0].id == "doc1"

def test_indiana_empty_query():
    indiana = IndianaJones()
    result = indiana.execute_retrieve("")
    
    assert result.is_error()
    assert result.detail.code == "empty"
```
