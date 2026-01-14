"""XFiles - Types and Data Transfer Objects.

Defines the core type aliases and structures for repository operations:
- Document: The base document type (dict with JSON-like values).
- QuerySpec: Query specification with projection, filter, ordering, pagination.
- WhereNode: AST for filter expressions in prefix form.
"""

from dataclasses import dataclass
from typing import (
    Any,
    Literal,
)

# =============================================================================
# BASE TYPE ALIASES
# =============================================================================

#: Document identifier type: string or bytes
type DocumentId = str | bytes

#: Document type: dict with JSON-like values.
#: Keys are strings, values can be any JSON-serializable type.
#: Field paths use dot-notation: "profile.age", "address.city".
type Document = dict[str, Any]

#: Patch type for partial updates (shallow merge semantics).
type Patch = dict[str, Any]


# =============================================================================
# WHERE NODE (FILTER AST) - PREFIX FORM
# =============================================================================

#: Core comparison operators (minimum common denominator)
type CoreComparisonOp = Literal["eq", "ne", "gt", "gte", "lt", "lte", "in"]

#: Logical operators for combining conditions
type LogicalOp = Literal["and", "or", "not"]

#: Extended string operators (optional, declared via capabilities)
type StringOp = Literal["contains", "startswith", "endswith", "regex"]

#: Other extended operators (optional, declared via capabilities)
type ExtendedOp = Literal["exists", "fulltext", "near", "within"]

#: All supported operator types
type WhereOp = CoreComparisonOp | LogicalOp | StringOp | ExtendedOp


# WhereNode AST types (prefix/tuple form for easy serialization)
# Format: (operator, ...args)
# Examples:
#   ("eq", "name", "Alice")
#   ("gt", "age", 18)
#   ("in", "status", ["active", "pending"])
#   ("and", ("eq", "type", "user"), ("gt", "age", 21))
#   ("or", ("eq", "role", "admin"), ("eq", "role", "superuser"))
#   ("not", ("eq", "deleted", True))

#: WhereNode is a recursive tuple structure representing filter AST.
#: Using forward reference string for recursive type.
type WhereNode = tuple[str, ...]


# =============================================================================
# QUERY SPEC - FULL QUERY SPECIFICATION
# =============================================================================


@dataclass(frozen=True, slots=True)
class QuerySpec:
    """Query specification for repository find operations.

    All fields except offset are optional. This provides a "plain" structure
    that's easy to serialize and represents the common query language.

    Attributes:
        select: Optional projection - list of field paths to return.
            If None, returns all fields.
            Example: ["id", "name", "profile.email"]

        where: Optional filter AST in prefix tuple form.
            Example: ("and", ("eq", "status", "active"), ("gt", "age", 18))

        order_by: Optional ordering - list of field paths with optional "-" prefix
            for descending order.
            Example: ["-created_at", "name"] (created_at DESC, name ASC)

        limit: Optional maximum number of results to return.
            None means no limit (backend default applies).

        offset: Starting position for pagination (default 0).

    Note:
        QuerySpec is the "internal common language" for queries.
        External formats (OData strings, JSON, etc.) should be converted
        to QuerySpec before being passed to repository methods.
    """

    select: list[str] | None = None
    where: WhereNode | None = None
    order_by: list[str] | None = None
    limit: int | None = None
    offset: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation.

        Returns:
            Dict with non-None values only (except offset which is always included).
        """
        result: dict[str, Any] = {"offset": self.offset}
        if self.select is not None:
            result["select"] = self.select
        if self.where is not None:
            result["where"] = self.where
        if self.order_by is not None:
            result["order_by"] = self.order_by
        if self.limit is not None:
            result["limit"] = self.limit
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QuerySpec":
        """Create QuerySpec from dictionary.

        Args:
            data: Dictionary with query specification fields.

        Returns:
            QuerySpec instance.
        """
        return cls(
            select=data.get("select"),
            where=data.get("where"),
            order_by=data.get("order_by"),
            limit=data.get("limit"),
            offset=data.get("offset", 0),
        )


# =============================================================================
# HELPER FUNCTIONS FOR BUILDING WHERE NODES
# =============================================================================


def eq(field: str, value: Any) -> WhereNode:
    """Create an equality condition: field == value."""
    return ("eq", field, value)


def ne(field: str, value: Any) -> WhereNode:
    """Create a not-equal condition: field != value."""
    return ("ne", field, value)


def gt(field: str, value: Any) -> WhereNode:
    """Create a greater-than condition: field > value."""
    return ("gt", field, value)


def gte(field: str, value: Any) -> WhereNode:
    """Create a greater-than-or-equal condition: field >= value."""
    return ("gte", field, value)


def lt(field: str, value: Any) -> WhereNode:
    """Create a less-than condition: field < value."""
    return ("lt", field, value)


def lte(field: str, value: Any) -> WhereNode:
    """Create a less-than-or-equal condition: field <= value."""
    return ("lte", field, value)


def in_(field: str, values: list[Any]) -> WhereNode:
    """Create an 'in' condition: field in [values].

    Args:
        field: Field name to match.
        values: List of values to match against. Always stored as a list
            for JSON serialization compatibility.

    Returns:
        WhereNode tuple: ("in", field, [values]).
    """
    return ("in", field, list(values))


def and_(*conditions: WhereNode) -> WhereNode:
    """Combine conditions with AND.

    Args:
        *conditions: Two or more WhereNode conditions.

    Returns:
        Combined WhereNode with AND logic.
    """
    if len(conditions) < 2:
        raise ValueError("and_ requires at least 2 conditions")
    result = conditions[0]
    for cond in conditions[1:]:
        result = ("and", result, cond)
    return result


def or_(*conditions: WhereNode) -> WhereNode:
    """Combine conditions with OR.

    Args:
        *conditions: Two or more WhereNode conditions.

    Returns:
        Combined WhereNode with OR logic.
    """
    if len(conditions) < 2:
        raise ValueError("or_ requires at least 2 conditions")
    result = conditions[0]
    for cond in conditions[1:]:
        result = ("or", result, cond)
    return result


def not_(condition: WhereNode) -> WhereNode:
    """Negate a condition.

    Args:
        condition: WhereNode to negate.

    Returns:
        Negated WhereNode.
    """
    return ("not", condition)


def exists(field: str) -> WhereNode:
    """Check if field exists."""
    return ("exists", field)


def contains(field: str, value: str) -> WhereNode:
    """Check if field contains substring."""
    return ("contains", field, value)


def startswith(field: str, value: str) -> WhereNode:
    """Check if field starts with prefix."""
    return ("startswith", field, value)


def endswith(field: str, value: str) -> WhereNode:
    """Check if field ends with suffix."""
    return ("endswith", field, value)


def fulltext(field: str, query: str) -> WhereNode:
    """Full-text search on field."""
    return ("fulltext", field, query)


__all__ = [
    # Type aliases
    "DocumentId",
    "Document",
    "Patch",
    "WhereOp",
    "WhereNode",
    # Dataclasses
    "QuerySpec",
    # Builder functions
    "eq",
    "ne",
    "gt",
    "gte",
    "lt",
    "lte",
    "in_",
    "and_",
    "or_",
    "not_",
    "exists",
    "contains",
    "startswith",
    "endswith",
    "fulltext",
]
