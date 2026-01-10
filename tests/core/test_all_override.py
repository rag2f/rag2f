from rag2f.core.protocols.embedder import Embedder


def test_plugin_override_registers_embedder(rag2f):
    assert rag2f.optimus_prime.has("mock_plugin"), "mock_plugin not found in registry"
    mock_embedder = rag2f.optimus_prime.get("mock_plugin")
    assert isinstance(mock_embedder, Embedder), "mock_plugin override should expose a valid Embedder"
    emb = mock_embedder.getEmbedding("test input")
    assert emb == [0.1, 0.2, 0.3], f"Unexpected embedding: {emb}"
