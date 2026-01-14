"""Tests for arity and type validation errors."""

import pytest

from rag2f.core.xfiles import (
    Capabilities,
    QuerySpec,
    ValidationError,
    validate_queryspec,
)


class TestArityValidation:
    """Test that incorrect arity raises ValidationError."""

    def test_eq_with_too_few_args(self, full_caps: Capabilities):
        """Eq with only 2 elements should fail."""
        query = QuerySpec(where=("eq", "name"))  # Missing value
        with pytest.raises(ValidationError, match="requires 3 elements, got 2"):
            validate_queryspec(query, full_caps)

    def test_eq_with_too_many_args(self, full_caps: Capabilities):
        """Eq with 4 elements should fail."""
        query = QuerySpec(where=("eq", "name", "Alice", "extra"))
        with pytest.raises(ValidationError, match="requires 3 elements, got 4"):
            validate_queryspec(query, full_caps)

    def test_and_with_only_one_condition(self, full_caps: Capabilities):
        """And with only one child should fail."""
        query = QuerySpec(where=("and", ("eq", "x", 1)))
        with pytest.raises(ValidationError, match="requires 3 elements, got 2"):
            validate_queryspec(query, full_caps)

    def test_or_with_too_few_args(self, full_caps: Capabilities):
        """Or with only one child should fail."""
        query = QuerySpec(where=("or", ("eq", "x", 1)))
        with pytest.raises(ValidationError, match="requires 3 elements, got 2"):
            validate_queryspec(query, full_caps)

    def test_not_with_too_many_args(self, full_caps: Capabilities):
        """Not with 2 conditions should fail."""
        query = QuerySpec(where=("not", ("eq", "x", 1), ("eq", "y", 2)))
        with pytest.raises(ValidationError, match="requires 2 elements, got 3"):
            validate_queryspec(query, full_caps)

    def test_exists_with_value(self, full_caps: Capabilities):
        """Exists with value argument should fail."""
        query = QuerySpec(where=("exists", "field", True))
        with pytest.raises(ValidationError, match="requires 2 elements, got 3"):
            validate_queryspec(query, full_caps)

    def test_empty_where_node(self, full_caps: Capabilities):
        """Empty tuple should fail."""
        query = QuerySpec(where=())
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_queryspec(query, full_caps)


class TestTypeValidation:
    """Test that incorrect types raise ValidationError."""

    def test_where_not_tuple(self, full_caps: Capabilities):
        """Where as list should fail."""
        query = QuerySpec(where=["eq", "name", "Alice"])  # type: ignore
        with pytest.raises(ValidationError, match="must be a tuple"):
            validate_queryspec(query, full_caps)

    def test_operator_not_string(self, full_caps: Capabilities):
        """Operator as integer should fail."""
        query = QuerySpec(where=(123, "name", "Alice"))  # type: ignore
        with pytest.raises(ValidationError, match="Operator must be a string"):
            validate_queryspec(query, full_caps)

    def test_field_name_not_string(self, full_caps: Capabilities):
        """Field name as integer should fail."""
        query = QuerySpec(where=("eq", 123, "Alice"))  # type: ignore
        with pytest.raises(ValidationError, match="Field name must be a string"):
            validate_queryspec(query, full_caps)

    def test_select_field_not_string(self, full_caps: Capabilities):
        """Select with non-string field should fail."""
        query = QuerySpec(select=["name", 123])  # type: ignore
        with pytest.raises(ValidationError, match="Select field must be a string"):
            validate_queryspec(query, full_caps)

    def test_order_by_field_not_string(self, full_caps: Capabilities):
        """Order by with non-string field should fail."""
        query = QuerySpec(order_by=["name", 123])  # type: ignore
        with pytest.raises(ValidationError, match="Order field must be a string"):
            validate_queryspec(query, full_caps)

    def test_limit_not_integer(self, full_caps: Capabilities):
        """Limit as string should fail."""
        query = QuerySpec(limit="100")  # type: ignore
        with pytest.raises(ValidationError, match="Limit must be an integer"):
            validate_queryspec(query, full_caps)

    def test_negative_limit(self, full_caps: Capabilities):
        """Negative limit should fail."""
        query = QuerySpec(limit=-10)
        with pytest.raises(ValidationError, match="must be non-negative"):
            validate_queryspec(query, full_caps)

    def test_negative_offset(self, full_caps: Capabilities):
        """Negative offset should fail."""
        query = QuerySpec(offset=-5)
        with pytest.raises(ValidationError, match="must be non-negative"):
            validate_queryspec(query, full_caps)

    def test_in_operator_values_must_be_list(self, full_caps: Capabilities):
        """In operator with tuple values should fail (must be list for JSON compatibility)."""
        # Manually construct a tuple-based in node (bypassing the in_ builder)
        query = QuerySpec(where=("in", "status", ("active", "pending")))  # tuple, not list
        with pytest.raises(ValidationError, match="must be a list"):
            validate_queryspec(query, full_caps)

    def test_in_operator_values_as_set_fails(self, full_caps: Capabilities):
        """In operator with set values should fail."""
        query = QuerySpec(where=("in", "status", {"active", "pending"}))  # set, not list
        with pytest.raises(ValidationError, match="must be a list"):
            validate_queryspec(query, full_caps)
