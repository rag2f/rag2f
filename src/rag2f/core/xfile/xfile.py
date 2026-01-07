"""XFile - Repository Plugin Manager.

XFile manages a registry of pluggable repositories, providing a centralized
interface for registering, retrieving by ID, and querying repositories
by metadata.

Named after The X-Files, this class manages the mysterious and varied
collection of data repositories within RAG2F - "The truth is out there."
"""

import logging
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    Iterator,
    List,
    Optional,
    TYPE_CHECKING,
    TypeVar,
    Union,
)

from rag2f.core.xfile.capabilities import Capabilities
from rag2f.core.xfile.repository import (
    AnyRepository,
    BaseRepository,
    QueryableRepository,
    VectorSearchRepository,
    GraphTraversalRepository,
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
    meta: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# XFILE - REPOSITORY PLUGIN MANAGER
# =============================================================================

class XFile:
    """Repository plugin manager for RAG2F instances.
    
    XFile manages a collection of heterogeneous repository plugins,
    providing:
    - Registration with unique IDs and metadata.
    - Lookup by ID.
    - Search by metadata predicates.
    - Iteration over registered repositories.
    
    Each RAG2F instance has its own XFile instance to maintain
    isolated repository registry state.
    
    Famous quote from The X-Files:
    "The truth is out there."
    
    Example:
        >>> xfile = XFile()
        >>> xfile.register("users_db", mongo_repo, meta={"type": "mongodb", "domain": "users"})
        >>> xfile.register("cache", redis_repo, meta={"type": "redis", "purpose": "cache"})
        >>> 
        >>> # Get by ID
        >>> users = xfile.get("users_db")
        >>> 
        >>> # Search by metadata
        >>> mongo_repos = xfile.search(lambda m: m.get("type") == "mongodb")
        >>> 
        >>> # Get capabilities
        >>> caps = xfile.get_capabilities("users_db")
    """

    def __init__(self, *, spock: Optional["Spock"] = None):
        """Initialize XFile repository manager.
        
        Args:
            spock: Optional Spock configuration manager for settings.
        """
        self._registry: Dict[str, RepositoryEntry] = {}
        self._spock = spock
        logger.debug("XFile instance created.")

    # =========================================================================
    # REGISTRATION
    # =========================================================================

    def register(
        self,
        id: str,
        repository: BaseRepository,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Register a repository with the given ID.
        
        Args:
            id: Unique identifier for the repository.
            repository: Repository instance implementing BaseRepository.
            meta: Optional metadata for searching/filtering.
                Common keys: "type", "domain", "purpose", "tags".
                
        Raises:
            ValueError: If ID is invalid or already exists.
            TypeError: If repository doesn't implement BaseRepository.
            
        Example:
            >>> xfile.register(
            ...     "orders_sql",
            ...     postgres_repo,
            ...     meta={"type": "postgresql", "domain": "orders", "tags": ["sql", "transactional"]},
            ... )
        """
        # Validate ID
        if not isinstance(id, str) or not id.strip():
            raise ValueError(f"Invalid repository ID: {id!r}")
        
        # Protocol compliance
        if not isinstance(repository, BaseRepository):
            raise TypeError(
                f"Repository '{id}' does not implement the BaseRepository protocol"
            )
        
        # Override policy: do not allow overriding existing registrations
        if id in self._registry:
            raise ValueError(
                f"Override not allowed for already registered repository: {id!r}"
            )
        
        entry = RepositoryEntry(
            id=id,
            repository=repository,
            meta=meta or {},
        )
        self._registry[id] = entry
        logger.debug("Repository '%s' registered successfully.", id)

    def register_batch(
        self,
        repositories: Dict[str, Union[BaseRepository, tuple[BaseRepository, Dict[str, Any]]]],
    ) -> None:
        """Register multiple repositories at once.
        
        Args:
            repositories: Dictionary mapping IDs to either:
                - Repository instances (no metadata).
                - Tuples of (repository, metadata).
                
        Raises:
            ValueError: If any ID is invalid or already exists.
            TypeError: If any repository doesn't implement BaseRepository.
            
        Example:
            >>> xfile.register_batch({
            ...     "users": users_repo,
            ...     "orders": (orders_repo, {"type": "sql", "domain": "orders"}),
            ...     "cache": (cache_repo, {"type": "redis"}),
            ... })
        """
        if repositories is None:
            repositories = {}
        
        if not hasattr(repositories, "items"):
            raise TypeError(
                "repositories parameter must be a mapping (e.g., dict)."
            )
        
        # Copy-on-write: work on a copy, then swap the reference
        new_registry: Dict[str, RepositoryEntry] = dict(self._registry)
        
        # Single pass: validate + insert
        for id, value in repositories.items():
            # Validate ID
            if not isinstance(id, str) or not id.strip():
                raise ValueError(f"Invalid repository ID: {id!r}")
            
            # Parse value (repo or (repo, meta) tuple)
            if isinstance(value, tuple) and len(value) == 2:
                repository, meta = value
            else:
                repository = value
                meta = {}
            
            # Protocol compliance
            if not isinstance(repository, BaseRepository):
                raise TypeError(
                    f"Repository '{id}' does not implement the BaseRepository protocol"
                )
            
            # Override policy
            if id in new_registry:
                raise ValueError(
                    f"Override not allowed for already registered repository: {id!r}"
                )
            
            entry = RepositoryEntry(
                id=id,
                repository=repository,
                meta=meta if isinstance(meta, dict) else {},
            )
            new_registry[id] = entry
        
        # Atomic swap of the reference
        self._registry = new_registry
        logger.debug(
            "Batch registration completed. Registry size=%d (+%d new repositories).",
            len(self._registry),
            len(repositories),
        )

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

    def get(self, id: str) -> Optional[BaseRepository]:
        """Get a repository by its ID.
        
        Args:
            id: The repository identifier.
            
        Returns:
            The repository instance if found, None otherwise.
        """
        entry = self._registry.get(id)
        if entry is None:
            logger.debug("Repository '%s' not found in registry.", id)
            return None
        return entry.repository

    def get_typed(self, id: str, protocol: type[T]) -> Optional[T]:
        """Get a repository by ID with type checking.
        
        Args:
            id: The repository identifier.
            protocol: Expected protocol type (e.g., QueryableRepository).
            
        Returns:
            The repository instance if found and compatible, None otherwise.
            
        Example:
            >>> repo = xfile.get_typed("users", QueryableRepository)
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

    def get_meta(self, id: str) -> Optional[Dict[str, Any]]:
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

    def get_capabilities(self, id: str) -> Optional[Capabilities]:
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

    def search(
        self,
        predicate: Callable[[Dict[str, Any]], bool],
    ) -> List[BaseRepository]:
        """Search repositories by metadata predicate.
        
        Args:
            predicate: Function that takes metadata dict and returns
                True if the repository should be included.
                
        Returns:
            List of matching repositories.
            
        Example:
            >>> # Find all SQL repositories
            >>> sql_repos = xfile.search(lambda m: m.get("type") in ("postgresql", "mysql"))
            >>> 
            >>> # Find repositories with specific tag
            >>> cached = xfile.search(lambda m: "cache" in m.get("tags", []))
        """
        results = []
        for entry in self._registry.values():
            try:
                if predicate(entry.meta):
                    results.append(entry.repository)
            except Exception as e:
                logger.warning(
                    "Predicate failed for repository '%s': %s",
                    entry.id,
                    e,
                )
        return results

    def search_ids(
        self,
        predicate: Callable[[Dict[str, Any]], bool],
    ) -> List[str]:
        """Search repository IDs by metadata predicate.
        
        Args:
            predicate: Function that takes metadata dict and returns
                True if the repository should be included.
                
        Returns:
            List of matching repository IDs.
        """
        results = []
        for entry in self._registry.values():
            try:
                if predicate(entry.meta):
                    results.append(entry.id)
            except Exception as e:
                logger.warning(
                    "Predicate failed for repository '%s': %s",
                    entry.id,
                    e,
                )
        return results

    def search_by_meta(
        self,
        **criteria: Any,
    ) -> List[BaseRepository]:
        """Search repositories by exact metadata key-value matches.
        
        Args:
            **criteria: Key-value pairs that must match in metadata.
                Special handling:
                - Lists: at least one element must match.
                - None: key must exist in meta.
                
        Returns:
            List of matching repositories.
            
        Example:
            >>> # Find all MongoDB repositories in users domain
            >>> repos = xfile.search_by_meta(type="mongodb", domain="users")
        """
        def matcher(meta: Dict[str, Any]) -> bool:
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
        
        return self.search(matcher)

    def search_by_capability(
        self,
        capability_check: Callable[[Capabilities], bool],
    ) -> List[BaseRepository]:
        """Search repositories by capability predicate.
        
        Args:
            capability_check: Function that takes Capabilities and returns
                True if the repository should be included.
                
        Returns:
            List of matching repositories.
            
        Example:
            >>> # Find all repositories that support vector search
            >>> vector_repos = xfile.search_by_capability(
            ...     lambda c: c.vector_search.supported
            ... )
            >>> 
            >>> # Find repos with native pushdown filtering
            >>> pushdown_repos = xfile.search_by_capability(
            ...     lambda c: c.filter.supported and c.filter.pushdown
            ... )
        """
        results = []
        for entry in self._registry.values():
            try:
                caps = entry.repository.capabilities()
                if capability_check(caps):
                    results.append(entry.repository)
            except Exception as e:
                logger.warning(
                    "Capability check failed for repository '%s': %s",
                    entry.id,
                    e,
                )
        return results

    # =========================================================================
    # ITERATION & INFO
    # =========================================================================

    def list_ids(self) -> List[str]:
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
    def registry(self) -> Dict[str, BaseRepository]:
        """Get a copy of the registry as {id: repository} dict.
        
        Returns:
            Shallow copy of the registry dictionary.
        """
        return {entry.id: entry.repository for entry in self._registry.values()}

    # =========================================================================
    # DEFAULT RESOLUTION
    # =========================================================================

    def get_default(self, purpose: Optional[str] = None) -> BaseRepository:
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
                f"Default repository '{configured_id}' not registered. "
                f"Available: {available}."
            )
        
        return entry.repository

    def _resolve_config_key(self, key: str) -> Optional[str]:
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
RepositoryManager = XFile


__all__ = [
    "XFile",
    "RepositoryManager",
    "RepositoryEntry",
]
