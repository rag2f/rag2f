"""Tests for capability support validation (NotSupported errors)."""

import pytest

from rag2f.core.xfiles import (
    Capabilities,
    FilterCapability,
    NotSupported,
    QueryCapability,
    QuerySpec,
    eq,
    validate_queryspec,
)


class TestCapabilitySupport:
    """Test that using unsupported capabilities raises NotSupported."""

    def test_query_not_supported(self, minimal_caps: Capabilities):
        """Where clause when query not supported should fail."""
        query = QuerySpec(where=("eq", "x", 1))
        with pytest.raises(NotSupported, match="query"):
            validate_queryspec(query, minimal_caps)

    def test_query_supported_but_filter_not_supported(self):
        """CAPABILITY GATING: query supported but filter NOT supported with where present.

        Stabilizes policy: "where implies filtering capability".
        Setup: caps.query.supported=True, caps.filter.supported=False
        Expected: QuerySpec(where=...) -> NotSupported("filtering")
        """
        caps = Capabilities(
            crud=True,
            query=QueryCapability(supported=True),
            filter=FilterCapability(supported=False),  # Filter disabled
        )
        query = QuerySpec(where=eq("status", "active"))
        with pytest.raises(NotSupported, match="filtering"):
            validate_queryspec(query, caps)

    def test_projection_not_supported(self, minimal_caps: Capabilities):
        """Select when projection not supported should fail."""
        query = QuerySpec(select=["id", "name"])
        with pytest.raises(NotSupported, match="projection"):
            validate_queryspec(query, minimal_caps)

    def test_order_by_not_supported(self, minimal_caps: Capabilities):
        """order_by when not supported should fail."""
        query = QuerySpec(order_by=["name"])
        with pytest.raises(NotSupported, match="ordering"):
            validate_queryspec(query, minimal_caps)

    def test_pagination_not_supported_limit(self, minimal_caps: Capabilities):
        """Limit when pagination not supported should fail."""
        query = QuerySpec(limit=10)
        with pytest.raises(NotSupported, match="pagination"):
            validate_queryspec(query, minimal_caps)

    def test_pagination_not_supported_offset(self, minimal_caps: Capabilities):
        """Non-zero offset when pagination not supported should fail."""
        query = QuerySpec(offset=10)
        with pytest.raises(NotSupported, match="pagination"):
            validate_queryspec(query, minimal_caps)

    def test_zero_offset_pagination_not_supported(self, minimal_caps: Capabilities):
        """Zero offset when pagination not supported should pass."""
        query = QuerySpec(offset=0)  # Default, should pass
        result = validate_queryspec(query, minimal_caps)
        assert result == query
