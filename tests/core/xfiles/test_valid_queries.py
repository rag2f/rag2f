"""Tests for valid query validation (happy path)."""

from rag2f.core.xfiles import (
    Capabilities,
    QuerySpec,
    and_,
    eq,
    exists,
    gt,
    gte,
    ne,
    not_,
    or_,
    validate_queryspec,
)


class TestValidQueries:
    """Test that valid queries pass validation."""

    def test_empty_query(self, full_caps: Capabilities):
        """Empty QuerySpec should pass."""
        query = QuerySpec()
        result = validate_queryspec(query, full_caps)
        assert result == query

    def test_simple_eq(self, full_caps: Capabilities):
        """Simple eq condition should pass."""
        query = QuerySpec(where=eq("name", "Alice"))
        result = validate_queryspec(query, full_caps)
        assert result == query

    def test_comparison_operators(self, full_caps: Capabilities):
        """All comparison operators should pass with correct arity."""
        for op_fn, field, value in [
            (eq, "age", 30),
            (ne, "status", "deleted"),
            (gt, "score", 100),
            (gte, "count", 5),
        ]:
            query = QuerySpec(where=op_fn(field, value))
            result = validate_queryspec(query, full_caps)
            assert result == query

    def test_logical_and(self, full_caps: Capabilities):
        """AND with two conditions should pass."""
        query = QuerySpec(where=and_(eq("status", "active"), gt("age", 18)))
        result = validate_queryspec(query, full_caps)
        assert result == query

    def test_logical_or(self, full_caps: Capabilities):
        """OR with two conditions should pass."""
        query = QuerySpec(where=or_(eq("role", "admin"), eq("role", "superuser")))
        result = validate_queryspec(query, full_caps)
        assert result == query

    def test_logical_not(self, full_caps: Capabilities):
        """NOT with one condition should pass."""
        query = QuerySpec(where=not_(eq("deleted", True)))
        result = validate_queryspec(query, full_caps)
        assert result == query

    def test_exists_operator(self, full_caps: Capabilities):
        """EXISTS with field should pass."""
        query = QuerySpec(where=exists("email"))
        result = validate_queryspec(query, full_caps)
        assert result == query

    def test_nested_conditions(self, full_caps: Capabilities):
        """Deeply nested conditions should pass."""
        query = QuerySpec(
            where=and_(or_(eq("type", "user"), eq("type", "admin")), not_(eq("banned", True)))
        )
        result = validate_queryspec(query, full_caps)
        assert result == query

    def test_select_fields(self, full_caps: Capabilities):
        """Select with string fields should pass."""
        query = QuerySpec(select=["id", "name", "email"])
        result = validate_queryspec(query, full_caps)
        assert result == query

    def test_order_by_ascending(self, full_caps: Capabilities):
        """Order by ascending should pass."""
        query = QuerySpec(order_by=["created_at", "name"])
        result = validate_queryspec(query, full_caps)
        assert result == query

    def test_order_by_descending(self, full_caps: Capabilities):
        """Order by descending (with -) should pass."""
        query = QuerySpec(order_by=["-created_at", "name"])
        result = validate_queryspec(query, full_caps)
        assert result == query

    def test_pagination(self, full_caps: Capabilities):
        """Valid pagination should pass."""
        query = QuerySpec(limit=50, offset=100)
        result = validate_queryspec(query, full_caps)
        assert result == query

    def test_full_query(self, full_caps: Capabilities):
        """Complete query with all options should pass."""
        query = QuerySpec(
            select=["id", "name"],
            where=and_(eq("status", "active"), gt("age", 21)),
            order_by=["-created_at"],
            limit=10,
            offset=0,
        )
        result = validate_queryspec(query, full_caps)
        assert result == query
