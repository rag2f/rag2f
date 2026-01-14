"""XFiles - Repository Protocols (Contracts).

Defines the abstract contracts for repository plugins:
- BaseRepository: Minimum CRUD + capabilities + native escape hatches.
- QueryableRepository: Adds find() with QuerySpec support.
- VectorSearchRepository: Adds vector_search() for embedding-based retrieval.
- GraphTraversalRepository: Adds traverse() for graph-based queries.

All repository implementations should inherit from BaseRepository and
optionally implement the additional interfaces based on their capabilities.
"""

from abc import abstractmethod
from collections.abc import Callable
from typing import (
    Any,
    Protocol,
    TypeVar,
    runtime_checkable,
)

from rag2f.core.xfiles.capabilities import Capabilities
from rag2f.core.xfiles.exceptions import NotSupported
from rag2f.core.xfiles.types import (
    Document,
    DocumentId,
    Patch,
    QuerySpec,
    WhereNode,
)

# Type variable for native handle types
T = TypeVar("T")


# =============================================================================
# BASE REPOSITORY PROTOCOL
# =============================================================================


@runtime_checkable
class BaseRepository(Protocol):
    """Base protocol for all repository implementations.

    This is the minimum contract that all repository plugins must implement.
    It provides:
    - Basic CRUD operations (get, insert, update, delete).
    - Capability declaration (capabilities).
    - Native escape hatches (native, as_native).

    Attributes:
        name: Optional human-readable name for the repository.

    Note:
        - All methods that operate on documents use DocumentId (str | bytes) as identifier.
        - Documents are plain dicts with JSON-like values.
        - Field paths use dot-notation (e.g., "profile.email").
        - The repository does not impose schema validation; that's the plugin's
          or an upper layer's responsibility.
    """

    @property
    def name(self) -> str:
        """Human-readable name for this repository instance."""
        ...

    @abstractmethod
    def capabilities(self) -> Capabilities:
        """Declare the capabilities supported by this repository.

        Returns:
            Capabilities object describing supported features.

        Note:
            This must return accurate information. The capabilities
            guide validation, error handling, and fallback decisions.
        """
        ...

    # =========================================================================
    # CRUD OPERATIONS
    # =========================================================================

    @abstractmethod
    def get(
        self,
        id: DocumentId,
        select: list[str] | None = None,
    ) -> Document:
        """Retrieve a document by its identifier.

        Args:
            id: The document identifier.
            select: Optional projection - list of field paths to return.
                If None, returns all fields.

        Returns:
            The document as a dict.

        Raises:
            NotFound: If the document doesn't exist.
            ValidationError: If select contains invalid fields.
        """
        ...

    @abstractmethod
    def insert(self, id: DocumentId, item: Document) -> None:
        """Insert a new document.

        Args:
            id: The document identifier.
            item: The document data.

        Raises:
            AlreadyExists: If a document with this id already exists.
            ValidationError: If the document data is invalid.
            BackendError: If the backend operation fails.
        """
        ...

    @abstractmethod
    def update(self, id: DocumentId, patch: Patch) -> None:
        """Update an existing document with a partial patch.

        The update semantics are "shallow merge": top-level keys in patch
        are merged into the document. For nested updates, use dot-notation
        keys (if supported by the plugin).

        Args:
            id: The document identifier.
            patch: Partial update data (keys to merge).

        Raises:
            NotFound: If the document doesn't exist.
            ValidationError: If the patch data is invalid.
            BackendError: If the backend operation fails.
        """
        ...

    @abstractmethod
    def delete(self, id: DocumentId) -> None:
        """Delete a document by its identifier.

        Args:
            id: The document identifier.

        Raises:
            NotFound: If the document doesn't exist.
            BackendError: If the backend operation fails.
        """
        ...

    # =========================================================================
    # NATIVE ESCAPE HATCHES
    # =========================================================================

    @abstractmethod
    def _get_native_handle(self, kind: str) -> object:
        """Internal method to retrieve native handle.

        Plugins must implement this method to provide native backend access.
        This is called by native() and as_native() after capability checks.

        Args:
            kind: The kind of native handle to retrieve.

        Returns:
            The native handle object (type depends on backend).

        Raises:
            NotSupported: If the requested kind is not available.

        Note:
            If capabilities().native.supported is True, this method MUST
            be implemented and handle at least the kinds declared in
            capabilities().native.kinds.
        """
        ...


# =============================================================================
# BASE REPOSITORY WITH NATIVE HELPERS (MIXIN)
# =============================================================================


