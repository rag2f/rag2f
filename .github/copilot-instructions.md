# RAG2F — Code Agent Instructions (v2)

**Purpose**  
Normative rules for contributing to RAG2F. This page explains **how** to work on the repo (style, tests, plugins, config).  
The **README** describes **what** RAG2F is.

---

## Quick Facts
- **Python**: minimum 3.12  
- **Layout**: `src/` (package in `src/rag2f/`)  
- **Principle**: minimal and stable core; complexity and variants live in **plugins**.

---

## Architecture
**Core modules**
- Johnny5 → `src/rag2f/core/johnny5/`
- Morpheus → `src/rag2f/core/morpheus/`
- Spock → `src/rag2f/core/spock/`
- OptimusPrime → `src/rag2f/core/optimus_prime/`
- XFiles → `src/rag2f/core/xfiles/`

**Contribution rule**  
If a feature can live as a **plugin**, it **must** be a **plugin** (not in core).

---

## Plugins & Hooks
**`@hook` decorator (priority: higher ⇒ executed earlier)**
```python
from rag2f.core.morpheus.decorators import hook

@hook("rag2f_bootstrap_embedders", priority=10)
def my_hook(embedders_registry, rag2f):
    return embedders_registry

@hook(priority=5)  # uses the function name as the hook id
def my_hook_name(data, rag2f):
    return data
```

**Plugin structure**
```
my_plugin/
├─ __init__.py
├─ plugin.toml  # or pyproject.toml with [tool.rag2f.plugin]
├─ hooks.py     # functions decorated with @hook
└─ requirements.txt  # plugin-specific dependencies
```

**Discovery**
1) **Entry points** (`group="rag2f.plugins"`) — highest precedence  
2) **Filesystem** — local `plugins/` folder

---

## Configuration (Spock)
**Priority**: `ENV > JSON > defaults in code`

**Minimal JSON example**
```json
{
  "rag2f": { "embedder_default": "value" },
  "plugins": {
    "plugin_id": {
      "setting1": "value",
      "nested": { "key": "value" }
    }
  }
}
```

**ENV pattern**
```
RAG2F__<SECTION>__<KEY>__<SUBKEY>
```

**ENV examples**
```bash
# Core
RAG2F__RAG2F__EMBEDDER_DEFAULT=value

# Plugin (secrets/credentials via ENV, not in repo)
RAG2F__PLUGINS__AZURE_OPENAI_EMBEDDER__API_KEY=sk-xxx
```
> For full details see **SPOCK_README.md**.

---

## Style, Security and Ruff (single source of truth: pyproject.toml)
- **Ruff is the only tool** for lint, import sorting and formatting.  
- **Quotes**: double (`"string"`). **Indent**: 4 spaces. **Line length**: 99.  
- **Type hints**: modern Python 3.12+ syntax (`list[str]`, `dict[str, Any]`, `type Alias = ...`).  
- **Docstrings**: Google style; keep docstrings short in tests/helpers.

**Suggested Ruff config extract (may not match `pyproject.toml` exactly because `D` and `W` are enabled when needed)**
```toml
[tool.ruff]
target-version = "py312"
line-length = 99
indent-width = 4
src = ["src"]

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "S", "D", "W"] # don't change for `D` and `W` because are enabled manual when needed 
ignore = ["E501"]  # handled by the formatter

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

### Lint rules to follow
- **E** — pycodestyle errors  
- **F** — pyflakes  
- **I** — isort (import sorting)  
- **UP** — pyupgrade (modernize for Python 3.12)  
- **B** — bugbear (bug-prone patterns)  
- **SIM** — simplify (safe simplifications)  
- **S** — security (bandit-like)  
- **D** — docstrings (pydocstyle)  
- **W** — pycodestyle warnings

**Modern syntax examples**
```python
# ✅ Modern

def get_items() -> list[str]:
    ...

type DocumentId = str | bytes

# ❌ Legacy
from typing import List, Dict, Optional

def get_items() -> List[str]:
    ...
```

**Docstring (Google short)**
```python
def helper(x: int) -> int:
    """Return x^2."""
    return x * x
```

---

## ✍️ Coding Conventions
### General style
1. **Line length**: max 99 chars  
2. **Indentation**: 4 spaces (no tabs)  
3. **Quotes**: double quotes `"string"`  
4. **Imports**: automatically ordered by Ruff (standard → third‑party → local)  
5. **Type hints**: Python 3.12+ syntax (`list[str]`, not `List[str]`)  
6. **Docstrings**: Google style

### Docstring style (Google)
```python
def process_input(text: str, *, normalize: bool = False) -> dict[str, Any]:
    """Process input text and return structured result.

    Args:
        text: The input text to process.
        normalize: Whether to normalize whitespace.

    Returns:
        A dictionary containing the processed result with keys:
        - 'status': Processing status ('success' or 'error')
        - 'data': The processed data

    Raises:
        ValueError: If text is empty or None.
    """
