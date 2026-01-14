"""Pytest fixtures.

This file adjusts sys.path for src-layout imports.
"""

# ruff: noqa: E402

import os
import sys

# Ensure `src` is on sys.path so imports like `from rag2f.core...` resolve during tests
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
if os.path.isdir(SRC):
    sys.path.insert(0, SRC)
sys.path.insert(0, ROOT)

import pytest
import pytest_asyncio
from rich.traceback import install

from rag2f.core.morpheus.morpheus import Morpheus
from rag2f.core.rag2f import RAG2F
from tests.utils import PATH_MOCK

# Enable readable tracebacks in development / test environments.
# Can be disabled with PYTEST_RICH=0
if os.getenv("PYTEST_RICH", "1") == "1":
    install(
        show_locals=True,  # show local variables for each frame
        width=None,  # use terminal width
        word_wrap=True,  # wrap long lines
        extra_lines=1,  # some context around lines
        suppress=["/usr/lib/python3", "site-packages"],  # hide "noisy" third-party frames
    )


@pytest_asyncio.fixture(scope="session")
async def rag2f():
    """Provide a session-scoped RAG2F instance for tests."""
    instance = await RAG2F.create(plugins_folder=f"{PATH_MOCK}/plugins/")
    return instance


@pytest_asyncio.fixture(scope="session")
async def morpheus(rag2f):
    """Provide the session-scoped Morpheus instance for tests."""
    return rag2f.morpheus


@pytest.fixture(scope="function")
def fresh_morpheus(rag2f):
    """Return a fresh Morpheus instance bound to the session rag2f.

    Useful for tests that need to patch entry points / plugin discovery without
    mutating the session-scoped Morpheus fixture.
    """
    return Morpheus(rag2f, plugins_folder=f"{PATH_MOCK}/plugins/")
