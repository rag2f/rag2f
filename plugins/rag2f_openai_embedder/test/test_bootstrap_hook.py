import pytest

@pytest.mark.asyncio
async def test_bootstrap_embedders_called(rag2f_openai_embedder):
    # The embedders should be registered via OptimusPrime
    optimus = rag2f_openai_embedder.optimus_prime
    
    # Check that OptimusPrime is initialized
    assert optimus is not None, "OptimusPrime should be initialized"
    # Check that at least one embedder is registered (the hook should run even if config is missing)
    assert optimus.has("rag2f_openai_embedder"), f"'rag2f_openai_embedder' should be registered in embedders. Found keys: {optimus.list_keys()}"