class RepositoryNativeMixin:
    """Mixin providing default implementations for native() and as_native().

    Repository implementations can inherit from this mixin to get the
    standard native escape hatch behavior. Requires:
    - capabilities() method returning Capabilities
    - _get_native_handle(kind) method implementation
    """

    def native(self, kind: str = "primary") -> object:
        """Get the native backend handle for direct access.

        This is an escape hatch for operations not covered by the
        abstract interface. Use with caution as it bypasses the
        repository abstraction.

        Args:
            kind: The kind of native handle to retrieve.
                - "primary": Main driver/client handle (default).
                - Other kinds depend on the plugin (e.g., "session", "tx",
                  "collection", "pipeline").

        Returns:
            The native handle object (type depends on backend).

        Raises:
            NotSupported: If native access is not supported or the
                requested kind is not available.

        Example:
            >>> # Direct access to underlying MongoDB client
            >>> mongo_client = repo.native("primary")
            >>> mongo_client.admin.command("ping")
        """
        caps = self.capabilities()  # type: ignore
        if not caps.native.supported:
            raise NotSupported(
                "native", details="Native access is not supported by this repository"
            )
        if kind not in caps.native.kinds:
            available = ", ".join(caps.native.kinds) or "none"
            raise NotSupported(
                f"native:{kind}",
                details=f"Kind '{kind}' not available. Available kinds: {available}",
            )
        return self._get_native_handle(kind)  # type: ignore

    def as_native(
        self,
        type_or_protocol: type[T] | Callable[[object], bool],
        kind: str = "primary",
    ) -> T:
        """Get the native handle with type checking.

        Like native(), but verifies the returned object is compatible
        with the expected type or protocol. This provides type safety
        when the plugin is selected at runtime.

        Args:
            type_or_protocol: Expected type, runtime_checkable Protocol,
                or callable that returns True if the object is compatible.
            kind: The kind of native handle (default "primary").

        Returns:
            The native handle, typed as T.

        Raises:
            NotSupported: If native access is not supported, the kind
                is not available, or the handle is incompatible with
                the expected type.

        Example:
            >>> from pymongo import MongoClient
            >>> client = repo.as_native(MongoClient)
            >>> # client is now typed as MongoClient

            >>> from typing import Protocol, runtime_checkable
            >>> @runtime_checkable
            ... class Pingable(Protocol):
            ...     def ping(self) -> bool: ...
            >>> client = repo.as_native(Pingable)
        """
        handle = self.native(kind)

        # Check compatibility
        if callable(type_or_protocol) and not isinstance(type_or_protocol, type):
            # It's a callable checker
            if not type_or_protocol(handle):
                raise NotSupported(
                    f"native:{kind}",
                    details=f"Native handle failed compatibility check with {type_or_protocol}",
                )
        elif isinstance(type_or_protocol, type):
            # It's a class or Protocol (potentially runtime_checkable)
            try:
                if not isinstance(handle, type_or_protocol):
                    raise NotSupported(
                        f"native:{kind}",
                        details=(
                            f"Native handle type '{type(handle).__name__}' is not compatible "
                            f"with expected type '{type_or_protocol.__name__}'"
                        ),
                    )
            except TypeError as e:
                # isinstance failed (e.g., non-runtime-checkable Protocol)
                raise NotSupported(
                    f"native:{kind}",
                    details=(
                        f"Cannot verify compatibility with '{type_or_protocol.__name__}'. "
                        "If using a Protocol, add the @runtime_checkable decorator."
                    ),
                ) from e
        else:
            # Fallback: try isinstance anyway
            try:
                if not isinstance(handle, type_or_protocol):  # type: ignore
                    raise NotSupported(
                        f"native:{kind}",
                        details=f"Native handle is not compatible with {type_or_protocol}",
                    )
            except TypeError as e:
                # isinstance failed (e.g., non-runtime-checkable Protocol)
                raise NotSupported(
                    f"native:{kind}",
                    details=(
                        f"Cannot verify compatibility with {type_or_protocol}. "
                        "Use a runtime_checkable Protocol or a type."
                    ),
                ) from e

        return handle  # type: ignore


# =============================================================================
# QUERYABLE REPOSITORY PROTOCOL
# =============================================================================


