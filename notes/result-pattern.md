# RAG2F Result Pattern

## Overview

RAG2F uses a **typed Result pattern** for handling operation outcomes. This approach separates:

- **Expected states** (empty input, duplicates, not handled, cache miss) → Returned as `Result` with `status="error"` or partial success
- **System errors** (backend crash, timeout, bugs) → Raised as exceptions

## Architecture

```
                    ┌─────────────────────┐
                    │     BaseResult      │  ← Common base (status, detail, is_ok())
                    │  - status           │
                    │  - detail           │    (StatusDetail)
                    │  - is_ok()          │
                    │  - is_error()       │
                    │  - success()        │
                    │  - fail()           │
                    └─────────┬───────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐    ┌────────────────┐    ┌───────────────┐
│ InsertResult  │    │ RetrieveResult │    │ SearchResult  │
│ + track_id    │    │ + query        │    │ + query       │
└───────────────┘    │ + items        │    │ + response    │
                     └────────────────┘    │ + used_source │
                                           │ + items       │
                                           └───────────────┘
```

## Naming Convention

**Convention: `execute_*` prefix + `[Result Pattern]` tag in docstring + strong TypeHint**

```python
def execute_text_foreground(self, text: str) -> InsertResult:
    """Process text input.
    
    [Result Pattern] Check result.is_ok() before using fields.
    
    Returns:
        InsertResult with status="success" or status="error"
    """
```

### Benefits
- ✅ `execute_*` prefix signals operation returns Result (not exception)
- ✅ TypeHint communicates exact return type (`-> InsertResult`)
- ✅ `[Result Pattern]` tag in docstring signals pattern to AI/developers
- ✅ Legacy aliases (`handle_*`, `retrieve`, `search`) for backward compatibility

### Recognition for AI Agents

When an AI agent sees `execute_*` method + `[Result Pattern]` in docstring:
1. Return type is a subclass of `BaseResult`
2. Must check `result.is_ok()` before accessing fields
3. Status details are in `result.detail` (if error/partial)
4. Expected failures don't raise exceptions

### Legacy Compatibility

Old method names remain as aliases:

```python
# Preferred (new code)
result = johnny5.execute_text_foreground(text)

# Legacy (backward compatibility)
result = johnny5.handle_text_foreground(text)  # Deprecated but works
```

## Why This Pattern?

### Performance

Raising exceptions has significant overhead in Python:
- Stack trace creation (~100-1000x slower)
- Object allocation for traceback
- Handler lookup through entire call chain

```python
# Benchmark: 100,000 iterations
# Raise exception: ~0.5-1.0 seconds
# Return result:   ~0.01-0.02 seconds
```

For **frequent expected states** (empty input, duplicates, cache miss), exceptions waste resources.

### Type Safety

Each Result subclass has **typed fields** visible to IDE/AI:

```python
# IDE/AI sees exact fields
result = johnny5.handle_text_foreground(text)
result.track_id  # ✓ IDE autocomplete works

result = indiana.retrieve(query)
result.items     # ✓ list[RetrievedItem]
result.query     # ✓ str
```

### Consistency

Same pattern across all modules:

```python
# Johnny5
result = johnny5.execute_text_foreground(text)
if result.is_ok():
    use(result.track_id)

# IndianaJones - SAME PATTERN
result = indiana.execute_retrieve(query)
if result.is_ok():
    use(result.items)

# XFiles - SAME PATTERN (for operations like cache get)
result = xfiles.execute_get(key)
if result.is_ok():
    use(result.value)
```

## StatusDetail + StatusCode: Flexible State Communication

`StatusDetail` is used for **both errors AND partial successes**:

```python
class StatusDetail(BaseModel):
    code: str       # Use StatusCode constants
    message: str    # Human-readable description
    context: dict   # Diagnostic data

class StatusCode:
    """Centralized status code constants."""
    EMPTY = "empty"
    DUPLICATE = "duplicate"
    NOT_FOUND = "not_found"
    # ... see result_dto.py for all codes
```

### Example: Using StatusCode

```python
from rag2f.core.dto.result_dto import StatusCode

# In implementation
if not text.strip():
    return InsertResult.fail(StatusCode.EMPTY, "Input text is empty")

# In caller
result = johnny5.execute_text_foreground(text)
if result.detail and result.detail.code == StatusCode.EMPTY:
    # Handle empty input
```

