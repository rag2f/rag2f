"""XFiles result DTOs.

Defines typed result classes for XFiles repository operations.
Uses the Result pattern: expected states return Result with appropriate status,
system errors raise exceptions.
"""

from typing import TYPE_CHECKING, Any

from pydantic import Field

from rag2f.core.dto.result_dto import BaseResult

if TYPE_CHECKING:
    pass


class GetResult(BaseResult):
    """Result of getting a repository by ID.

    [Result Pattern] Check result.is_ok() before using result.repository.

    Attributes:
        repository: The repository instance if found.
        id: The requested repository ID.

    Status codes:
        - success: Repository found
        - success + detail(NOT_FOUND): Repository not found (expected state)
    """

    repository: Any = Field(default=None, description="Repository if found (BaseRepository)")
    id: str = Field(default="", description="Requested repository ID")


class RegisterResult(BaseResult):
    """Result of registering a repository.

    [Result Pattern] Check result.is_ok() before assuming registration succeeded.

    Attributes:
        id: The repository ID.
        created: Whether a new registration was created (vs. skipped).

    Status codes:
        - success: Repository registered successfully
        - success + detail(DUPLICATE): Same instance already registered (skipped)
        - error + detail(ALREADY_EXISTS): Different instance with same ID exists
        - error + detail(INVALID): Invalid ID or repository
    """

    id: str = Field(default="", description="Repository ID")
    created: bool = Field(default=True, description="True if newly created, False if skipped")


class SearchRepoResult(BaseResult):
    """Result of searching repositories.

    [Result Pattern] Check result.is_ok() before using result.repositories.

    Attributes:
        repositories: List of matching repositories.
        ids: List of matching repository IDs.

    Status codes:
        - success: Search completed (may be empty)
        - success + detail(NO_RESULTS): No repositories matched (informational)
    """

    repositories: list[Any] = Field(
        default_factory=list, description="Matching repositories (BaseRepository)"
    )
    ids: list[str] = Field(default_factory=list, description="Matching repository IDs")


class CacheResult(BaseResult):
    """Result of cache operations (get from cache).

    [Result Pattern] Check result.is_ok() before using result.value.

    Attributes:
        value: Cached value if found.
        key: The cache key requested.
        hit: Whether the cache was hit.

    Status codes:
        - success + hit=True: Cache hit
        - error + detail(CACHE_MISS): Cache miss (explicit lookup failed)
    """

    value: Any = Field(default=None, description="Cached value if hit")
    key: str = Field(default="", description="Cache key")
    hit: bool = Field(default=False, description="True if cache hit")


__all__ = [
    "GetResult",
    "RegisterResult",
    "SearchRepoResult",
    "CacheResult",
]
