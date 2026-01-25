"""XFiles - Repository Plugin Manager.

XFiles manages a registry of pluggable repositories, providing a centralized
interface for registering, retrieving by ID, and querying repositories
by metadata.

Named after The X-Files, this class manages the mysterious and varied
collection of data repositories within RAG2F - "The truth is out there."
"""

import logging
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import (
    TYPE_CHECKING,
    Any,
    Optional,
    TypeVar,
)

from rag2f.core.dto.result_dto import StatusCode, StatusDetail
from rag2f.core.dto.xfiles_dto import GetResult, RegisterResult, SearchRepoResult
from rag2f.core.xfiles.capabilities import Capabilities
from rag2f.core.xfiles.repository import (
    BaseRepository,
)

if TYPE_CHECKING:
    from rag2f.core.spock.spock import Spock


logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseRepository)


# =============================================================================
# REPOSITORY ENTRY (INTERNAL)
# =============================================================================


@dataclass(slots=True)
class RepositoryEntry:
    """Internal entry for registered repositories.

    Stores the repository instance along with its registration metadata.

    Attributes:
        id: Unique identifier for this repository registration.
        repository: The repository instance.
        meta: Arbitrary metadata for searching/filtering.
    """

    id: str
    repository: BaseRepository
    meta: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# XFILE - REPOSITORY PLUGIN MANAGER
# =============================================================================