### Example: Partial Success

Hook decides status based on operation outcome:

```python
# Plugin hook handles duplicate - partial success
def handle_duplicate(track_id, text):
    existing_doc = db.get(track_id)
    return InsertResult.success(
        track_id=track_id,
        detail=StatusDetail(
            code=StatusCode.DUPLICATE_MERGED,
            message="Input merged with existing document",
            context={"merged_with": existing_doc.id}
        )
    )
```

## Error Handling Matrix

| Situation | Handling | Who Handles | Pattern |
|-----------|----------|-------------|---------|
| Empty input | `Result.fail(StatusCode.EMPTY, ...)` | Caller checks `is_error()` | Johnny5, IndianaJones |
| Duplicate | Hook decides status | Caller checks `detail` | Johnny5 |
| Not handled | `Result.fail(StatusCode.NOT_HANDLED, ...)` | Caller decides action | Johnny5 |
| Cache miss / Not found | `Result.fail(StatusCode.NOT_FOUND, ...)` | Caller handles gracefully | XFiles |
| Partial success | `Result.success(..., detail=StatusDetail(...))` | Caller checks `detail` | Any module |
| Backend crash | `raise RetrievalError` | Middleware/error handler | IndianaJones |
| Timeout | `raise RetrievalError` | Middleware/error handler | IndianaJones |
| Bug/invariant | `raise RuntimeError` | Should never happen | Any module |

## XFiles: When to Use Result vs Exception

### Use Result Pattern For:
- **Cache miss / Not found** (frequent, expected)
- **Query operations** that may return no results
- **Validation failures** (invalid query spec)

```python
# XFiles with Result pattern
result = xfiles.get_cached("user:123")
if result.is_error() and result.detail.code == "not_found":
    # Normal cache miss - reload from DB
    value = db.load("user:123")
```

### Use Exceptions For:
- **CRUD invariant violations** (AlreadyExists on insert with existing ID)
- **Backend failures** (database connection lost)
- **Protocol violations** (invalid repository type)

```python
# XFiles with exceptions (for invariants)
try:
    xfiles.insert({"id": "123", "data": "..."})  # ID already exists
except AlreadyExists:
    # This is an invariant violation - caller error
```

### Rationale

| Operation | Frequency | Pattern | Why |
|-----------|-----------|---------|-----|
| Cache miss | High (50%+) | Result | Too expensive to exception |
| Query no results | Medium | Result | Expected outcome |
| Insert duplicate ID | Low | Exception | Caller error / bug |
| Get by ID not found | Depends | Exception* | Unexpected in most cases |

\* `get()` raises `NotFound` because it's a direct lookup - caller expects it to exist. Use `get_optional()` for Result pattern.

## Usage Patterns

### Pattern 1: Simple Check (90% of cases)

```python
result = johnny5.handle_text_foreground(text)

if result.is_ok():
    print(f"Track ID: {result.track_id}")
else:
    print(f"Error [{result.detail.code}]: {result.detail.message}")
```

### Pattern 2: Handle by Status Code

```python
result = johnny5.handle_text_foreground(text)

if result.is_error():
    match result.detail.code:
        case "empty":
            ask_user_for_input()
        case "duplicate":
            use_existing(result.detail.context.get("id"))
        case "not_handled":
            configure_plugins()
```

### Pattern 3: Check Partial Success

```python
result = johnny5.handle_text_foreground(text)

if result.is_ok():
    if result.detail and result.detail.code == "duplicate_merged":
        # Partial success - inform user
        print(f"Merged with existing: {result.detail.context['merged_with']}")
    else:
        # Full success
        print(f"Inserted: {result.track_id}")
```

### Pattern 4: Service with System Error Handling

```python
def search_service(query: str) -> dict:
    """API service that must always return a response."""
    
    # try ONLY for system errors
    try:
        result = indiana.retrieve(query, k=5)
    except RetrievalError as e:
        # System error (backend down, timeout)
        logger.error("System error: %s", e)
        return {"status": "error", "code": "system_error"}
    
    # Expected states are in result.detail
    if result.is_error():
        return {"status": "error", "code": result.detail.code}
    
    return {"status": "success", "items": [i.to_dict() for i in result.items]}
```

