"""XFiles - QuerySpec Validation Module.

Provides centralized validation for QuerySpec objects, ensuring:
- WhereNode arity (correct number of arguments per operator)
- Operator support based on Capabilities
- Field allowlisting for select/order_by
- Pagination limit enforcement

This module catches invalid queries early, preventing silent bugs and
ensuring consistent behavior across different repository plugins.
"""

from rag2f.core.xfiles.capabilities import Capabilities
from rag2f.core.xfiles.exceptions import NotSupported, ValidationError
from rag2f.core.xfiles.types import QuerySpec, WhereNode

# =============================================================================
# OPERATOR ARITY DEFINITIONS
# =============================================================================

# Operators with arity 3: (op, field, value)
ARITY_3_COMPARISON: frozenset[str] = frozenset(
    {
        "eq",
        "ne",
        "gt",
        "gte",
        "lt",
        "lte",
        "in",
        "contains",
        "startswith",
        "endswith",
        "regex",
        "fulltext",
        "near",
        "within",
    }
)

# Operators with arity 2: (op, field) or (op, condition)
ARITY_2_UNARY: frozenset[str] = frozenset(
    {
        "exists",  # (exists, field)
        "not",  # (not, condition)
    }
)

# Operators with arity 3 (binary logical): (op, left, right)
ARITY_3_LOGICAL: frozenset[str] = frozenset(
    {
        "and",
        "or",
    }
)

# All known operators for reference
ALL_KNOWN_OPS: frozenset[str] = ARITY_3_COMPARISON | ARITY_2_UNARY | ARITY_3_LOGICAL


def get_expected_arity(op: str) -> int:
    """Get the expected arity (tuple length) for an operator.

    Args:
        op: Operator name.

    Returns:
        Expected tuple length (including the operator itself).
        Returns 0 if operator is unknown.
    """
    if op in ARITY_3_COMPARISON or op in ARITY_3_LOGICAL:
        return 3
    if op in ARITY_2_UNARY:
        return 2
    return 0  # Unknown operator


# =============================================================================
# WHERE NODE VALIDATION
# =============================================================================


def _validate_where_node(
    node: WhereNode,
    caps: Capabilities,
    allowed_fields: set[str] | None = None,
    path: str = "where",
) -> None:
    """Recursively validate a WhereNode AST.

    Args:
        node: WhereNode tuple to validate.
        caps: Repository capabilities.
        allowed_fields: Optional set of allowed field names. If None, all fields allowed.
        path: Current path in AST for error messages.

    Raises:
        ValidationError: If node structure is invalid (wrong arity, invalid type).
        NotSupported: If operator is not supported by capabilities.
    """
    # Check basic tuple structure
    if not isinstance(node, tuple):
        raise ValidationError(
            f"WhereNode must be a tuple, got {type(node).__name__}",
            field=path,
            value=node,
        )

    if len(node) == 0:
        raise ValidationError(
            "WhereNode cannot be empty",
            field=path,
            value=node,
        )

    op = node[0]

    # Check operator is a string
    if not isinstance(op, str):
        raise ValidationError(
            f"Operator must be a string, got {type(op).__name__}",
            field=f"{path}[0]",
            value=op,
        )

    # Check operator is supported by capabilities
    if caps.filter.supported and op not in caps.filter.ops:
        raise NotSupported(
            feature=f"filter operator '{op}'",
            details=f"Supported operators: {', '.join(caps.filter.ops)}",
        )

    # Check arity
    expected_arity = get_expected_arity(op)
    if expected_arity == 0:
        raise ValidationError(
            f"Unknown operator '{op}'",
            field=path,
            value=node,
        )

    actual_arity = len(node)
    if actual_arity != expected_arity:
        raise ValidationError(
            f"Operator '{op}' requires {expected_arity} elements, got {actual_arity}",
            field=path,
            value=node,
        )

    # Validate based on operator type
    if op in ARITY_3_COMPARISON:
        # Format: (op, field, value)
        field_name = node[1]
        if not isinstance(field_name, str):
            raise ValidationError(
                f"Field name must be a string, got {type(field_name).__name__}",
                field=f"{path}[1]",
                value=field_name,
            )

        # Check field allowlist
        if allowed_fields is not None and field_name not in allowed_fields:
            raise ValidationError(
                f"Field '{field_name}' is not in allowed fields",
                field=f"{path}[1]",
                value=field_name,
            )

        # Validate 'in' operator: values must be a list (canonical form)
        if op == "in":
            values = node[2]
            if not isinstance(values, list):
                raise ValidationError(
                    f"'in' operator values must be a list, got {type(values).__name__}. "
                    "Use the in_() builder or provide a list for JSON compatibility.",
                    field=f"{path}[2]",
                    value=values,
                )
        # Other comparison operators: value can be any type

    elif op == "exists":
        # Format: (exists, field)
        field_name = node[1]
        if not isinstance(field_name, str):
            raise ValidationError(
                f"Field name must be a string, got {type(field_name).__name__}",
                field=f"{path}[1]",
                value=field_name,
            )

        if allowed_fields is not None and field_name not in allowed_fields:
            raise ValidationError(
                f"Field '{field_name}' is not in allowed fields",
                field=f"{path}[1]",
                value=field_name,
            )

    elif op == "not":
        # Format: (not, condition)
        condition = node[1]
        _validate_where_node(condition, caps, allowed_fields, f"{path}.not")

    elif op in ARITY_3_LOGICAL:
        # Format: (and/or, left, right)
        left = node[1]
        right = node[2]
        _validate_where_node(left, caps, allowed_fields, f"{path}.{op}.left")
        _validate_where_node(right, caps, allowed_fields, f"{path}.{op}.right")


