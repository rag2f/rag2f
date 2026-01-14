"""XFiles - Capabilities Declaration System.

Defines the capability structure for repository plugins to declare
what features they support and how (pushdown vs fallback).
"""

from dataclasses import dataclass, field
from typing import Any, Literal

# =============================================================================
# CAPABILITY FEATURE DESCRIPTORS
# =============================================================================


@dataclass(frozen=True, slots=True)
class FeatureSupport:
    """Describes support level for a feature.

    Attributes:
        supported: Whether the feature is available at all.
        pushdown: Whether the feature is executed natively by the backend.
            If False but supported=True, the plugin implements fallback
            (client-side emulation).
    """

    supported: bool = False
    pushdown: bool = False

    def to_dict(self) -> dict[str, bool]:
        """Convert the feature support to a JSON-serializable dictionary.

        Returns:
            A dictionary with "supported" and "pushdown" keys.
        """
        return {"supported": self.supported, "pushdown": self.pushdown}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FeatureSupport":
        """Create a FeatureSupport from a dictionary.

        Args:
            data: A dictionary containing "supported" and "pushdown" keys.

        Returns:
            A FeatureSupport instance.
        """
        return cls(
            supported=data.get("supported", False),
            pushdown=data.get("pushdown", False),
        )


@dataclass(frozen=True, slots=True)
class FilterCapability:
    """Describes filter/where capabilities.

    Attributes:
        supported: Whether filtering is available.
        pushdown: Whether filtering is executed natively.
        ops: List of supported operators (e.g., ["eq", "gt", "in", "and", "or"]).
    """

    supported: bool = False
    pushdown: bool = False
    ops: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        """Convert the filter capability to a JSON-serializable dictionary.

        Returns:
            A dictionary representation of the capability.
        """
        return {
            "supported": self.supported,
            "pushdown": self.pushdown,
            "ops": list(self.ops),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FilterCapability":
        """Create a FilterCapability from a dictionary.

        Args:
            data: A dictionary containing capability fields.

        Returns:
            A FilterCapability instance.
        """
        ops = data.get("ops", [])
        return cls(
            supported=data.get("supported", False),
            pushdown=data.get("pushdown", False),
            ops=tuple(ops) if isinstance(ops, (list, tuple)) else tuple(),
        )


#: Pagination mode type
type PaginationMode = Literal["offset", "cursor", "both"]


@dataclass(frozen=True, slots=True)
class PaginationCapability:
    """Describes pagination capabilities.

    Attributes:
        supported: Whether pagination is available.
        pushdown: Whether pagination is executed natively.
        mode: Pagination mode - "offset", "cursor", or "both".
        max_limit: Maximum allowed limit value (None = no maximum).
    """

    supported: bool = False
    pushdown: bool = False
    mode: PaginationMode = "offset"
    max_limit: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert the pagination capability to a JSON-serializable dictionary.

        Returns:
            A dictionary representation of the capability.
        """
        result: dict[str, Any] = {
            "supported": self.supported,
            "pushdown": self.pushdown,
            "mode": self.mode,
        }
        if self.max_limit is not None:
            result["max_limit"] = self.max_limit
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PaginationCapability":
        """Create a PaginationCapability from a dictionary.

        Args:
            data: A dictionary containing capability fields.

        Returns:
            A PaginationCapability instance.
        """
        return cls(
            supported=data.get("supported", False),
            pushdown=data.get("pushdown", False),
            mode=data.get("mode", "offset"),
            max_limit=data.get("max_limit"),
        )


@dataclass(frozen=True, slots=True)
class NativeCapability:
    """Describes native escape hatch capabilities.

    Attributes:
        supported: Whether native() is available.
        kinds: List of available native handle kinds
            (e.g., ["primary", "session", "tx", "collection"]).
    """

    supported: bool = False
    kinds: tuple[str, ...] = field(default_factory=lambda: ("primary",))

    def to_dict(self) -> dict[str, Any]:
        """Convert the native capability to a JSON-serializable dictionary.

        Returns:
            A dictionary representation of the capability.
        """
        return {
            "supported": self.supported,
            "kinds": list(self.kinds),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NativeCapability":
        """Create a NativeCapability from a dictionary.

        Args:
            data: A dictionary containing capability fields.

        Returns:
            A NativeCapability instance.
        """
        kinds = data.get("kinds", ["primary"])
        return cls(
            supported=data.get("supported", False),
            kinds=tuple(kinds) if isinstance(kinds, (list, tuple)) else ("primary",),
        )


@dataclass(frozen=True, slots=True)
class QueryCapability:
    """Describes general query (find) capability.

    Attributes:
        supported: Whether find() method is available.
    """

    supported: bool = False

    def to_dict(self) -> dict[str, bool]:
        """Convert the query capability to a JSON-serializable dictionary.

        Returns:
            A dictionary representation of the capability.
        """
        return {"supported": self.supported}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QueryCapability":
        """Create a QueryCapability from a dictionary.

        Args:
            data: A dictionary containing capability fields.

        Returns:
            A QueryCapability instance.
        """
        return cls(supported=data.get("supported", False))


@dataclass(frozen=True, slots=True)
class UpdateCapability:
    """Describes update operation capabilities.

    Attributes:
        dot_notation: Whether dot-notation keys are supported in patches
            (e.g., {"profile.age": 30} updates nested field).
        deep_merge: Whether update performs deep merge vs shallow merge.
            If False, only top-level keys are merged.
        atomic_ops: Supported atomic update operators (e.g., ["$inc", "$push"]
            for MongoDB-style updates). Empty tuple if not supported.
    """

    dot_notation: bool = False
    deep_merge: bool = False
    atomic_ops: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        """Convert the update capability to a JSON-serializable dictionary.

        Returns:
            A dictionary representation of the capability.
        """
        return {
            "dot_notation": self.dot_notation,
            "deep_merge": self.deep_merge,
            "atomic_ops": list(self.atomic_ops),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UpdateCapability":
        """Create an UpdateCapability from a dictionary.

        Args:
            data: A dictionary containing capability fields.

        Returns:
            An UpdateCapability instance.
        """
        ops = data.get("atomic_ops", [])
        return cls(
            dot_notation=data.get("dot_notation", False),
            deep_merge=data.get("deep_merge", False),
            atomic_ops=tuple(ops) if isinstance(ops, (list, tuple)) else tuple(),
        )


@dataclass(frozen=True, slots=True)
class VectorSearchCapability:
    """Describes vector search capabilities.

    Attributes:
        supported: Whether vector_search() is available.
        dimensions: Expected embedding dimensions (None = any).
        distance_metrics: Supported distance metrics (e.g., ["cosine", "euclidean"]).
    """

    supported: bool = False
    dimensions: int | None = None
    distance_metrics: tuple[str, ...] = field(default_factory=lambda: ("cosine",))

    def to_dict(self) -> dict[str, Any]:
        """Convert the vector search capability to a JSON-serializable dictionary.

        Returns:
            A dictionary representation of the capability.
        """
        result: dict[str, Any] = {"supported": self.supported}
        if self.dimensions is not None:
            result["dimensions"] = self.dimensions
        result["distance_metrics"] = list(self.distance_metrics)
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VectorSearchCapability":
        """Create a VectorSearchCapability from a dictionary.

        Args:
            data: A dictionary containing capability fields.

        Returns:
            A VectorSearchCapability instance.
        """
        metrics = data.get("distance_metrics", ["cosine"])
        return cls(
            supported=data.get("supported", False),
            dimensions=data.get("dimensions"),
            distance_metrics=tuple(metrics) if isinstance(metrics, (list, tuple)) else ("cosine",),
        )


@dataclass(frozen=True, slots=True)
class GraphTraversalCapability:
    """Describes graph traversal capabilities.

    Attributes:
        supported: Whether traverse() is available.
        max_depth: Maximum traversal depth (None = no limit).
    """

    supported: bool = False
    max_depth: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert the graph traversal capability to a JSON-serializable dictionary.

        Returns:
            A dictionary representation of the capability.
        """
        result: dict[str, Any] = {"supported": self.supported}
        if self.max_depth is not None:
            result["max_depth"] = self.max_depth
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GraphTraversalCapability":
        """Create a GraphTraversalCapability from a dictionary.

        Args:
            data: A dictionary containing capability fields.

        Returns:
            A GraphTraversalCapability instance.
        """
        return cls(
            supported=data.get("supported", False),
            max_depth=data.get("max_depth"),
        )


# =============================================================================
# MAIN CAPABILITIES CLASS
# =============================================================================


@dataclass(frozen=True, slots=True)
class Capabilities:
    """Complete capability declaration for a repository plugin.

    This structure describes what a repository supports and how.
    Plugins must provide accurate capabilities to enable:
    - Validation of incoming queries.
    - Fail-fast behavior for unsupported operations.
    - Client-side fallback decisions.

    Attributes:
        crud: Whether basic CRUD operations are supported (usually True).
        query: General query (find) capability.
        projection: Projection/select capability.
        filter: Filter/where capability with supported operators.
        order_by: Ordering capability.
        pagination: Pagination capability with mode and limits.
        update: Update operation capability (dot-notation, merge semantics, atomic ops).
        native: Native escape hatch capability.
        vector_search: Vector search capability (optional interface).
        graph_traversal: Graph traversal capability (optional interface).
        extra: Additional plugin-specific capabilities.

    Example:
        >>> caps = Capabilities(
        ...     crud=True,
        ...     query=QueryCapability(supported=True),
        ...     projection=FeatureSupport(supported=True, pushdown=True),
        ...     filter=FilterCapability(
        ...         supported=True,
        ...         pushdown=True,
        ...         ops=("eq", "gt", "lt", "in", "and", "or"),
        ...     ),
        ...     pagination=PaginationCapability(
        ...         supported=True,
        ...         pushdown=True,
        ...         mode="offset",
        ...         max_limit=1000,
        ...     ),
        ... )
    """

    crud: bool = True
    query: QueryCapability = field(default_factory=QueryCapability)
    projection: FeatureSupport = field(default_factory=FeatureSupport)
    filter: FilterCapability = field(default_factory=FilterCapability)
    order_by: FeatureSupport = field(default_factory=FeatureSupport)
    pagination: PaginationCapability = field(default_factory=PaginationCapability)
    update: UpdateCapability = field(default_factory=UpdateCapability)
    native: NativeCapability = field(default_factory=NativeCapability)
    vector_search: VectorSearchCapability = field(default_factory=VectorSearchCapability)
    graph_traversal: GraphTraversalCapability = field(default_factory=GraphTraversalCapability)
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert capabilities to dictionary representation."""
        result: dict[str, Any] = {
            "crud": self.crud,
            "query": self.query.to_dict(),
            "projection": self.projection.to_dict(),
            "filter": self.filter.to_dict(),
            "order_by": self.order_by.to_dict(),
            "pagination": self.pagination.to_dict(),
            "update": self.update.to_dict(),
            "native": self.native.to_dict(),
            "vector_search": self.vector_search.to_dict(),
            "graph_traversal": self.graph_traversal.to_dict(),
        }
        if self.extra:
            result["extra"] = self.extra
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Capabilities":
        """Create Capabilities from dictionary representation."""
        return cls(
            crud=data.get("crud", True),
            query=QueryCapability.from_dict(data.get("query", {})),
            projection=FeatureSupport.from_dict(data.get("projection", {})),
            filter=FilterCapability.from_dict(data.get("filter", {})),
            order_by=FeatureSupport.from_dict(data.get("order_by", {})),
            pagination=PaginationCapability.from_dict(data.get("pagination", {})),
            update=UpdateCapability.from_dict(data.get("update", {})),
            native=NativeCapability.from_dict(data.get("native", {})),
            vector_search=VectorSearchCapability.from_dict(data.get("vector_search", {})),
            graph_traversal=GraphTraversalCapability.from_dict(data.get("graph_traversal", {})),
            extra=data.get("extra", {}),
        )

    def supports_operator(self, op: str) -> bool:
        """Check if a filter operator is supported.

        Args:
            op: Operator name (e.g., "eq", "gt", "and").

        Returns:
            True if the operator is in the supported ops list.
        """
        return self.filter.supported and op in self.filter.ops

    def supports_native_kind(self, kind: str) -> bool:
        """Check if a native handle kind is supported.

        Args:
            kind: Native handle kind (e.g., "primary", "session").

        Returns:
            True if the kind is available.
        """
        return self.native.supported and kind in self.native.kinds


# =============================================================================
# FACTORY HELPERS
# =============================================================================


def minimal_crud_capabilities() -> Capabilities:
    """Create minimal capabilities for a CRUD-only repository.

    Returns:
        Capabilities with only CRUD enabled.
    """
    return Capabilities(crud=True)


def standard_queryable_capabilities(
    filter_ops: tuple[str, ...] = ("eq", "ne", "gt", "gte", "lt", "lte", "in", "and", "or", "not"),
    max_limit: int = 1000,
    pushdown: bool = False,
) -> Capabilities:
    """Create standard capabilities for a queryable repository.

    Conservative default: pushdown=False (client-side execution).
    SQL-like plugins should set pushdown=True for native execution.

    Args:
        filter_ops: Supported filter operators.
        max_limit: Maximum allowed limit for pagination.
        pushdown: Whether features are executed natively (default False).
            If True, all query features use backend-native execution.
            If False, features may use client-side fallback.

    Returns:
        Capabilities with CRUD, query, projection, filter, order_by, pagination.
    """
    return Capabilities(
        crud=True,
        query=QueryCapability(supported=True),
        projection=FeatureSupport(supported=True, pushdown=pushdown),
        filter=FilterCapability(supported=True, pushdown=pushdown, ops=filter_ops),
        order_by=FeatureSupport(supported=True, pushdown=pushdown),
        pagination=PaginationCapability(
            supported=True,
            pushdown=pushdown,
            mode="offset",
            max_limit=max_limit,
        ),
        native=NativeCapability(supported=True, kinds=("primary",)),
    )


__all__ = [
    # Feature descriptors
    "FeatureSupport",
    "FilterCapability",
    "PaginationCapability",
    "NativeCapability",
    "QueryCapability",
    "UpdateCapability",
    "VectorSearchCapability",
    "GraphTraversalCapability",
    # Main class
    "Capabilities",
    # Type aliases
    "PaginationMode",
    # Factory helpers
    "minimal_crud_capabilities",
    "standard_queryable_capabilities",
]
