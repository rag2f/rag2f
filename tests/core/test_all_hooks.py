

def test_hook_rag2f_bootstrap_embedders(rag2f):
    # After bootstrap, mock_embedder must be present in the registry
    assert rag2f.optimus_prime.has("mock_plugin"), "mock_plugin not found in registry"
    mock = rag2f.optimus_prime.get("mock_plugin")
    # Check that it implements the Embedder protocol
    from rag2f.core.protocols.embedder import Embedder
    assert isinstance(mock, Embedder), "mock_plugin does not implement the Embedder protocol"
    # Check that it returns the expected embedding
    emb = mock.getEmbedding("test input")
    assert emb == [0.1, 0.2, 0.3], f"Unexpected embedding: {emb}"
