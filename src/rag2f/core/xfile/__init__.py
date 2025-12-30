"""XFile - Pluggable Repository Manager for RAG2F.

XFile provides a unified interface for managing heterogeneous repository plugins,
supporting CRUD operations, advanced queries via QuerySpec, capabilities declaration,
and native escape hatches for backend-specific operations.

Named after The X-Files - "The truth is out there."

Main Components
---------------
- **XFile**: Repository plugin manager (register, get, search by ID/meta).
- **BaseRepository**: Minimum contract for all repository plugins (CRUD + native).
- **QueryableRepository**: Extension for advanced queries with QuerySpec.
- **VectorSearchRepository**: Extension for embedding-based retrieval.
- **GraphTraversalRepository**: Extension for graph-based queries.
- **QuerySpec**: Query AST for projection, filtering, ordering, pagination.
- **Capabilities**: Declares what features a repository supports.

Quick Start
-----------
    >>> from rag2f.core.xfile import XFile, QuerySpec, eq, and_
    >>> 
    >>> # Create manager
    >>> xfile = XFile()
    >>> 
    >>> # Register repositories with metadata
    >>> xfile.register("users", my_repo, meta={"type": "mongodb", "domain": "users"})
    >>> 
    >>> # Get repository by ID
    >>> repo = xfile.get("users")
    >>> 
    >>> # Search by metadata
    >>> mongo_repos = xfile.search(lambda m: m.get("type") == "mongodb")
    >>> 
    >>> # Build and execute queries (if repository is QueryableRepository)
    >>> query = QuerySpec(
    ...     select=["id", "name", "email"],
    ...     where=and_(eq("status", "active"), eq("role", "admin")),
    ...     order_by=["-created_at"],
    ...     limit=10,
    ... )
    >>> # results = repo.find(query)  # if repo supports queries

Exception Hierarchy
-------------------
- **RepositoryError**: Base for all repository exceptions.
- **NotFound**: Document not found.
- **AlreadyExists**: Document ID already exists.
- **NotSupported**: Feature/operation not supported.
- **ValidationError**: Input validation failed.
- **BackendError**: Underlying backend operation failed.

Query DSL Helpers
-----------------
Helper functions for building WhereNode AST:
    eq, ne, gt, gte, lt, lte, in_, and_, or_, not_,
    exists, contains, startswith, endswith, fulltext
"""

# =============================================================================
# EXCEPTIONS
# =============================================================================
from rag2f.core.xfile.exceptions import (
    RepositoryError,
    NotFound,
    AlreadyExists,
    NotSupported,
    ValidationError,
    BackendError,
)

# =============================================================================
# TYPES AND DTOs
# =============================================================================
from rag2f.core.xfile.types import (
    # Type aliases
    DocumentId,
    Document,
    Patch,
    WhereOp,
    WhereNode,
    # Dataclasses
    QuerySpec,
    # Builder functions
    eq,
    ne,
    gt,
    gte,
    lt,
    lte,
    in_,
    and_,
    or_,
    not_,
    exists,
    contains,
    startswith,
    endswith,
    fulltext,
)

# =============================================================================
# CAPABILITIES
# =============================================================================
from rag2f.core.xfile.capabilities import (
    # Feature descriptors
    FeatureSupport,
    FilterCapability,
    PaginationCapability,
    NativeCapability,
    QueryCapability,
    UpdateCapability,
    VectorSearchCapability,
    GraphTraversalCapability,
    # Main class
    Capabilities,
    # Type aliases
    PaginationMode,
    # Factory helpers
    minimal_crud_capabilities,
    standard_queryable_capabilities,
)

# =============================================================================
# VALIDATION
# =============================================================================
from rag2f.core.xfile.validation import (
    validate_queryspec,
    get_expected_arity,
    ALL_KNOWN_OPS,
    ARITY_2_UNARY,
    ARITY_3_COMPARISON,
    ARITY_3_LOGICAL,
)

# =============================================================================
# REPOSITORY PROTOCOLS
# =============================================================================
from rag2f.core.xfile.repository import (
    BaseRepository,
    QueryableRepository,
    VectorSearchRepository,
    GraphTraversalRepository,
    RepositoryNativeMixin,
    AnyRepository,
)

# =============================================================================
# MANAGER
# =============================================================================
from rag2f.core.xfile.xfile import (
    XFile,
    RepositoryManager,
    RepositoryEntry,
)


__all__ = [
    # Manager
    "XFile",
    "RepositoryManager",
    "RepositoryEntry",
    # Repository protocols
    "BaseRepository",
    "QueryableRepository",
    "VectorSearchRepository",
    "GraphTraversalRepository",
    "RepositoryNativeMixin",
    "AnyRepository",
    # Exceptions
    "RepositoryError",
    "NotFound",
    "AlreadyExists",
    "NotSupported",
    "ValidationError",
    "BackendError",
    # Types
    "DocumentId",
    "Document",
    "Patch",
    "WhereOp",
    "WhereNode",
    "QuerySpec",
    # Query builders
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
    # Capabilities
    "FeatureSupport",
    "FilterCapability",
    "PaginationCapability",
    "NativeCapability",
    "QueryCapability",
    "UpdateCapability",
    "VectorSearchCapability",
    "GraphTraversalCapability",
    "Capabilities",
    "PaginationMode",
    "minimal_crud_capabilities",
    "standard_queryable_capabilities",
    # Validation
    "validate_queryspec",
    "get_expected_arity",
    "ALL_KNOWN_OPS",
    "ARITY_2_UNARY",
    "ARITY_3_COMPARISON",
    "ARITY_3_LOGICAL",
]
