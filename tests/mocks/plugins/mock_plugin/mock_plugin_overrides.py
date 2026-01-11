from typing import List, Optional

from rag2f.core.morpheus.decorators.plugin_decorator import plugin
from rag2f.core.rag2f import RAG2F
from rag2f.core.xfiles import BaseRepository, minimal_crud_capabilities
from rag2f.core.xfiles.types import Document, DocumentId, Patch


class MockEmbedder:
    """Simple embedder used by the mock plugin tests."""

    @property
    def size(self) -> int:
        return 3

    def getEmbedding(self, text: str, *, normalize: bool = False):
        return [0.1, 0.2, 0.3]


class MockRepository(BaseRepository):
    """Repository stub used by the mock plugin activation tests."""

    def __init__(self, name: str):
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def capabilities(self):
        return minimal_crud_capabilities()

    def get(self, id: DocumentId, select: Optional[List[str]] = None) -> Document:  # pragma: no cover
        raise NotImplementedError("MockRepository does not store data")

    def insert(self, id: DocumentId, item: Document) -> None:  # pragma: no cover
        raise NotImplementedError("MockRepository does not store data")

    def update(self, id: DocumentId, patch: Patch) -> None:  # pragma: no cover
        raise NotImplementedError("MockRepository does not store data")

    def delete(self, id: DocumentId) -> None:  # pragma: no cover
        raise NotImplementedError("MockRepository does not store data")

    def _get_native_handle(self, kind: str):  # pragma: no cover
        raise NotImplementedError("MockRepository does not expose native handles")


@plugin
def activated(plugin, rag2f_instance: RAG2F):
    plugin.custom_id = plugin.id
    embedder_manager = rag2f_instance.optimus_prime
    if not embedder_manager.has(plugin.id):
        embedder_manager.register(plugin.id, MockEmbedder())

    repo_manager = rag2f_instance.xfiles
    repo_id = f"{plugin.id}_repository"
    if not repo_manager.has(repo_id):
        repo = MockRepository(repo_id)
        repo_manager.register(repo_id, repo, meta={"origin": "mock_plugin"})


@plugin
def deactivated(plugin, rag2f_instance: RAG2F):
    embedder_manager = rag2f_instance.optimus_prime
    embedder_manager.unregister(plugin.id)

    repo_manager = rag2f_instance.xfiles
    repo_id = f"{plugin.id}_repository"
    repo_manager.unregister(repo_id)