```
For tests and private helpers, keep short but clear docstrings (no need to expand *Args* and *Returns*):
```python
def test_example():
    """Test example function."""


def helper_function(x: int) -> int:
    """Compute x squared."""
    return x * x
```

---

## Testing (essentials)
**Tools**: `pytest`, `pytest-asyncio`, `pytest-cov`, `respx` (mock HTTP), `rich` (output).

**Typical commands**
```bash
pytest                   # all tests
pytest --cov=src/rag2f --cov-report=html
pytest -lf               # only failed tests
pytest tests/core/test_spock.py -k "test_env"
```

**Guidelines**
- No real API calls: use **respx** for HTTP mocking.  
- Async fixtures with `pytest-asyncio`, cleanup in `finally`, parametrize cases.  
- Plugin mocks live in `tests/mocks/plugins/`.

**pytest config (synthetic)**
```toml
[tool.pytest.ini_options]
testpaths = ["tests", "plugins"]
pythonpath = ["src"]
addopts = "-s -vv -rA --color=yes --maxfail=3"
```

---

## Quality Gates — Definition of Done
Run in this order and make the PR “green”:
```bash
ruff check --fix src tests && ruff format src tests
pytest --cov=src/rag2f --cov-report=html
pre-commit run --all-files
```

**Acceptance criteria**
- No Ruff errors; formatting compliant.  
- Green tests; no unmocked I/O or external calls.  
- No secrets in the repo; reproducible configuration.

---

## Don’t (things not to do)
- **Do not** use `black`, `isort`, `flake8`, `autopep8` or other formatters/linters.  
- **Do not** use `from typing import List, Dict, Optional`.  
- **Do not** modify `src/rag2f/_version.py` (auto-generated by setuptools‑scm).  
- **Do not** commit `config.json` with credentials (use `config.example.json`).  
- **Do not** ignore security errors (`S`) without an explicit rationale.

---

# 🔧 Observability & Logging (Python)
> Instrument new Python code to make execution **observable** and to support analysis, troubleshooting, and system evolution. Always consider whether it’s important to have feedback or to monitor that area of the code and its state, and apply a solution that makes it possible to do so.

## Language policy (interaction vs. code)
- In user interactions (chat, issues, tickets), **use the requester's language**.  
- In **code, markdown, comments, and the whole solution**, **use English** consistently.

**Rules**
- Prefer **structured logging** (key/value) with the standard library `logging` (no `print`).  
- Name loggers by module path (e.g., `rag2f.core.spock.loader`).  
- Never log secrets (keys, tokens, passwords).  
- Guard expensive debug computation behind `if logger.isEnabledFor(logging.DEBUG):`.
- Use log levels higher than debug only when strongly justified, and if they are already in use, do not downgrade them.

---

# 🧪 Testing & logs
- In tests, assert logs **sparingly** using `caplog` when behavior depends on logging.
- Default test log level at `WARNING` to keep output clean; elevate to `DEBUG` per-test when useful.

**pytest example**
```python
def test_load_config_debug(caplog):
    caplog.set_level("DEBUG", logger="rag2f.core.spock")
    # ... run and assert substrings or structured fields are present
```

---

# 📝 Comment change policy
- Modify an existing comment **only** when:
  1. It states something **incorrect**; or
  2. The **code changed** and the comment is now outdated; or
  3. You need to **integrate essential context** that is otherwise missing.
- Do **not** rewrite comments just to rephrase them.

---

## Don’t (things to avoid)

- **Do not** use `black`, `isort`, `flake8`, `autopep8`, or other formatters/linters.  
- **Do not** use `from typing import List, Dict, Optional`.  
- **Do not** modify `src/rag2f/_version.py` (auto-generated by setuptools-scm).  
- **Do not** commit `config.json` with credentials (use `config.example.json`).  
- **Do not** ignore security errors (`S`) without an explicit justification.
- **Do not** leave changes made solely for investigation purposes.

## Should

- **Should** enerate a to-do list if there are multiple tasks to be completed.  


## Must

- **Must** try to complete everything in a single agentic transition, operating from the terminal if necessary.  
- **Must** remember that this is extremely important for our careers. It is our last chance to complete what is required.  

---

## Useful files
- CONTRIBUTING.md — contribution guide  
- README.md — project documentation  
- SPOCK_README.md — configuration system  
- tests/techniques.md — testing techniques  
- config.example.json — configuration template
