"""Tests for XFile QuerySpec Validation Module.

Tests cover:
- WhereNode arity validation
- Operator support validation against Capabilities
- Field allowlist validation for select/where/order_by
- Pagination limit enforcement (max_limit clamping)
"""

import pytest

from rag2f.core.xfile import (
    # Types
    QuerySpec,
    WhereNode,
    # Query builders
    eq,
    ne,
    gt,
    gte,
    and_,
    or_,
    not_,
    exists,
    contains,
    in_,
    # Capabilities
    Capabilities,
    FilterCapability,
    FeatureSupport,
    PaginationCapability,
    QueryCapability,
    # Validation
    validate_queryspec,
    get_expected_arity,
    ALL_KNOWN_OPS,
    ARITY_2_UNARY,
    ARITY_3_COMPARISON,
    ARITY_3_LOGICAL,
    # Exceptions
    ValidationError,
    NotSupported,
)


# =============================================================================
# FIXTURES
# =============================================================================

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
            ops=("eq", "ne", "gt", "gte", "lt", "lte", "in", "and", "or", "not", "exists", "contains"),
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


# =============================================================================
# TEST: ARITY HELPERS
# =============================================================================

class TestArityHelpers:
    """Test arity constant sets and get_expected_arity function."""
    
    def test_arity_3_comparison_operators(self):
        """Comparison operators should have arity 3."""
        for op in ("eq", "ne", "gt", "gte", "lt", "lte", "in"):
            assert op in ARITY_3_COMPARISON
            assert get_expected_arity(op) == 3
    
    def test_arity_2_unary_operators(self):
        """Unary operators should have arity 2."""
        for op in ("exists", "not"):
            assert op in ARITY_2_UNARY
            assert get_expected_arity(op) == 2
    
    def test_arity_3_logical_operators(self):
        """Binary logical operators should have arity 3."""
        for op in ("and", "or"):
            assert op in ARITY_3_LOGICAL
            assert get_expected_arity(op) == 3
    
    def test_unknown_operator_arity(self):
        """Unknown operators should return arity 0."""
        assert get_expected_arity("unknown_op") == 0
        assert get_expected_arity("foobar") == 0
    
    def test_all_known_ops_is_union(self):
        """ALL_KNOWN_OPS should be union of all arity sets."""
        expected = ARITY_2_UNARY | ARITY_3_COMPARISON | ARITY_3_LOGICAL
        assert ALL_KNOWN_OPS == expected


# =============================================================================
# TEST: VALID QUERIES
# =============================================================================

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
        query = QuerySpec(
            where=and_(eq("status", "active"), gt("age", 18))
        )
        result = validate_queryspec(query, full_caps)
        assert result == query
    
    def test_logical_or(self, full_caps: Capabilities):
        """OR with two conditions should pass."""
        query = QuerySpec(
            where=or_(eq("role", "admin"), eq("role", "superuser"))
        )
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
            where=and_(
                or_(eq("type", "user"), eq("type", "admin")),
                not_(eq("banned", True))
            )
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


# =============================================================================
# TEST: ARITY VALIDATION ERRORS
# =============================================================================

