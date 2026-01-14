"""Tests for field allowlist validation."""

import pytest

from rag2f.core.xfiles import (
    Capabilities,
    QuerySpec,
    ValidationError,
    and_,
    eq,
    exists,
    not_,
    or_,
    validate_queryspec,
)


class TestFieldAllowlist:
    """Test field allowlist enforcement."""

    def test_where_field_not_allowed(self, full_caps: Capabilities):
        """Where with disallowed field should fail."""
        query = QuerySpec(where=eq("secret_field", "value"))
        with pytest.raises(ValidationError, match="not in allowed fields"):
            validate_queryspec(query, full_caps, allowed_fields={"name", "age", "status"})

    def test_where_field_allowed(self, full_caps: Capabilities):
        """Where with allowed field should pass."""
        query = QuerySpec(where=eq("name", "Alice"))
        result = validate_queryspec(query, full_caps, allowed_fields={"name", "age", "status"})
        assert result == query

    def test_select_field_not_allowed(self, full_caps: Capabilities):
        """Select with disallowed field should fail."""
        query = QuerySpec(select=["id", "secret_field"])
        with pytest.raises(ValidationError, match="not allowed in select"):
            validate_queryspec(query, full_caps, allowed_select={"id", "name", "email"})

    def test_select_field_allowed(self, full_caps: Capabilities):
        """Select with allowed fields should pass."""
        query = QuerySpec(select=["id", "name"])
        result = validate_queryspec(query, full_caps, allowed_select={"id", "name", "email"})
        assert result == query

    def test_order_by_field_not_allowed(self, full_caps: Capabilities):
        """order_by with disallowed field should fail."""
        query = QuerySpec(order_by=["secret_field"])
        with pytest.raises(ValidationError, match="not allowed in order_by"):
            validate_queryspec(query, full_caps, allowed_order_by={"name", "created_at"})

    def test_order_by_descending_field_not_allowed(self, full_caps: Capabilities):
        """order_by descending with disallowed field should fail."""
        query = QuerySpec(order_by=["-secret_field"])
        with pytest.raises(ValidationError, match="not allowed in order_by"):
            validate_queryspec(query, full_caps, allowed_order_by={"name", "created_at"})

    def test_order_by_descending_field_allowed(self, full_caps: Capabilities):
        """order_by descending with allowed field should pass."""
        query = QuerySpec(order_by=["-created_at"])
        result = validate_queryspec(query, full_caps, allowed_order_by={"name", "created_at"})
        assert result == query

    def test_exists_field_not_allowed(self, full_caps: Capabilities):
        """Exists with disallowed field should fail."""
        query = QuerySpec(where=exists("secret"))
        with pytest.raises(ValidationError, match="not in allowed fields"):
            validate_queryspec(query, full_caps, allowed_fields={"name", "email"})

    def test_nested_where_field_not_allowed(self, full_caps: Capabilities):
        """Nested where with disallowed field should fail."""
        query = QuerySpec(
            where=and_(
                eq("name", "Alice"),
                eq("secret", "value"),  # Not allowed
            )
        )
        with pytest.raises(ValidationError, match="not in allowed fields"):
            validate_queryspec(query, full_caps, allowed_fields={"name", "age"})

    def test_deeply_nested_error_path_diagnostic(self, full_caps: Capabilities):
        """Deeply nested where error should include diagnostic path in ValidationError.field.

        Structure: where=or(eq("ok",...), not(and(eq("ok",...), eq("secret",...))))
        The "secret" field is at path: where.or.right -> not -> and.right
        ValidationError.field should contain path like "where.or.right.not.and.right[1]"
        """
        query = QuerySpec(
            where=or_(
                eq("name", "Alice"),  # OK
                not_(
                    and_(
                        eq("age", 30),  # OK
                        eq("secret", "value"),  # NOT ALLOWED - deeply nested
                    )
                ),
            )
        )
        with pytest.raises(ValidationError) as exc_info:
            validate_queryspec(query, full_caps, allowed_fields={"name", "age"})

        # Verify error contains diagnostic path
        error = exc_info.value
        assert error.field is not None, "ValidationError.field should contain path"
        # Path should indicate deep nesting (contains or/not/and markers)
        assert "or" in error.field or "not" in error.field or "and" in error.field, (
            f"Path should be diagnostic, got: {error.field}"
        )
        assert "secret" in str(error.value) or "secret" in error.details, (
            "Error should mention the problematic field 'secret'"
        )

    def test_no_allowlist_allows_all(self, full_caps: Capabilities):
        """Without allowlist, all fields should be allowed."""
        query = QuerySpec(
            select=["any_field"],
            where=eq("any_other_field", "value"),
            order_by=["yet_another_field"],
        )
        result = validate_queryspec(query, full_caps)
        assert result == query
