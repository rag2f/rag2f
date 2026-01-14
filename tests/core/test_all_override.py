"""Tests for plugin override registration and deactivation."""

from rag2f.core.protocols.embedder import Embedder
from rag2f.core.xfiles import minimal_crud_capabilities


def test_plugin_override_registers_embedder(rag2f):
    """Registering a plugin override should expose an embedder."""
    assert rag2f.optimus_prime.has("mock_plugin"), "mock_plugin not found in registry"
    mock_embedder = rag2f.optimus_prime.get("mock_plugin")
    assert isinstance(mock_embedder, Embedder), (
        "mock_plugin override should expose a valid Embedder"
    )
    emb = mock_embedder.getEmbedding("test input")
    assert emb == [0.1, 0.2, 0.3], f"Unexpected embedding: {emb}"


def test_plugin_override_registers_repository(rag2f):
    """Registering a plugin override should expose a repository."""
    repo_id = "mock_plugin_repository"
    assert rag2f.xfiles.has(repo_id), "mock_plugin repository not registered"
    repo = rag2f.xfiles.get(repo_id)
    assert repo is not None
    assert repo.name == repo_id
    assert repo.capabilities() == minimal_crud_capabilities()
    assert rag2f.xfiles.get_meta(repo_id) == {"origin": "mock_plugin"}


def test_plugin_override_handles_deactivation(rag2f):
    """Deactivation should unregister and activation should restore overrides."""
    repo_id = "mock_plugin_repository"
    plugin = rag2f.morpheus.plugins["mock_plugin"]

    plugin.deactivate()

    assert not rag2f.optimus_prime.has("mock_plugin"), "embedder should be removed on deactivate"
    assert not rag2f.xfiles.has(repo_id), "repository should be removed on deactivate"

    plugin.activate()

    assert rag2f.optimus_prime.has("mock_plugin"), "embedder should be re-registered"
    assert rag2f.xfiles.has(repo_id), "repository should be re-registered"
    assert rag2f.xfiles.get_meta(repo_id) == {"origin": "mock_plugin"}