class TestArityValidation:
    """Test that incorrect arity raises ValidationError."""
    
    def test_eq_with_too_few_args(self, full_caps: Capabilities):
        """eq with only 2 elements should fail."""
        query = QuerySpec(where=("eq", "name"))  # Missing value
        with pytest.raises(ValidationError, match="requires 3 elements, got 2"):
            validate_queryspec(query, full_caps)
    
    def test_eq_with_too_many_args(self, full_caps: Capabilities):
        """eq with 4 elements should fail."""
        query = QuerySpec(where=("eq", "name", "Alice", "extra"))
        with pytest.raises(ValidationError, match="requires 3 elements, got 4"):
            validate_queryspec(query, full_caps)
    
    def test_and_with_only_one_condition(self, full_caps: Capabilities):
        """and with only one child should fail."""
        query = QuerySpec(where=("and", ("eq", "x", 1)))
        with pytest.raises(ValidationError, match="requires 3 elements, got 2"):
            validate_queryspec(query, full_caps)
    
    def test_or_with_too_few_args(self, full_caps: Capabilities):
        """or with only one child should fail."""
        query = QuerySpec(where=("or", ("eq", "x", 1)))
        with pytest.raises(ValidationError, match="requires 3 elements, got 2"):
            validate_queryspec(query, full_caps)
    
    def test_not_with_too_many_args(self, full_caps: Capabilities):
        """not with 2 conditions should fail."""
        query = QuerySpec(where=("not", ("eq", "x", 1), ("eq", "y", 2)))
        with pytest.raises(ValidationError, match="requires 2 elements, got 3"):
            validate_queryspec(query, full_caps)
    
    def test_exists_with_value(self, full_caps: Capabilities):
        """exists with value argument should fail."""
        query = QuerySpec(where=("exists", "field", True))
        with pytest.raises(ValidationError, match="requires 2 elements, got 3"):
            validate_queryspec(query, full_caps)
    
    def test_empty_where_node(self, full_caps: Capabilities):
        """Empty tuple should fail."""
        query = QuerySpec(where=())
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_queryspec(query, full_caps)


# =============================================================================
# TEST: TYPE VALIDATION ERRORS
# =============================================================================

class TestTypeValidation:
    """Test that incorrect types raise ValidationError."""
    
    def test_where_not_tuple(self, full_caps: Capabilities):
        """where as list should fail."""
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
        """in operator with tuple values should fail (must be list for JSON compatibility)."""
        # Manually construct a tuple-based in node (bypassing the in_ builder)
        query = QuerySpec(where=("in", "status", ("active", "pending")))  # tuple, not list
        with pytest.raises(ValidationError, match="must be a list"):
            validate_queryspec(query, full_caps)

    def test_in_operator_values_as_set_fails(self, full_caps: Capabilities):
        """in operator with set values should fail."""
        query = QuerySpec(where=("in", "status", {"active", "pending"}))  # set, not list
        with pytest.raises(ValidationError, match="must be a list"):
            validate_queryspec(query, full_caps)


# =============================================================================
# TEST: OPERATOR SUPPORT (NotSupported)
# =============================================================================

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
        """Unknown operator with filter disabled should raise ValidationError after NotSupported check."""
        # With filter not supported, validation skips the caps check
        # and goes to arity validation where it fails
        caps = Capabilities(
            query=QueryCapability(supported=True),
            filter=FilterCapability(supported=False),
        )
        query = QuerySpec(where=("foobar", "field", "value"))
        with pytest.raises(NotSupported, match="filtering"):
            validate_queryspec(query, caps)


# =============================================================================
# TEST: CAPABILITY SUPPORT (NotSupported)
# =============================================================================

class TestCapabilitySupport:
    """Test that using unsupported capabilities raises NotSupported."""
    
    def test_query_not_supported(self, minimal_caps: Capabilities):
        """where clause when query not supported should fail."""
        query = QuerySpec(where=("eq", "x", 1))
        with pytest.raises(NotSupported, match="query"):
            validate_queryspec(query, minimal_caps)
    
    def test_projection_not_supported(self, minimal_caps: Capabilities):
        """select when projection not supported should fail."""
        query = QuerySpec(select=["id", "name"])
        with pytest.raises(NotSupported, match="projection"):
            validate_queryspec(query, minimal_caps)
    
    def test_order_by_not_supported(self, minimal_caps: Capabilities):
        """order_by when not supported should fail."""
        query = QuerySpec(order_by=["name"])
        with pytest.raises(NotSupported, match="ordering"):
            validate_queryspec(query, minimal_caps)
    
    def test_pagination_not_supported_limit(self, minimal_caps: Capabilities):
        """limit when pagination not supported should fail."""
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


# =============================================================================
# TEST: FIELD ALLOWLIST VALIDATION
# =============================================================================

