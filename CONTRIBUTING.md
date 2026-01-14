# Contributing

Thanks for contributing to rag2f.

## Development standards (Ruff-only)

This project uses **Ruff only** for:

- Linting (including security checks)
- Import sorting
- Formatting

Key settings:

- Target Python: **3.12**
- Line length: **99**
- Security rules enabled (Bandit-like `S` checks)
- Tests may use `assert` (security rule `S101` is ignored in `tests/`)

## Quickstart

Use the project-local `.venv` so the workflow is consistent across Dev Container and local setups:

```bash
bash scripts/bootstrap-venv.sh
source .venv/bin/activate
```

Install dev dependencies (manual alternative):

```bash
pip install -e '.[dev]'
```

Install and enable pre-commit:

```bash
pip install pre-commit
pre-commit install
```

Run all hooks locally:

```bash
pre-commit run --all-files
```

## Running Ruff manually

```bash
ruff check src tests
ruff check --fix src tests
ruff format src tests
ruff format --check src tests
```

## Running tests

```bash
pytest
```

## Before opening a PR

- Ensure `pre-commit run --all-files` is clean.
- Ensure `pytest` passes.
- Keep changes focused and avoid unrelated refactors.