@runtime_checkable
class QueryableRepository(BaseRepository, Protocol):
    """Repository that supports advanced queries via QuerySpec.

    Extends BaseRepository with the find() method for complex queries
    including projection, filtering, ordering, and pagination.

    Implementations should declare query capability as supported in
    capabilities().query.
    """

    @abstractmethod
    def find(self, query: QuerySpec) -> list[Document]:
        """Find documents matching the query specification.

        Args:
            query: Query specification with select, where, order_by,
                limit, and offset.

        Returns:
            List of matching documents.

        Raises:
            NotSupported: If query capability is not supported.
            ValidationError: If the query contains invalid fields or
                unsupported operators.
            BackendError: If the backend operation fails.

        Example:
            >>> from rag2f.core.xfiles.types import QuerySpec, eq, and_, gt
            >>> query = QuerySpec(
            ...     select=["id", "name", "email"],
            ...     where=and_(eq("status", "active"), gt("age", 18)),
            ...     order_by=["-created_at"],
            ...     limit=10,
            ...     offset=0,
            ... )
            >>> results = repo.find(query)
        """
        ...


# =============================================================================
# VECTOR SEARCH REPOSITORY PROTOCOL
# =============================================================================


@runtime_checkable
class VectorSearchRepository(BaseRepository, Protocol):
    """Repository that supports vector similarity search.

    Extends BaseRepository with vector_search() for embedding-based
    retrieval (e.g., semantic search, RAG retrieval).

    Implementations should declare vector_search capability in
    capabilities().vector_search.
    """

    @abstractmethod
    def vector_search(
        self,
        embedding: list[float],
        top_k: int = 10,
        where: WhereNode | None = None,
        select: list[str] | None = None,
    ) -> list[Document]:
        """Search for documents by vector similarity.

        Args:
            embedding: Query embedding vector.
            top_k: Maximum number of results to return.
            where: Optional filter to apply before/after similarity search.
            select: Optional projection - fields to return.

        Returns:
            List of documents ordered by similarity (most similar first).
            Documents may include a "_score" or "_distance" field.

        Raises:
            NotSupported: If vector search is not supported.
            ValidationError: If embedding dimensions don't match or
                filter is invalid.
            BackendError: If the backend operation fails.

        Example:
            >>> embedding = embedder.embed("search query")
            >>> results = repo.vector_search(
            ...     embedding=embedding,
            ...     top_k=5,
            ...     where=("eq", "category", "documents"),
            ...     select=["id", "title", "content"],
            ... )
        """
        ...


# =============================================================================
# GRAPH TRAVERSAL REPOSITORY PROTOCOL
# =============================================================================


@runtime_checkable
class GraphTraversalRepository(BaseRepository, Protocol):
    """Repository that supports graph traversal queries.

    Extends BaseRepository with traverse() for graph-based queries
    (e.g., find related documents, path queries).

    The traversal spec is a separate AST not compatible with QuerySpec
    because graph semantics differ significantly from document queries.

    Implementations should declare graph_traversal capability in
    capabilities().graph_traversal.
    """

    @abstractmethod
    def traverse(
        self,
        start_id: DocumentId,
        spec: dict[str, Any],
    ) -> Any:
        """Traverse the graph starting from a document.

        Args:
            start_id: Starting node/document identifier.
            spec: Traversal specification (plugin-specific AST).
                Common keys might include:
                - "direction": "outgoing" | "incoming" | "both"
                - "edge_types": List of edge/relation types to follow
                - "max_depth": Maximum traversal depth
                - "filter": Filter for visited nodes
                - "return": What to return ("nodes", "paths", "edges")

        Returns:
            Traversal results (format depends on spec and plugin).

        Raises:
            NotSupported: If graph traversal is not supported.
            NotFound: If start_id doesn't exist.
            ValidationError: If spec is invalid.
            BackendError: If the backend operation fails.

        Example:
            >>> results = repo.traverse(
            ...     start_id="user:123",
            ...     spec={
            ...         "direction": "outgoing",
            ...         "edge_types": ["follows", "likes"],
            ...         "max_depth": 2,
            ...         "return": "nodes",
            ...     },
            ... )
        """
        ...


# =============================================================================
# TYPE ALIASES FOR CONVENIENCE
# =============================================================================

#: Any repository type (for type hints that accept any repository)
AnyRepository = (
    BaseRepository | QueryableRepository | VectorSearchRepository | GraphTraversalRepository
)


__all__ = [
    # Main protocols
    "BaseRepository",
    "QueryableRepository",
    "VectorSearchRepository",
    "GraphTraversalRepository",
    # Mixin for native support
    "RepositoryNativeMixin",
    # Type aliases
    "AnyRepository",
]
