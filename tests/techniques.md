# RAG2F Testing Techniques Guide

This guide documents the testing techniques used in the RAG2F project and provides recommendations for writing effective tests.

## Table of Contents

1. [Mock Plugin Testing](#mock-plugin-testing)
2. [Unit Testing with Mocks](#unit-testing-with-mocks)
3. [Fixture-Based Testing](#fixture-based-testing)
4. [Integration Testing](#integration-testing)
5. [Parameterized Testing](#parameterized-testing)
6. [Testing Async Code](#testing-async-code)
7. [Testing Hooks and Plugins](#testing-hooks-and-plugins)
8. [Configuration Testing](#configuration-testing)
9. [Recommended Patterns](#recommended-patterns)

---

## 1. Mock Plugin Testing

**Location**: [`tests/mocks/plugins/`](tests/mocks/plugins/)

### Technique: Full Mock Plugins

Create complete plugin directories with real structure for integration testing.

**Example**: [`tests/mocks/plugins/mock_plugin/`](tests/mocks/plugins/mock_plugin/)

```python
# Structure
mock_plugin/
├── __init__.py
├── mock_hook.py           # Hooks with @hook decorator
├── mock_all_hook.py       # Bootstrap hooks
├── mock_plugin_overrides.py  # Plugin-specific overrides
├── plugin_context.py      # Context management
└── nested_folder/
    └── mock_another_hook.py
```

**Benefits**:
- Tests real plugin loading mechanism
- Validates hook discovery and execution
- Tests plugin isolation and context

**When to use**:
- Testing plugin manager ([`Morpheus`](src/rag2f/core/morpheus/morpheus.py))
- Integration tests requiring real plugin behavior
- Testing hook priority and execution order

**Example Test**: [`tests/morpheus/test_hooks.py`](tests/morpheus/test_hooks.py)

---

## 2. Unit Testing with Mocks

**Location**: [`tests/core/test_johnny5.py`](tests/core/test_johnny5.py)

### Technique: Lightweight Mock Objects

Use `unittest.mock.Mock` to create minimal test doubles without full plugin structure.

```python
from unittest.mock import Mock
from types import SimpleNamespace

def _build_johnny5(side_effect):
    """Helper to create Johnny5 with mocked dependencies."""
    morpheus = Mock()
    morpheus.execute_hook = Mock(side_effect=side_effect)
    rag2f = SimpleNamespace(morpheus=morpheus)
    return Johnny5(rag2f_instance=rag2f), morpheus, rag2f
```

**Benefits**:
- Fast execution
- Complete control over behavior
- Easy to test edge cases
- No dependency on real implementations

**When to use**:
- Testing business logic in isolation
- Testing error handling paths
- Verifying method call arguments
- Testing deterministic behavior

**Example**:
```python
def test_handle_text_uses_hook_id():
    expected_id = "from-hook"
    
    def side_effect(hook_name, *args, **kwargs):
        if hook_name == "get_id_input_text":
            return expected_id
        if hook_name == "check_duplicated_input_text":
            assert args[1] == expected_id
            return False
        if hook_name == "handle_text_foreground":
            assert args[1] == expected_id
            return True
    
    johnny5, morpheus, rag2f = _build_johnny5(side_effect)
    response = johnny5.handle_text_foreground("hello world")
    
    assert response.status == "success"
    morpheus.execute_hook.assert_any_call(
        "get_id_input_text", None, "hello world", rag2f=rag2f
    )
```

---

## 3. Fixture-Based Testing

**Location**: [`tests/conftest.py`](tests/conftest.py)

### Technique: Pytest Fixtures with Async Support

Use `pytest_asyncio` fixtures for shared test setup.

```python
@pytest_asyncio.fixture(scope="session")
async def rag2f():
    """Session-scoped RAG2F instance for integration tests."""
    instance = await RAG2F.create(plugins_folder=f"{PATH_MOCK}/plugins/")
    return instance

@pytest_asyncio.fixture(scope="session")
async def morpheus(rag2f):
    """Reuse rag2f's morpheus instance."""
    return rag2f.morpheus
```

**Benefits**:
- Share expensive setup across tests
- Automatic cleanup
- Clear dependency hierarchy
- Reduce test execution time

**Scopes**:
- `function`: New instance per test (default)
- `class`: Shared within test class
- `module`: Shared within module
- `session`: Shared across all tests

**When to use**:
- Integration tests requiring real instances
- Tests that need consistent state
- Tests with expensive setup (database, network)

**Example Test**: [`tests/core/test_all_hooks.py`](tests/core/test_all_hooks.py)

---

## 4. Integration Testing

**Location**: [`tests/core/test_plugin_entry_points.py`](tests/core/test_plugin_entry_points.py)

### Technique: Testing Real Integration with Mocked External Dependencies

Test full flow while mocking only external boundaries.

```python
@pytest.mark.asyncio
async def test_entry_point_loading_mechanism():
    """Test that entry point loading mechanism works correctly."""
    # Create a mock entry point
    mock_entry_point = Mock(spec=EntryPoint)
    mock_entry_point.name = "test_plugin"
    
    test_plugin_path = os.path.join(utils.get_default_plugins_path(), "macgyver")
    mock_entry_point.load.return_value = lambda: test_plugin_path
    
    with patch('rag2f.core.morpheus.morpheus.entry_points') as mock_ep:
        mock_ep.return_value = [mock_entry_point]
        
        morpheus = Morpheus()
        await morpheus._load_from_entry_points()
        
        mock_entry_point.load.assert_called_once()
```

**Benefits**:
- Tests real code paths
- Validates integration points
- Catches interface mismatches
- Realistic failure scenarios

**When to use**:
- Testing component interactions
- Validating plugin discovery mechanisms
- Testing priority and conflict resolution

---

## 5. Parameterized Testing

**Location**: [`tests/core/test_spock.py`](tests/core/test_spock.py)

### Technique: Test Multiple Scenarios with Same Logic

Use `@pytest.mark.parametrize` to run same test with different inputs.

```python
@pytest.mark.parametrize("section, config_data, getter, key, expected, default_key, default_value", [
    ("rag2f", 
     {"rag2f": {"key1": "value1", "key2": "value2"}}, 
     "get_rag2f_config", 
     "key1", 
     "value1", 
     "nonexistent", 
     "default_value"),
    ("plugins", 
     {"plugins": {"my_plugin": {"setting1": "value1", "setting2": 42}}}, 
     "get_plugin_config", 
     "my_plugin", 
     {"setting1": "value1", "setting2": 42}, 
     "nonexistent_plugin", 
     "default"),
])
def test_get_config(self, section, config_data, getter, key, expected, default_key, default_value):
    # Test implementation runs for each parameter set
    ...
```

**Benefits**:
- DRY principle - avoid test duplication
- Better coverage with less code
- Clear test case documentation
- Easy to add new scenarios

**When to use**:
- Testing same logic with different inputs
- Boundary condition testing
- Type validation testing
- Configuration priority testing

---

## 6. Testing Async Code

**Location**: Multiple test files

### Technique: Use `pytest-asyncio` and `@pytest.mark.asyncio`

```python
@pytest.mark.asyncio
async def test_multiple_rag2f_instances_isolated_config():
    """Test that multiple RAG2F instances have isolated Spock configurations."""
    config1_path = create_temp_config({"rag2f": {"embedder_default": "embedder1"}})
    config2_path = create_temp_config({"rag2f": {"embedder_default": "embedder2"}})
    
    try:
        rag2f1 = await RAG2F.create(config_path=config1_path)
        rag2f2 = await RAG2F.create(config_path=config2_path)
        
        assert rag2f1.spock.get_rag2f_config("embedder_default") == "embedder1"
        assert rag2f2.spock.get_rag2f_config("embedder_default") == "embedder2"
        assert rag2f1.spock is not rag2f2.spock
    finally:
        cleanup_temp_files(config1_path, config2_path)
```

**Benefits**:
- Tests async initialization correctly
- Validates concurrent behavior
- Tests async context managers

**Common Patterns**:
- Use `@pytest_asyncio.fixture` for async fixtures
- Use `@pytest.mark.asyncio` for async tests
- Always clean up resources in `finally` blocks

---

## 7. Testing Hooks and Plugins

**Location**: [`tests/morpheus/test_hooks.py`](tests/morpheus/test_hooks.py), [`tests/morpheus/test_plugin.py`](tests/morpheus/test_plugin.py)

### Technique: Test Hook Discovery and Execution

```python
def test_hook_priority_execution(morpheus):
    """Test that hooks execute in priority order."""
    message = "Priorities:"
    out = morpheus.execute_hook("morpheus_test_hook_message", message, rag2f=None)
    assert out == "Priorities: priority 4 priority 3 priority 2"
```

**Benefits**:
- Validates hook registration
- Tests priority ordering
- Verifies plugin isolation

**Test Checklist for Plugins**:
- ✅ Hook discovery from nested folders
- ✅ Priority ordering
- ✅ Plugin-specific context access
- ✅ Override mechanisms
- ✅ Dependency installation
- ✅ Settings model validation

---

## 8. Configuration Testing

**Location**: [`tests/core/test_spock.py`](tests/core/test_spock.py), [`tests/core/test_spock_integration.py`](tests/core/test_spock_integration.py)

### Technique: Test Configuration Priority and Sources

```python
def test_env_overrides_json(self):
    """Test that environment variables override JSON values."""
    # Create JSON config
    config_data = {"rag2f": {"embedder_default": "json_embedder"}}
    config_path = create_temp_config(config_data)
    
    # Set environment variable
    os.environ["RAG2F__RAG2F__EMBEDDER_DEFAULT"] = "env_embedder"
    
    try:
        spock = Spock(config_path=config_path)
        spock.load()
        
        # Environment should win
        assert spock.get_rag2f_config("embedder_default") == "env_embedder"
    finally:
        os.unlink(config_path)
        del os.environ["RAG2F__RAG2F__EMBEDDER_DEFAULT"]
```

**Test Coverage**:
- ✅ JSON loading
- ✅ Environment variable parsing
- ✅ Priority (ENV > JSON > defaults)
- ✅ Type inference (int, float, bool, JSON)
- ✅ Nested configuration
- ✅ Multiple instances isolation

---

## 9. Recommended Patterns

### Pattern 1: Test Helpers

Create reusable test helpers in separate modules:

```python
# tests/utils.py
PATH_MOCK = "tests/mocks"

def get_mock_plugin_info():
    return {
        "id": "mock_plugin",
        "hooks": 3
    }
```

### Pattern 2: Temporary File Management

Always clean up temporary files:

```python
import tempfile

def test_with_temp_file():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(config_data, f)
        config_path = f.name
    
    try:
        # Test logic here
        ...
    finally:
        os.unlink(config_path)
```

### Pattern 3: Context-Based Testing

Use context managers for setup/teardown:

```python
@contextmanager
def temp_env_var(key, value):
    """Temporarily set an environment variable."""
    old_value = os.environ.get(key)
    os.environ[key] = value
    try:
        yield
    finally:
        if old_value is None:
            del os.environ[key]
        else:
            os.environ[key] = old_value

def test_with_env():
    with temp_env_var("RAG2F__TEST", "value"):
        # Test with environment variable
        ...
```

### Pattern 4: Mock Side Effects for Complex Behavior

```python
def test_complex_hook_chain():
    call_count = {"get_id": 0, "check_dup": 0}
    
    def side_effect(hook_name, *args, **kwargs):
        if hook_name == "get_id_input_text":
            call_count["get_id"] += 1
            return "test-id"
        elif hook_name == "check_duplicated_input_text":
            call_count["check_dup"] += 1
            return False
        # ... more hooks
    
    johnny5, morpheus, _ = _build_johnny5(side_effect)
    johnny5.handle_text_foreground("test")
    
    assert call_count["get_id"] == 1
    assert call_count["check_dup"] == 1
```

### Pattern 5: Testing Error Conditions

```python
def test_plugin_loading_with_invalid_path():
    """Test that invalid plugin paths raise clear errors."""
    with pytest.raises(Exception) as exc_info:
        Plugin(rag2f,"/non/existent/folder")
    
    assert "Cannot create" in str(exc_info.value)
```

### Pattern 6: Monkeypatch for External Dependencies

```python
def test_uuid_generation(monkeypatch):
    """Test UUID generation with predictable value."""
    fake_uuid = uuid.UUID("00000000-0000-0000-0000-00000000abcd")
    monkeypatch.setattr(johnny5_module.uuid, "uuid4", lambda: fake_uuid)
    
    # Now uuid.uuid4() will return fake_uuid
    ...
```

---

## Testing Best Practices for RAG2F

### 1. Test Isolation

✅ **DO**:
- Use fixtures for shared setup
- Clean up resources in `finally` blocks
- Reset global state between tests
- Use `scope="function"` for mutable state

❌ **DON'T**:
- Share mutable state between tests
- Rely on test execution order
- Leave temporary files
- Modify global configuration without cleanup

### 2. Mock External Dependencies

✅ **DO**:
- Mock HTTP clients (OpenAI SDK)
- Mock file system when testing logic
- Mock environment variables
- Use `respx` for HTTP mocking ([`plugins/rag2f_azure_openai_embedder/test/test_embedder_unit.py`](plugins/rag2f_azure_openai_embedder/test/test_embedder_unit.py))

❌ **DON'T**:
- Make real API calls in unit tests
- Depend on external services
- Test third-party library behavior

### 3. Test Coverage

**Focus on YOUR code**:
- Configuration validation
- Hook execution order
- Plugin discovery logic
- Error handling
- Edge cases (empty strings, None, etc.)

**Don't test**:
- Third-party libraries (OpenAI SDK)
- Standard library behavior
- Framework internals

### 4. Test Naming

Use descriptive names that explain:
- What is being tested
- What conditions
- What is expected

```python
# ✅ Good
def test_hook_priority_execution_with_multiple_plugins():
    ...

def test_env_var_overrides_json_config():
    ...

# ❌ Bad
def test_hook():
    ...

def test_config():
    ...
```

### 5. Async Testing

✅ **DO**:
```python
@pytest.mark.asyncio
async def test_async_operation():
    result = await async_function()
    assert result == expected
```

❌ **DON'T**:
```python
def test_async_operation():
    # This won't work properly
    asyncio.run(async_function())
```

---

## Quick Reference: When to Use Which Technique

| Scenario | Technique | Example |
|----------|-----------|---------|
| Testing plugin loading | Mock plugins in `tests/mocks/` | [`tests/morpheus/test_plugin.py`](tests/morpheus/test_plugin.py) |
| Testing business logic | `unittest.mock.Mock` | [`tests/core/test_johnny5.py`](tests/core/test_johnny5.py) |
| Testing config priority | Temp files + env vars | [`tests/core/test_spock.py`](tests/core/test_spock.py) |
| Testing hook execution | Mock plugin with `@hook` | [`tests/morpheus/test_hooks.py`](tests/morpheus/test_hooks.py) |
| Testing multiple inputs | `@pytest.mark.parametrize` | [`tests/core/test_spock.py`](tests/core/test_spock.py) |
| Testing async code | `@pytest.mark.asyncio` | [`tests/core/test_spock_integration.py`](tests/core/test_spock_integration.py) |
| Testing HTTP integration | `respx.mock` | [`plugins/rag2f_openai_embedder/test/test_embedder_unit.py`](plugins/rag2f_openai_embedder/test/test_embedder_unit.py) |
| Testing error handling | `pytest.raises` | [`tests/morpheus/test_plugin.py`](tests/morpheus/test_plugin.py) |

---

## Additional Testing Tools

### Coverage Analysis

```bash
# Run tests with coverage
pytest --cov=src/rag2f --cov-report=html

# View coverage report
open htmlcov/index.html
```

### Test Filtering

```bash
# Run specific test file
pytest tests/core/test_spock.py

# Run specific test
pytest tests/core/test_spock.py::TestSpockBasics::test_initialization

# Run tests matching pattern
pytest -k "test_env"

# Run only async tests
pytest -m asyncio
```

### Debug Mode

```bash
# Stop on first failure
pytest -x

# Show local variables on failure
pytest -l

# Enable print statements
pytest -s

# Verbose output
pytest -v
```

---

## Plugin-Specific Testing Example

For a new plugin, create these tests:

```python
# tests/my_plugin/test_my_plugin.py

import pytest
from plugins.my_plugin.src.my_component import MyComponent

class TestMyPluginUnit:
    """Test plugin logic in isolation."""
    
    def test_configuration_validation(self):
        """Test that plugin validates required config."""
        with pytest.raises(ValueError, match="api_key required"):
            MyComponent({})
    
    def test_core_functionality(self):
        """Test main plugin behavior."""
        config = {"api_key": "test-key"}
        component = MyComponent(config)
        result = component.process("input")
        assert result == "expected"

class TestMyPluginIntegration:
    """Test plugin integration with RAG2F."""
    
    @pytest.mark.asyncio
    async def test_hook_registration(self, rag2f):
        """Test that plugin hooks are registered."""
        assert "my_plugin_hook" in rag2f.morpheus.hooks
    
    @pytest.mark.asyncio
    async def test_bootstrap(self, rag2f):
        """Test plugin bootstrap process."""
        # Verify plugin initialized correctly
        assert rag2f.morpheus.plugin_exists("my_plugin")
```

---

## Conclusion

The RAG2F testing strategy combines:
1. **Mock plugins** for realistic integration testing
2. **Unit mocks** for fast, isolated logic testing
3. **Fixtures** for shared setup and dependency injection
4. **Parameterization** for comprehensive coverage
5. **Async support** for testing async operations

Follow these patterns to write maintainable, reliable tests that clearly document expected behavior.