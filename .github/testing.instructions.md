---
name: RAG2F Testing Instructions
description: Agent-oriented testing guidelines for RAG2F
applyTo: "tests/**/*.py"
---

# RAG2F – Testing Guidelines (Agent-Oriented)

## 🎯 Testing Philosophy

Tests are written to validate **our code behavior**, not third-party libraries.

Key principles:
- Prefer **conceptual clarity over exhaustive coverage**
- Use **lightweight mocks** instead of real integrations
- Plugins are **always mocked**
- Tests must be **isolated, deterministic, and repeatable**
- Shared setup belongs in **fixtures**, not in tests

> For Copilot agents: focus on **contracts, side effects, and state transitions**, not on implementation details.

---

## 🧩 Test Structure (Conceptual)

- `conftest.py`  
  Shared fixtures and test environment setup.
- `mocks/plugins/`  
  Mock plugins used for integration-style tests.
- `core/`  
  Tests for core RAG2F components.
- `**/`  
  Tests for other classes.

---

## 🔌 Plugin Mocking (Key Concept)

All plugins used in tests are **mock plugins**.

Why:
- Real plugins introduce side effects
- Filesystem and dynamic loading must be predictable
- Hook execution order must be controllable

Mock plugins:
- Live under `tests/mocks/plugins/`
- Behave like real plugins, but only implement **test-specific hooks**
- Are safe to load in automated environments

> Copilot hint: assume plugins as **replaceable dependencies**, never as trusted runtime code.

---

## ⚙️ Fixtures and State Management

- Use **session-scoped fixtures** for expensive, stable objects
- Use **function-scoped fixtures** for mutable state
- Never share mutable state across tests

Conceptually:
- Session = infrastructure
- Function = behavior under test

---

## 🧪 Common Testing Patterns

Preferred patterns:
- Async tests for async code
- Parametrized tests for scenario coverage
- Explicit error testing using exceptions
- Monkeypatching for non-deterministic behavior (time, UUIDs, env vars)

Avoid:
- Real HTTP calls
- `time.sleep`
- Order-dependent tests
- Implicit shared state

---

## 🌐 External Interactions

All external services must be mocked:
- HTTP calls
- Embedding APIs
- Filesystem side effects
- Environment variables

Tests must run **offline** and without credentials.

---

## ✅ Test Quality Checklist

Before committing:
- Tests are deterministic
- No real I/O or network calls
- Temporary resources are cleaned up
- Test names describe **behavior**, not implementation
- Mock plugins are used where plugins are involved

---

## 🚫 Anti-Patterns

- Testing third-party library internals
- Depending on test execution order
- Leaving temporary files behind
- Sharing mutable singletons
- Using real plugins or APIs

---

## 🧠 Mental Model for Copilot

When generating or modifying tests:
- Identify the **unit or collaboration**
- Replace external dependencies with **mocks**
- Assert on **observable behavior**
- Prefer **simple, explicit setups**

> If a test is hard to explain, it is probably doing too much.
