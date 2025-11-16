

def _hook_rag2f_bootstrap_embedders(rag2f):
    # After bootstrap, mock_embedder must be present in the registry
    registry = rag2f.embedder_registry
    assert "mock_embedder" in registry, "mock_embedder not found in registry"
    mock = registry["mock_embedder"]
    # Check that it implements the Embedder protocol
    from rag2f.core.protocols.embedder import Embedder
    assert isinstance(mock, Embedder), "mock_embedder does not implement the Embedder protocol"
    # Check that it returns the expected embedding
    emb = mock.getEmbedding("test input")
    assert emb == [0.1, 0.2, 0.3], f"Unexpected embedding: {emb}"
