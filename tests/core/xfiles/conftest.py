"""Shared fixtures for XFiles validation tests."""

import pytest

from rag2f.core.xfiles import (
    Capabilities,
    FeatureSupport,
    FilterCapability,
    PaginationCapability,
    QueryCapability,
)


@pytest.fixture
def full_caps() -> Capabilities:
    """Capabilities with full support for all common operations."""
    return Capabilities(
        crud=True,
        query=QueryCapability(supported=True),
        projection=FeatureSupport(supported=True, pushdown=True),
        filter=FilterCapability(
            supported=True,
            pushdown=True,
            ops=(
                "eq",
                "ne",
                "gt",
                "gte",
                "lt",
                "lte",
                "in",
                "and",
                "or",
                "not",
                "exists",
                "contains",
            ),
        ),
        order_by=FeatureSupport(supported=True, pushdown=True),
        pagination=PaginationCapability(
            supported=True,
            pushdown=True,
            mode="offset",
            max_limit=1000,
        ),
    )


@pytest.fixture
def minimal_caps() -> Capabilities:
    """Minimal capabilities (CRUD only, no queries)."""
    return Capabilities(
        crud=True,
        query=QueryCapability(supported=False),
        projection=FeatureSupport(supported=False),
        filter=FilterCapability(supported=False),
        order_by=FeatureSupport(supported=False),
        pagination=PaginationCapability(supported=False),
    )


@pytest.fixture
def limited_ops_caps() -> Capabilities:
    """Capabilities with limited filter operators (only eq, and)."""
    return Capabilities(
        crud=True,
        query=QueryCapability(supported=True),
        projection=FeatureSupport(supported=True),
        filter=FilterCapability(
            supported=True,
            pushdown=True,
            ops=("eq", "and"),
        ),
        order_by=FeatureSupport(supported=True),
        pagination=PaginationCapability(supported=True, max_limit=100),
    )
