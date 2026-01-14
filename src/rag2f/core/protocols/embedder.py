"""Embedding protocol definitions.

This module defines the `Embedder` protocol and helpers used to register
embedder implementations.
"""

from typing import Protocol, runtime_checkable

Vector = list[float]


@runtime_checkable
class Embedder(Protocol):
    """Structural interface (duck typing) for embedding providers."""

    @property
    def size(self) -> int:
        """Expected size of the embedding vector produced by this provider."""
        ...

    def getEmbedding(self, text: str, *, normalize: bool = False) -> Vector:
        """Returns the embedding of `text` as a list of floats, with length == size."""
        ...

    # def getEmbeddingBatch(
    #     self, texts: Sequence[str], *, normalize: bool = False
    # ) -> List[Vector]:
    #     """Returns an embedding for each text (order preserved), each of length `size`."""
    #     ...


def register(reg: dict[str, Embedder], name: str, obj: object) -> None:
    """Register an embedder instance in a registry.

    Args:
        reg: Registry mapping from name to embedder.
        name: Registry key.
        obj: Candidate embedder object.

    Raises:
        TypeError: If obj does not implement the Embedder protocol.
    """
    if not isinstance(obj, Embedder):  # funziona grazie a @runtime_checkable
        raise TypeError(f"{name} does not implement Embedder (missing size/getEmbedding)")
    reg[name] = obj
