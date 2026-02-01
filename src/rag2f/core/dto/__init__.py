"""DTO package for rag2f core.

Provides BaseResult pattern for consistent result handling across modules.
"""

from .indiana_jones_dto import RetrievedItem, RetrieveResult, ReturnMode, SearchResult
from .johnny5_dto import InsertResult
from .result_dto import BaseResult, StatusCode, StatusDetail
from .xfiles_dto import CacheResult, GetResult, RegisterResult, SearchRepoResult

__all__ = [
    "BaseResult",
    "StatusDetail",
    "StatusCode",
    "InsertResult",
    "RetrievedItem",
    "RetrieveResult",
    "ReturnMode",
    "SearchResult",
    "GetResult",
    "RegisterResult",
    "SearchRepoResult",
    "CacheResult",
]