### Pattern 5: Pipeline Composition

```python
async def search_with_fallback(query: str) -> RetrieveResult:
    """Try primary backend, fallback on failure."""
    
    try:
        result = indiana_primary.retrieve(query)
        if result.is_ok() and result.items:
            return result
    except RetrievalError:
        logger.warning("Primary backend failed")
    
    # Fallback
    return indiana_fallback.retrieve(query)
```

## AI Agent Template

For AI agents implementing RAG2F operations, use this template:

```python
# === RAG2F RESULT HANDLING TEMPLATE ===

# 1. Call method (no try needed for expected states)
result = module.method(args)

# 2. Check status
if result.is_ok():
    # Access typed fields:
    # - InsertResult: result.track_id
    # - RetrieveResult: result.items, result.query
    # - SearchResult: result.response, result.used_source_ids
    
    # Check for partial success
    if result.detail:
        # result.detail.code: "partial", "duplicate_merged", etc.
        # result.detail.message: description
        # result.detail.context: diagnostic data
        pass
else:
    # Handle error by code:
    # result.detail.code: "empty", "duplicate", "not_found", "not_handled"
    # result.detail.message: human-readable description
    # result.detail.context: diagnostic data dict
    logger.warning("[%s] %s", result.detail.code, result.detail.message)

# 3. ONLY if catching system errors (rare, <10% of cases):
try:
    result = indiana.retrieve(query)
except RetrievalError as e:
    handle_system_error(e)
```

## Status Codes Reference

### Johnny5 (InsertResult)

| Code | Status | Description | Context Fields |
|------|--------|-------------|----------------|
| `empty` | error | Input is empty or whitespace | - |
| `duplicate` | error/success* | Input already processed | `id`, `text` |
| `duplicate_merged` | success | Merged with existing | `merged_with` |
| `not_handled` | error | No hook handled input | - |
| `partial` | success | Partially processed | hook-specific |

\* Hook decides if duplicate is error or success

### IndianaJones (RetrieveResult, SearchResult)

| Code | Status | Description | Context Fields |
|------|--------|-------------|----------------|
| `empty_query` | error | Query is empty or whitespace | - |
| `no_results` | success | Query valid but no items found | `query` |
| `degraded` | success | Partial results (some backends failed) | `failed_backends` |

### XFiles (when using Result pattern)

| Code | Status | Description | Context Fields |
|------|--------|-------------|----------------|
| `not_found` | error | Cache miss / item not found | `key` |
| `invalid_spec` | error | Query spec validation failed | `field`, `reason` |
| `partial_results` | success | Some results, pagination | `total`, `has_more` |

### Common Exceptions (System Errors)

| Exception | When Raised | Module |
|-----------|-------------|--------|
| `RetrievalError` | Backend crash, timeout, plugin failure | IndianaJones |
| `PluginError` | Hook execution failed | Johnny5, Morpheus |
| `NotFound` | Direct get() by ID not found | XFiles |
| `AlreadyExists` | Insert with existing ID | XFiles |
| `ValidationError` | Query spec validation (alternative to Result) | XFiles |
| `RuntimeError` | Invariant violation (bug) | Any module |

## Migration Guide

### Before (Exception-based)

```python
try:
    result = johnny5.handle_text_foreground(text)
    use(result.track_id)
except InsertError as e:
    if "empty" in str(e):
        handle_empty()
    elif "duplicate" in str(e):
        handle_duplicate()
```

### After (Result-based)

```python
result = johnny5.handle_text_foreground(text)

if result.is_ok():
    use(result.track_id)
else:
    match result.detail.code:
        case "empty":
            handle_empty()
        case "duplicate":
            handle_duplicate()
```

## Benefits Summary

| Aspect | Benefit |
|--------|---------|
| **Performance** | No stack trace for expected states (100-1000x faster) |
| **Type Safety** | IDE/AI sees exact fields via TypeHint |
| **Consistency** | Same pattern across Johnny5, IndianaJones, XFiles |
| **Composability** | Easy pipeline building without try/except nesting |
| **Flexibility** | StatusDetail supports both errors and partial success |
| **Debugging** | Structured context dict for diagnostics |
| **AI-Friendly** | Predictable pattern via `[Result Pattern]` tag |
| **Hook-Driven** | Plugins can decide success/error/partial status |
