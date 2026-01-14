"""XFiles - Repository Plugin Exceptions.

Custom exceptions for repository operations, providing clear error
semantics for CRUD, query validation, and backend interactions.
"""

from typing import Any


class RepositoryError(Exception):
    """Base exception for all repository-related errors."""

    pass


class NotFound(RepositoryError):
    """Raised when a requested document is not found.

    Attributes:
        id: The identifier of the document that was not found.
        repository: Optional name of the repository.
    """

    def __init__(self, id: Any, repository: str | None = None):
        """Initialize NotFound.

        Args:
            id: The identifier of the missing document.
            repository: Optional name of the repository.
        """
        self.id = id
        self.repository = repository
        repo_info = f" in repository '{repository}'" if repository else ""
        super().__init__(f"Document with id={id!r} not found{repo_info}.")


class AlreadyExists(RepositoryError):
    """Raised when attempting to insert a document with an existing id.

    Attributes:
        id: The identifier that already exists.
        repository: Optional name of the repository.
    """

    def __init__(self, id: Any, repository: str | None = None):
        """Initialize AlreadyExists.

        Args:
            id: The identifier of the document that already exists.
            repository: Optional name of the repository.
        """
        self.id = id
        self.repository = repository
        repo_info = f" in repository '{repository}'" if repository else ""
        super().__init__(f"Document with id={id!r} already exists{repo_info}.")


class NotSupported(RepositoryError):
    """Raised when a requested feature or operation is not supported.

    This exception should be raised when:
    - A capability is not supported by the plugin (fail-fast).
    - A specific operator in a where clause is not supported.
    - A native handle type is requested but not available.

    Attributes:
        feature: The feature or operation that is not supported.
        repository: Optional name of the repository.
        details: Optional additional context.
    """

    def __init__(
        self,
        feature: str,
        repository: str | None = None,
        details: str | None = None,
    ):
        """Initialize NotSupported.

        Args:
            feature: The unsupported feature or operation.
            repository: Optional name of the repository.
            details: Optional extra details.
        """
        self.feature = feature
        self.repository = repository
        self.details = details

        repo_info = f" in repository '{repository}'" if repository else ""
        detail_info = f": {details}" if details else ""
        super().__init__(f"Feature '{feature}' is not supported{repo_info}{detail_info}.")


class ValidationError(RepositoryError):
    """Raised when input validation fails.

    This exception should be raised when:
    - A field in select/projection is not allowed.
    - A where clause operator is invalid.
    - An order_by field is not sortable.
    - Limit/offset values are invalid or exceed allowed maximums.

    Attributes:
        details: Description of what validation failed.
        field: Optional name of the field that failed validation.
        value: Optional value that failed validation.
    """

    def __init__(
        self,
        details: str,
        field: str | None = None,
        value: Any = None,
    ):
        """Initialize ValidationError.

        Args:
            details: Human-readable description of the validation failure.
            field: Optional field name associated with the error.
            value: Optional invalid value.
        """
        self.details = details
        self.field = field
        self.value = value

        field_info = f" (field={field!r})" if field else ""
        value_info = f" [value={value!r}]" if value is not None else ""
        super().__init__(f"Validation error{field_info}: {details}{value_info}")


class BackendError(RepositoryError):
    """Raised when an underlying backend operation fails.

    This exception wraps errors from the underlying storage system
    (database, file system, etc.) and provides context.

    Attributes:
        details: Description of the backend error.
        cause: Optional original exception from the backend.
    """

    def __init__(
        self,
        details: str,
        cause: BaseException | None = None,
    ):
        """Initialize BackendError.

        Args:
            details: Description of the backend error.
            cause: Optional original exception from the backend.
        """
        self.details = details
        self.cause = cause

        cause_info = f" (caused by: {type(cause).__name__}: {cause})" if cause else ""
        super().__init__(f"Backend error: {details}{cause_info}")

        if cause:
            self.__cause__ = cause


__all__ = [
    "RepositoryError",
    "NotFound",
    "AlreadyExists",
    "NotSupported",
    "ValidationError",
    "BackendError",
]