# =============================================================================
# MAIN VALIDATION FUNCTION
# =============================================================================


def validate_queryspec(
    query: QuerySpec,
    caps: Capabilities,
    *,
    allowed_fields: set[str] | None = None,
    allowed_select: set[str] | None = None,
    allowed_order_by: set[str] | None = None,
) -> QuerySpec:
    """Validate a QuerySpec against repository capabilities and field allowlists.

    This function performs comprehensive validation:
    1. Verifies arity for each operator in the where clause.
    2. Verifies that operators are in caps.filter.ops if filtering is supported.
    3. Verifies that select fields are in the allowed set.
    4. Verifies that order_by fields are in the allowed set.
    5. Applies max_limit from pagination capabilities when defined.

    Args:
        query: QuerySpec to validate.
        caps: Repository capabilities to validate against.
        allowed_fields: Optional set of allowed field names for where clause.
            If None, all fields are allowed.
        allowed_select: Optional set of allowed field names for select.
            If None, all fields are allowed.
        allowed_order_by: Optional set of allowed field names for order_by.
            If None, all fields are allowed.

    Returns:
        QuerySpec, potentially modified (e.g., limit clamped to max_limit).

    Raises:
        ValidationError: If query structure is invalid.
        NotSupported: If query uses unsupported capabilities.

    Example:
        >>> from rag2f.core.xfiles import (
        ...     validate_queryspec, QuerySpec, eq, Capabilities, FilterCapability
        ... )
        >>>
        >>> caps = Capabilities(
        ...     filter=FilterCapability(supported=True, ops=("eq", "gt", "and")),
        ... )
        >>> query = QuerySpec(where=("eq", "name", "Alice"), limit=100)
        >>> validated = validate_queryspec(query, caps)
    """
    # Start with original query values
    result_limit = query.limit

    # ---------------------------------------------------------------------------
    # Validate query capability
    # ---------------------------------------------------------------------------
    if query.where is not None and not caps.query.supported:
        raise NotSupported(
            feature="query",
            details="Repository does not support queries (find operations)",
        )

    # ---------------------------------------------------------------------------
    # Validate projection (select)
    # ---------------------------------------------------------------------------
    if query.select is not None:
        if not caps.projection.supported:
            raise NotSupported(
                feature="projection",
                details="Repository does not support field projection (select)",
            )

        for i, field in enumerate(query.select):
            if not isinstance(field, str):
                raise ValidationError(
                    f"Select field must be a string, got {type(field).__name__}",
                    field=f"select[{i}]",
                    value=field,
                )

            if allowed_select is not None and field not in allowed_select:
                raise ValidationError(
                    f"Field '{field}' is not allowed in select",
                    field=f"select[{i}]",
                    value=field,
                )

    # ---------------------------------------------------------------------------
    # Validate filtering (where)
    # ---------------------------------------------------------------------------
    if query.where is not None:
        if not caps.filter.supported:
            raise NotSupported(
                feature="filtering",
                details="Repository does not support filtering (where clause)",
            )

        _validate_where_node(query.where, caps, allowed_fields, "where")

    # ---------------------------------------------------------------------------
    # Validate ordering (order_by)
    # ---------------------------------------------------------------------------
    if query.order_by is not None:
        if not caps.order_by.supported:
            raise NotSupported(
                feature="ordering",
                details="Repository does not support ordering (order_by)",
            )

        for i, order_field in enumerate(query.order_by):
            if not isinstance(order_field, str):
                raise ValidationError(
                    f"Order field must be a string, got {type(order_field).__name__}",
                    field=f"order_by[{i}]",
                    value=order_field,
                )

            # Strip leading "-" for descending order check
            field_name = order_field.lstrip("-")

            if allowed_order_by is not None and field_name not in allowed_order_by:
                raise ValidationError(
                    f"Field '{field_name}' is not allowed in order_by",
                    field=f"order_by[{i}]",
                    value=order_field,
                )

    # ---------------------------------------------------------------------------
    # Validate pagination
    # ---------------------------------------------------------------------------
    if (query.limit is not None or query.offset != 0) and not caps.pagination.supported:
        raise NotSupported(
            feature="pagination",
            details="Repository does not support pagination",
        )

    # Validate limit
    if query.limit is not None:
        if not isinstance(query.limit, int):
            raise ValidationError(
                f"Limit must be an integer, got {type(query.limit).__name__}",
                field="limit",
                value=query.limit,
            )

        if query.limit < 0:
            raise ValidationError(
                "Limit must be non-negative",
                field="limit",
                value=query.limit,
            )

        # Apply max_limit from capabilities
        if caps.pagination.max_limit is not None:
            result_limit = min(query.limit, caps.pagination.max_limit)

    # Validate offset
    if not isinstance(query.offset, int):
        raise ValidationError(
            f"Offset must be an integer, got {type(query.offset).__name__}",
            field="offset",
            value=query.offset,
        )

    if query.offset < 0:
        raise ValidationError(
            "Offset must be non-negative",
            field="offset",
            value=query.offset,
        )

    # ---------------------------------------------------------------------------
    # Return validated (possibly modified) QuerySpec
    # ---------------------------------------------------------------------------
    if result_limit != query.limit:
        # Return new QuerySpec with clamped limit
        return QuerySpec(
            select=query.select,
            where=query.where,
            order_by=query.order_by,
            limit=result_limit,
            offset=query.offset,
        )

    return query


__all__ = [
    "validate_queryspec",
    "get_expected_arity",
    "ALL_KNOWN_OPS",
    "ARITY_2_UNARY",
    "ARITY_3_COMPARISON",
    "ARITY_3_LOGICAL",
]
