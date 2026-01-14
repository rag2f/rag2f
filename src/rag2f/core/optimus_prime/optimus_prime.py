"""OptimusPrime - Embedder Registry Manager for RAG2F.

OptimusPrime manages the registry of embedders, providing a centralized
interface for registering, retrieving, and querying embedders throughout
the application.

Named after Optimus Prime from Transformers, this class transforms and
manages the embedder ecosystem within RAG2F.
"""

import logging
from typing import TYPE_CHECKING, Optional

from rag2f.core.protocols import Embedder

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from rag2f.core.spock.spock import Spock


class OptimusPrime:
    """Embedder registry manager for RAG2F instances.

    Each RAG2F instance has its own OptimusPrime instance to maintain
    isolated embedder registry state.

    Famous quote from Optimus Prime in Transformers:
    "Freedom is the right of all sentient beings."
    """

    def __init__(self, *, spock: Optional["Spock"] = None):
        """Initialize OptimusPrime embedder registry manager."""
        self._embedder_registry: dict[str, Embedder] = {}
        self._spock = spock
        logger.debug("OptimusPrime instance created.")

    def register(self, key: str, embedder: Embedder) -> None:
        """Register an embedder with the given key.

        Args:
            key: Unique identifier for the embedder
            embedder: Embedder instance implementing the Embedder protocol

        Raises:
            ValueError: If key is invalid or already exists
            TypeError: If embedder doesn't implement Embedder protocol
        """
        # Validate key
        if not isinstance(key, str) or not key.strip():
            raise ValueError(f"Invalid embedder key: {key!r}")

        # Protocol compliance
        if not isinstance(embedder, Embedder):
            raise TypeError(f"Embedder '{key}' does not implement the Embedder protocol")

        # Override policy: do not allow overriding existing embedders.
        # Idempotency: allow registering the *same instance* twice.
        if key in self._embedder_registry:
            if self._embedder_registry[key] is embedder:
                logger.warning(
                    "Embedder '%s' already registered with the same instance; attention and investigate because this could be a poor use of resources. Skipping.",
                    key,
                )
                return
            raise ValueError(f"Override not allowed for already registered embedder: {key!r}")

        self._embedder_registry[key] = embedder
        logger.debug("Embedder '%s' registered successfully.", key)

    def get(self, key: str) -> Embedder | None:
        """Get an embedder by its key.

        Args:
            key: The embedder identifier

        Returns:
            The Embedder instance if found, None otherwise
        """
        embedder = self._embedder_registry.get(key)
        if embedder is None:
            logger.debug("Embedder '%s' not found in registry.", key)
        return embedder

    def has(self, key: str) -> bool:
        """Check if an embedder exists in the registry.

        Args:
            key: The embedder identifier

        Returns:
            True if the embedder exists, False otherwise
        """
        return key in self._embedder_registry

    def list_keys(self) -> list[str]:
        """Get a list of all registered embedder keys.

        Returns:
            List of embedder keys in the registry
        """
        return list(self._embedder_registry.keys())

    def unregister(self, key: str) -> bool:
        """Unregister an embedder by key.

        Returns True if the embedder was removed, False if it was not found.
        """
        if key in self._embedder_registry:
            del self._embedder_registry[key]
            logger.debug("Embedder '%s' unregistered.", key)
            return True
        return False

    def get_default(self) -> Embedder:
        """Return the default embedder based on configuration hints.

        Returns:
            The Embedder instance that should be treated as default.

        Raises:
            LookupError: If no embedders are registered or default selection fails.
        """
        registry_size = len(self._embedder_registry)

        if registry_size == 0:
            raise LookupError("No embedders registered; unable to determine default embedder.")

        normalized_key = self._resolve_default_key()

        if registry_size == 1:
            only_key, embedder = next(iter(self._embedder_registry.items()))
            if normalized_key and normalized_key != only_key:
                logger.warning(
                    "Configured default embedder '%s' not found; using only registered embedder '%s' instead.",
                    normalized_key,
                    only_key,
                )
            return embedder

        if not normalized_key:
            raise LookupError(
                "Multiple embedders registered but no default configured; set 'rag2f.embedder_default'."
            )

        embedder = self._embedder_registry.get(normalized_key)
        if embedder is None:
            available = ", ".join(sorted(self._embedder_registry.keys())) or "<none>"
            raise LookupError(
                f"Default embedder '{normalized_key}' not registered. Available embedders: {available}."
            )

        return embedder

    def _resolve_default_key(self) -> str | None:
        if self._spock is None:
            return None

        value = self._spock.get_rag2f_config("embedder_default")
        if isinstance(value, str):
            value = value.strip()
        return value or None

    @property
    def registry(self) -> dict[str, Embedder]:
        """Get a copy of the embedder registry.

        Returns:
            A shallow copy of the embedder registry dictionary
        """
        return dict(self._embedder_registry)


EmbedderManager = OptimusPrime