class XFiles:
    """Repository plugin manager for RAG2F instances.

    XFiles manages a collection of heterogeneous repository plugins,
    providing:
    - Registration with unique IDs and metadata.
    - Lookup by ID.
    - Search by metadata predicates.
    - Iteration over registered repositories.

    Each RAG2F instance has its own XFiles instance to maintain
    isolated repository registry state.

    Famous quote from The X-Files:
    "The truth is out there."

    Example:
        >>> xfiles = XFiles()
        >>> xfiles.register("users_db", mongo_repo, meta={"type": "mongodb", "domain": "users"})
        >>> xfiles.register("cache", redis_repo, meta={"type": "redis", "purpose": "cache"})
        >>>
        >>> # Get by ID
        >>> users = xfiles.get("users_db")
        >>>
        >>> # Search by metadata
        >>> mongo_repos = xfiles.search(lambda m: m.get("type") == "mongodb")
        >>>
        >>> # Get capabilities
        >>> caps = xfiles.get_capabilities("users_db")
    """

    def __init__(self, *, spock: Optional["Spock"] = None):
        """Initialize XFiles repository manager.

        Args:
            spock: Optional Spock configuration manager for settings.
        """
        self._registry: dict[str, RepositoryEntry] = {}
        self._spock = spock
        logger.debug("XFiles instance created.")

    # =========================================================================
    # REGISTRATION
    # =========================================================================

    def execute_register(
        self,
        id: str,
        repository: BaseRepository,
        meta: dict[str, Any] | None = None,
    ) -> RegisterResult:
        """Register a repository with the given ID.

        [Result Pattern] Check result.is_ok() and result.created for status.

        Args:
            id: Unique identifier for the repository.
            repository: Repository instance implementing BaseRepository.
            meta: Optional metadata for searching/filtering.
                Common keys: "type", "domain", "purpose", "tags".

        Returns:
            RegisterResult with:
            - success + created=True: New registration
            - success + created=False + detail(DUPLICATE): Same instance (skipped)
            - error + detail(ALREADY_EXISTS): Different instance with same ID
            - error + detail(INVALID): Invalid ID or repository type

        Example:
            >>> result = xfiles.execute_register(
            ...     "orders_sql",
            ...     postgres_repo,
            ...     meta={"type": "postgresql", "domain": "orders"},
            ... )
            >>> if result.is_ok() and result.created:
            ...     print("Registered!")
        """
        # Validate ID
        if not isinstance(id, str) or not id.strip():
            return RegisterResult.fail(
                StatusDetail(
                    code=StatusCode.INVALID,
                    message=f"Invalid repository ID: {id!r}",
                    context={"id": id},
                ),
                id=str(id) if id else "",
                created=False,
            )

        # Protocol compliance
        if not isinstance(repository, BaseRepository):
            return RegisterResult.fail(
                StatusDetail(
                    code=StatusCode.INVALID,
                    message=f"Repository '{id}' does not implement the BaseRepository protocol",
                    context={"id": id, "type": type(repository).__name__},
                ),
                id=id,
                created=False,
            )

        # Override policy: do not allow overriding existing registrations
        if id in self._registry:
            if self._registry[id].repository is repository:
                logger.warning(
                    "Repository '%s' already registered with the same instance; attention and investigate because this could be a poor use of resources. Skipping.",
                    id,
                )
                return RegisterResult.success(
                    id=id,
                    created=False,
                    detail=StatusDetail(
                        code=StatusCode.DUPLICATE,
                        message="Same instance already registered",
                    ),
                )
            return RegisterResult.fail(
                StatusDetail(
                    code=StatusCode.ALREADY_EXISTS,
                    message=f"Override not allowed for already registered repository: {id!r}",
                    context={"id": id},
                ),
                id=id,
                created=False,
            )

        entry = RepositoryEntry(
            id=id,
            repository=repository,
            meta=meta or {},
        )
        self._registry[id] = entry
        logger.debug("Repository '%s' registered successfully.", id)
        return RegisterResult.success(id=id, created=True)

    def unregister(self, id: str) -> bool:
        """Unregister a repository by ID.

        Args:
            id: The repository identifier.

        Returns:
            True if the repository was removed, False if not found.
        """
        if id in self._registry:
            del self._registry[id]
            logger.debug("Repository '%s' unregistered.", id)
            return True
        return False

    # =========================================================================
    # LOOKUP
    # =========================================================================

    def execute_get(self, id: str) -> GetResult:
        """Get a repository by its ID.

        [Result Pattern] Check result.is_ok() and result.repository.

        Args:
            id: The repository identifier.

        Returns:
            GetResult with:
            - success: Repository found in result.repository
            - success + detail(NOT_FOUND): Repository not found (expected state)
        """
        entry = self._registry.get(id)
        if entry is None:
            logger.debug("Repository '%s' not found in registry.", id)
            return GetResult.success(
                repository=None,
                id=id,
                detail=StatusDetail(
                    code=StatusCode.NOT_FOUND,
                    message=f"Repository '{id}' not found",
                    context={"id": id},
                ),
            )
        return GetResult.success(repository=entry.repository, id=id)

    def get_typed(self, id: str, protocol: type[T]) -> T | None:
        """Get a repository by ID with type checking.

        Args:
            id: The repository identifier.
            protocol: Expected protocol type (e.g., QueryableRepository).

        Returns:
            The repository instance if found and compatible, None otherwise.

        Example:
            >>> repo = xfiles.get_typed("users", QueryableRepository)
            >>> if repo:
            ...     results = repo.find(query)
        """
        entry = self._registry.get(id)
        if entry is None:
            return None
        if isinstance(entry.repository, protocol):
            return entry.repository  # type: ignore
        logger.debug(
            "Repository '%s' found but not compatible with %s.",
            id,
            protocol.__name__,
        )
        return None

    def get_meta(self, id: str) -> dict[str, Any] | None:
        """Get the metadata for a repository.

        Args:
            id: The repository identifier.

        Returns:
            Copy of the metadata dict if found, None otherwise.
        """
        entry = self._registry.get(id)
        if entry is None:
            return None
        return dict(entry.meta)

    def get_capabilities(self, id: str) -> Capabilities | None:
        """Get the capabilities of a repository.

        Args:
            id: The repository identifier.

        Returns:
            Capabilities if found, None otherwise.
        """
        entry = self._registry.get(id)
        if entry is None:
            return None
        return entry.repository.capabilities()

    def has(self, id: str) -> bool:
        """Check if a repository exists in the registry.

        Args:
            id: The repository identifier.

        Returns:
            True if the repository exists, False otherwise.
        """
        return id in self._registry

    # =========================================================================
    # SEARCH
    # =========================================================================

    def execute_search(
        self,
        predicate: Callable[[dict[str, Any]], bool],
    ) -> SearchRepoResult:
        """Search repositories by metadata predicate.

        [Result Pattern] Check result.is_ok() and result.repositories.

        Args:
            predicate: Function that takes metadata dict and returns
                True if the repository should be included.

        Returns:
            SearchRepoResult with:
            - success: Search completed, repositories in result.repositories
            - success + detail(NO_RESULTS): No matches found (informational)

        Example:
            >>> result = xfiles.execute_search(lambda m: m.get("type") == "mongodb")
            >>> if result.is_ok():
            ...     for repo in result.repositories:
            ...         use(repo)
        """
        repositories = []
        ids = []
        for entry in self._registry.values():
            try:
                if predicate(entry.meta):
                    repositories.append(entry.repository)
                    ids.append(entry.id)
            except Exception as e:
                logger.warning(
                    "Predicate failed for repository '%s': %s",
                    entry.id,
                    e,
                )

        if not repositories:
            return SearchRepoResult.success(
                repositories=[],
                ids=[],
                detail=StatusDetail(
                    code=StatusCode.NO_RESULTS,
                    message="No repositories matched the predicate",
                ),
            )
        return SearchRepoResult.success(repositories=repositories, ids=ids)

    def execute_search_by_meta(
        self,
        **criteria: Any,
    ) -> SearchRepoResult:
        """Search repositories by exact metadata key-value matches.

        [Result Pattern] Check result.is_ok() and result.repositories.

        Args:
            **criteria: Key-value pairs that must match in metadata.
                Special handling:
                - Lists: at least one element must match.
                - None: key must exist in meta.

        Returns:
            SearchRepoResult with matching repositories.

        Example:
            >>> result = xfiles.execute_search_by_meta(type="mongodb", domain="users")
            >>> if result.is_ok():
            ...     for repo in result.repositories:
            ...         use(repo)
        """

        def matcher(meta: dict[str, Any]) -> bool:
            for key, value in criteria.items():
                if key not in meta:
                    return False
                meta_value = meta[key]
                if value is None:
                    # Just check existence
                    continue
                if isinstance(value, (list, tuple)):
                    # Check if any value matches
                    if meta_value not in value:
                        return False
                elif meta_value != value:
                    return False
            return True

        return self.execute_search(matcher)

    def execute_search_by_capability(
        self,
        capability_check: Callable[[Capabilities], bool],
    ) -> SearchRepoResult:
        """Search repositories by capability predicate.

        [Result Pattern] Check result.is_ok() and result.repositories.

        Args:
            capability_check: Function that takes Capabilities and returns
                True if the repository should be included.

        Returns:
            SearchRepoResult with matching repositories.

        Example:
            >>> result = xfiles.execute_search_by_capability(
            ...     lambda c: c.vector_search.supported
            ... )
            >>> if result.is_ok():
            ...     for repo in result.repositories:
            ...         use(repo)
        """
        repositories = []
        ids = []
        for entry in self._registry.values():
            try:
                caps = entry.repository.capabilities()
                if capability_check(caps):
                    repositories.append(entry.repository)
                    ids.append(entry.id)
            except Exception as e:
                logger.warning(
                    "Capability check failed for repository '%s': %s",
                    entry.id,
                    e,
                )

        if not repositories:
            return SearchRepoResult.success(
                repositories=[],
                ids=[],
                detail=StatusDetail(
                    code=StatusCode.NO_RESULTS,
                    message="No repositories matched the capability check",
                ),
            )
        return SearchRepoResult.success(repositories=repositories, ids=ids)

    # =========================================================================
    # ITERATION & INFO
    # =========================================================================

    def list_ids(self) -> list[str]:
        """Get a list of all registered repository IDs.

        Returns:
            List of repository IDs in the registry.
        """
        return list(self._registry.keys())

    def __len__(self) -> int:
        """Return the number of registered repositories."""
        return len(self._registry)

    def __iter__(self) -> Iterator[tuple[str, BaseRepository]]:
        """Iterate over (id, repository) pairs."""
        for entry in self._registry.values():
            yield entry.id, entry.repository

    def __contains__(self, id: str) -> bool:
        """Check if repository ID exists in registry."""
        return id in self._registry

    @property
    def registry(self) -> dict[str, BaseRepository]:
        """Get a copy of the registry as {id: repository} dict.

        Returns:
            Shallow copy of the registry dictionary.
        """
        return {entry.id: entry.repository for entry in self._registry.values()}

    # =========================================================================
    # DEFAULT RESOLUTION
    # =========================================================================

    def get_default(self, purpose: str | None = None) -> BaseRepository:
        """Return the default repository based on configuration hints.

        Args:
            purpose: Optional purpose qualifier (e.g., "vectors", "cache").
                If provided, looks for purpose-specific config key.

        Returns:
            The repository instance that should be treated as default.

        Raises:
            LookupError: If no repositories are registered or default
                selection fails.
        """
        registry_size = len(self._registry)

        if registry_size == 0:
            raise LookupError("No repositories registered; unable to determine default.")

        config_key = f"repository_default_{purpose}" if purpose else "repository_default"
        configured_id = self._resolve_config_key(config_key)

        if registry_size == 1:
            only_id, entry = next(iter(self._registry.items()))
            if configured_id and configured_id != only_id:
                logger.warning(
                    "Configured default repository '%s' not found; "
                    "using only registered repository '%s' instead.",
                    configured_id,
                    only_id,
                )
            return entry.repository

        if not configured_id:
            raise LookupError(
                f"Multiple repositories registered but no default configured; "
                f"set 'rag2f.{config_key}'."
            )

        entry = self._registry.get(configured_id)
        if entry is None:
            available = ", ".join(sorted(self._registry.keys())) or "<none>"
            raise LookupError(
                f"Default repository '{configured_id}' not registered. Available: {available}."
            )

        return entry.repository

    def _resolve_config_key(self, key: str) -> str | None:
        """Resolve a configuration key from Spock.

        Args:
            key: Configuration key to look up.

        Returns:
            Configured value or None.
        """
        if self._spock is None:
            return None

        value = self._spock.get_rag2f_config(key)
        if isinstance(value, str):
            value = value.strip()
        return value or None


# Alias for consistency with other managers
RepositoryManager = XFiles


__all__ = [
    "XFiles",
    "RepositoryManager",
    "RepositoryEntry",
]
