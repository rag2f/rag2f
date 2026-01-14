"""Tests for operator support validation (NotSupported errors)."""

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


class TestOperatorSupport:
    """Test that unsupported operators raise NotSupported."""

    def test_unsupported_operator(self, limited_ops_caps: Capabilities):
        """Using gt when only eq/and supported should fail."""
        query = QuerySpec(where=("gt", "age", 18))
        with pytest.raises(NotSupported, match="filter operator 'gt'"):
            validate_queryspec(query, limited_ops_caps)

    def test_unsupported_or(self, limited_ops_caps: Capabilities):
        """Using or when not in ops should fail."""
        query = QuerySpec(where=("or", ("eq", "a", 1), ("eq", "b", 2)))
        with pytest.raises(NotSupported, match="filter operator 'or'"):
            validate_queryspec(query, limited_ops_caps)

    def test_unsupported_not(self, limited_ops_caps: Capabilities):
        """Using not when not in ops should fail."""
        query = QuerySpec(where=("not", ("eq", "x", 1)))
        with pytest.raises(NotSupported, match="filter operator 'not'"):
            validate_queryspec(query, limited_ops_caps)

    def test_supported_operator_passes(self, limited_ops_caps: Capabilities):
        """Using eq (which is supported) should pass."""
        query = QuerySpec(where=eq("name", "Alice"))
        result = validate_queryspec(query, limited_ops_caps)
        assert result == query

    def test_unknown_operator(self, full_caps: Capabilities):
        """Unknown operator should fail as NotSupported (not in caps.filter.ops)."""
        query = QuerySpec(where=("foobar", "field", "value"))
        # Unknown operator is first checked against caps.filter.ops
        # Since it's not there, we get NotSupported
        with pytest.raises(NotSupported, match="filter operator 'foobar'"):
            validate_queryspec(query, full_caps)

    def test_unknown_operator_when_filter_disabled(self):
        """Unknown operator should raise NotSupported when filtering is disabled."""
        # With filter not supported, validation skips the caps check
        # and goes to arity validation where it fails
        caps = Capabilities(
            query=QueryCapability(supported=True),
            filter=FilterCapability(supported=False),
        )
        query = QuerySpec(where=("foobar", "field", "value"))
        with pytest.raises(NotSupported, match="filtering"):
            validate_queryspec(query, caps)
