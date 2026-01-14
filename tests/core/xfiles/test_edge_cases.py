"""Tests for edge cases and boundary conditions."""

import pytest

from rag2f.core.xfiles import (
    Capabilities,
    QuerySpec,
    ValidationError,
    and_,
    contains,
    eq,
    in_,
    not_,
    or_,
    validate_queryspec,
)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_deeply_nested_and_or(self, full_caps: Capabilities):
        """Deeply nested AND/OR should be validated recursively."""
        query = QuerySpec(
            where=and_(
                or_(and_(eq("a", 1), eq("b", 2)), eq("c", 3)), not_(or_(eq("d", 4), eq("e", 5)))
            )
        )
        result = validate_queryspec(query, full_caps)
        assert result == query

    def test_in_operator_with_list_values(self, full_caps: Capabilities):
        """in_ operator with list values should pass (canonical form)."""
        query = QuerySpec(where=in_("status", ["active", "pending", "review"]))
        result = validate_queryspec(query, full_caps)
        assert result == query
        # Verify the builder produces a list, not a tuple
        assert isinstance(query.where[2], list)

    def test_contains_string_operator(self, full_caps: Capabilities):
        """Contains operator should pass."""
        query = QuerySpec(where=contains("description", "keyword"))
        result = validate_queryspec(query, full_caps)
        assert result == query

    def test_multiple_order_by_with_mixed_direction(self, full_caps: Capabilities):
        """Multiple order_by fields with mixed directions should pass."""
        query = QuerySpec(order_by=["-created_at", "name", "-priority"])
        result = validate_queryspec(query, full_caps)
        assert result == query

    def test_empty_select_list(self, full_caps: Capabilities):
        """Empty select list should pass (means no projection)."""
        query = QuerySpec(select=[])
        result = validate_queryspec(query, full_caps)
        assert result == query

    def test_empty_order_by_list(self, full_caps: Capabilities):
        """Empty order_by list should pass."""
        query = QuerySpec(order_by=[])
        result = validate_queryspec(query, full_caps)
        assert result == query

    def test_zero_limit(self, full_caps: Capabilities):
        """Zero limit should pass (valid edge case)."""
        query = QuerySpec(limit=0)
        result = validate_queryspec(query, full_caps)
        assert result.limit == 0

    def test_dot_notation_fields(self, full_caps: Capabilities):
        """Dot-notation field names should work."""
        query = QuerySpec(
            select=["profile.name", "profile.email"],
            where=eq("profile.status", "active"),
            order_by=["-profile.created_at"],
        )
        result = validate_queryspec(query, full_caps)
        assert result == query

    def test_dot_notation_with_allowlist(self, full_caps: Capabilities):
        """Dot-notation fields should match allowlist exactly."""
        query = QuerySpec(where=eq("profile.status", "active"))

        # Should fail - allowlist has "profile", not "profile.status"
        with pytest.raises(ValidationError):
            validate_queryspec(query, full_caps, allowed_fields={"profile", "name"})

        # Should pass - allowlist has exact match
        result = validate_queryspec(query, full_caps, allowed_fields={"profile.status", "name"})
        assert result == query


class TestInOperatorCanonicalForm:
    """Regression tests for in_() operator canonical form.

    Historical bug: in_() builder produced tuple values but validator required list.
    Fix: in_() now uses list(values) to normalize any iterable to list.

    These tests ensure we don't regress to tuple output.
    """

    def test_in_builder_normalizes_tuple_input_to_list(self, full_caps: Capabilities):
        """REGRESSION: in_() must convert tuple input to list for JSON compatibility.

        This test guards against regression where in_() produced:
            ('in', 'field', ('a', 'b'))  # tuple - WRONG
        instead of:
            ('in', 'field', ['a', 'b'])  # list - CORRECT
        """
        # Pass tuple to in_() builder
        node = in_("status", ("active", "pending", "review"))

        # Builder MUST normalize to list
        assert isinstance(node[2], list), f"in_() must produce list, got {type(node[2]).__name__}"
        assert node == ("in", "status", ["active", "pending", "review"])

        # Must pass validation
        query = QuerySpec(where=node)
        result = validate_queryspec(query, full_caps)
        assert result == query

    def test_in_builder_normalizes_generator_to_list(self, full_caps: Capabilities):
        """in_() must convert generator/iterator to list."""
        # Pass generator expression
        node = in_("id", (x for x in [1, 2, 3]))

        assert isinstance(node[2], list)
        assert node[2] == [1, 2, 3]

        query = QuerySpec(where=node)
        result = validate_queryspec(query, full_caps)
        assert result == query

    def test_in_builder_preserves_list_input(self, full_caps: Capabilities):
        """in_() with list input should preserve it as list."""
        original = ["active", "pending"]
        node = in_("status", original)

        assert isinstance(node[2], list)
        # Should be a new list (copy), not the same reference
        assert node[2] == original

        query = QuerySpec(where=node)
        result = validate_queryspec(query, full_caps)
        assert result == query

    def test_manual_tuple_values_rejected_by_validator(self, full_caps: Capabilities):
        """Manually constructed tuple values must be rejected by validator.

        This ensures the validator acts as a safety net when the builder is bypassed.
        """
        # Bypass builder, manually construct with tuple
        manual_node = ("in", "status", ("active", "pending"))
        query = QuerySpec(where=manual_node)

        with pytest.raises(ValidationError, match="must be a list"):
            validate_queryspec(query, full_caps)

    def test_in_canonical_form_with_nested_conditions(self, full_caps: Capabilities):
        """in_() canonical form must work in nested AND/OR conditions."""
        query = QuerySpec(
            where=and_(
                in_("status", ("active", "pending")),  # tuple input
                or_(
                    eq("role", "admin"),
                    in_("department", ["IT", "HR", "Finance"]),  # list input
                ),
            )
        )

        # Both in_ nodes should have list values
        # where = (and, left, right)
        # left = (in, "status", values)
        left = query.where[1]
        assert isinstance(left[2], list), "Nested in_() must produce list"

        # right = (or, ..., in_node)
        right_in = query.where[2][2]  # (or, eq_node, in_node) -> in_node
        assert isinstance(right_in[2], list), "Nested in_() must produce list"

        result = validate_queryspec(query, full_caps)
        assert result == query
