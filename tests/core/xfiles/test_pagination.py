"""Tests for pagination and max_limit clamping."""

from rag2f.core.xfiles import (
    Capabilities,
    PaginationCapability,
    QueryCapability,
    QuerySpec,
    eq,
    validate_queryspec,
)


class TestMaxLimitClamping:
    """Test that limit is clamped to max_limit from capabilities."""

    def test_limit_under_max(self, full_caps: Capabilities):
        """Limit under max_limit should not be modified."""
        # full_caps has max_limit=1000
        query = QuerySpec(limit=500)
        result = validate_queryspec(query, full_caps)
        assert result.limit == 500

    def test_limit_at_max(self, full_caps: Capabilities):
        """Limit at max_limit should not be modified."""
        query = QuerySpec(limit=1000)
        result = validate_queryspec(query, full_caps)
        assert result.limit == 1000

    def test_limit_over_max(self, full_caps: Capabilities):
        """Limit over max_limit should be clamped."""
        query = QuerySpec(limit=5000)
        result = validate_queryspec(query, full_caps)
        assert result.limit == 1000  # Clamped to max_limit

    def test_limit_clamped_returns_new_queryspec(self, full_caps: Capabilities):
        """When limit is clamped, a new QuerySpec is returned."""
        query = QuerySpec(
            select=["id"],
            where=eq("status", "active"),
            limit=5000,
        )
        result = validate_queryspec(query, full_caps)

        # Should be a new object
        assert result is not query
        # Other fields preserved
        assert result.select == ["id"]
        assert result.where == ("eq", "status", "active")
        # Limit clamped
        assert result.limit == 1000

    def test_no_max_limit_no_clamping(self):
        """Without max_limit, any limit should pass."""
        caps = Capabilities(
            query=QueryCapability(supported=True),
            pagination=PaginationCapability(supported=True, max_limit=None),
        )
        query = QuerySpec(limit=999999)
        result = validate_queryspec(query, caps)
        assert result.limit == 999999

    def test_smaller_max_limit(self, limited_ops_caps: Capabilities):
        """With smaller max_limit=100, larger limits are clamped."""
        query = QuerySpec(limit=200)
        result = validate_queryspec(query, limited_ops_caps)
        assert result.limit == 100
