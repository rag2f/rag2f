import pytest

@pytest.mark.asyncio
async def test_bootstrap_embedders_called(rag2f):
    # The embedders_registry should be populated by the bootstrap hook
    embedders = getattr(rag2f, 'embedder_registry', None)
    # Accept both dict and object with keys
    assert embedders is not None, "Embedders registry should be initialized by bootstrap hook"
    # Check that at least one embedder is registered (the hook should run even if config is missing)
    assert isinstance(embedders, dict), "Embedders registry should be a dict"   
    assert "rag2f_azure_openai_embedder" in embedders, "'rag2f_azure_openai_embedder' should be registered in embedders"
