"""Mock plugin overrides used by activation/deactivation tests."""

from rag2f.core.morpheus.decorators.plugin_decorator import plugin
from rag2f.core.rag2f import RAG2F
from rag2f.core.xfiles import BaseRepository, minimal_crud_capabilities
from rag2f.core.xfiles.types import Document, DocumentId, Patch


class MockEmbedder:
    """Simple embedder used by the mock plugin tests."""

    @property
    def size(self) -> int:
        """Return a small fixed embedding size for tests."""
        return 3

    def getEmbedding(self, text: str, *, normalize: bool = False):
        """Return a deterministic embedding vector for tests."""
        return [0.1, 0.2, 0.3]


class MockRepository(BaseRepository):
    """Repository stub used by the mock plugin activation tests."""

    def __init__(self, name: str):
        """Create a repository stub with the given name."""
        self._name = name

    @property
    def name(self) -> str:
        """Return the repository name."""
        return self._name

    def capabilities(self):
        """Return minimal CRUD capabilities for this repository."""
        return minimal_crud_capabilities()

    def get(self, id: DocumentId, select: list[str] | None = None) -> Document:  # pragma: no cover
        """Not implemented for this repository stub."""
        raise NotImplementedError("MockRepository does not store data")

    def insert(self, id: DocumentId, item: Document) -> None:  # pragma: no cover
        """Not implemented for this repository stub."""
        raise NotImplementedError("MockRepository does not store data")

    def update(self, id: DocumentId, patch: Patch) -> None:  # pragma: no cover
        """Not implemented for this repository stub."""
        raise NotImplementedError("MockRepository does not store data")

    def delete(self, id: DocumentId) -> None:  # pragma: no cover
        """Not implemented for this repository stub."""
        raise NotImplementedError("MockRepository does not store data")

    def _get_native_handle(self, kind: str):  # pragma: no cover
        raise NotImplementedError("MockRepository does not expose native handles")


@plugin
def activated(plugin, rag2f_instance: RAG2F):
    """Activation hook that registers an embedder and a repository."""
    plugin.custom_id = plugin.id
    embedder_manager = rag2f_instance.optimus_prime
    if not embedder_manager.has(plugin.id):
        embedder_manager.register(plugin.id, MockEmbedder())

    repo_manager = rag2f_instance.xfiles
    repo_id = f"{plugin.id}_repository"
    if not repo_manager.has(repo_id):
        repo = MockRepository(repo_id)
        repo_manager.execute_register(repo_id, repo, meta={"origin": "mock_plugin"})


@plugin
def deactivated(plugin, rag2f_instance: RAG2F):
    """Deactivation hook that unregisters the embedder and repository."""
    embedder_manager = rag2f_instance.optimus_prime
    embedder_manager.unregister(plugin.id)

    repo_manager = rag2f_instance.xfiles
    repo_id = f"{plugin.id}_repository"
    repo_manager.unregister(repo_id)