class TestFieldAllowlist:
    """Test field allowlist enforcement."""
    
    def test_where_field_not_allowed(self, full_caps: Capabilities):
        """where with disallowed field should fail."""
        query = QuerySpec(where=eq("secret_field", "value"))
        with pytest.raises(ValidationError, match="not in allowed fields"):
            validate_queryspec(
                query, full_caps, 
                allowed_fields={"name", "age", "status"}
            )
    
    def test_where_field_allowed(self, full_caps: Capabilities):
        """where with allowed field should pass."""
        query = QuerySpec(where=eq("name", "Alice"))
        result = validate_queryspec(
            query, full_caps,
            allowed_fields={"name", "age", "status"}
        )
        assert result == query
    
    def test_select_field_not_allowed(self, full_caps: Capabilities):
        """select with disallowed field should fail."""
        query = QuerySpec(select=["id", "secret_field"])
        with pytest.raises(ValidationError, match="not allowed in select"):
            validate_queryspec(
                query, full_caps,
                allowed_select={"id", "name", "email"}
            )
    
    def test_select_field_allowed(self, full_caps: Capabilities):
        """select with allowed fields should pass."""
        query = QuerySpec(select=["id", "name"])
        result = validate_queryspec(
            query, full_caps,
            allowed_select={"id", "name", "email"}
        )
        assert result == query
    
    def test_order_by_field_not_allowed(self, full_caps: Capabilities):
        """order_by with disallowed field should fail."""
        query = QuerySpec(order_by=["secret_field"])
        with pytest.raises(ValidationError, match="not allowed in order_by"):
            validate_queryspec(
                query, full_caps,
                allowed_order_by={"name", "created_at"}
            )
    
    def test_order_by_descending_field_not_allowed(self, full_caps: Capabilities):
        """order_by descending with disallowed field should fail."""
        query = QuerySpec(order_by=["-secret_field"])
        with pytest.raises(ValidationError, match="not allowed in order_by"):
            validate_queryspec(
                query, full_caps,
                allowed_order_by={"name", "created_at"}
            )
    
    def test_order_by_descending_field_allowed(self, full_caps: Capabilities):
        """order_by descending with allowed field should pass."""
        query = QuerySpec(order_by=["-created_at"])
        result = validate_queryspec(
            query, full_caps,
            allowed_order_by={"name", "created_at"}
        )
        assert result == query
    
    def test_exists_field_not_allowed(self, full_caps: Capabilities):
        """exists with disallowed field should fail."""
        query = QuerySpec(where=exists("secret"))
        with pytest.raises(ValidationError, match="not in allowed fields"):
            validate_queryspec(
                query, full_caps,
                allowed_fields={"name", "email"}
            )
    
    def test_nested_where_field_not_allowed(self, full_caps: Capabilities):
        """Nested where with disallowed field should fail."""
        query = QuerySpec(
            where=and_(
                eq("name", "Alice"),
                eq("secret", "value")  # Not allowed
            )
        )
        with pytest.raises(ValidationError, match="not in allowed fields"):
            validate_queryspec(
                query, full_caps,
                allowed_fields={"name", "age"}
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


# =============================================================================
# TEST: MAX_LIMIT CLAMPING
# =============================================================================

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


# =============================================================================
# TEST: EDGE CASES
# =============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_deeply_nested_and_or(self, full_caps: Capabilities):
        """Deeply nested AND/OR should be validated recursively."""
        query = QuerySpec(
            where=and_(
                or_(
                    and_(eq("a", 1), eq("b", 2)),
                    eq("c", 3)
                ),
                not_(
                    or_(eq("d", 4), eq("e", 5))
                )
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
        """contains operator should pass."""
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
            validate_queryspec(
                query, full_caps,
                allowed_fields={"profile", "name"}
            )
        
        # Should pass - allowlist has exact match
        result = validate_queryspec(
            query, full_caps,
            allowed_fields={"profile.status", "name"}
        )
        assert result == query
