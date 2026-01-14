"""Integration test for Spock configuration with RAG2F."""

import json
import os
import tempfile

import pytest

from rag2f.core.rag2f import RAG2F


class TestSpockRAG2FIntegration:
    """Test Spock integration with RAG2F."""

    @pytest.mark.asyncio
    async def test_multiple_rag2f_instances_isolated_config(self):
        """Test that multiple RAG2F instances have isolated Spock configurations."""
        config1_data = {"rag2f": {"embedder_default": "embedder1"}}

        config2_data = {"rag2f": {"embedder_default": "embedder2"}}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f1:
            json.dump(config1_data, f1)
            config1_path = f1.name

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f2:
            json.dump(config2_data, f2)
            config2_path = f2.name

        try:
            # Create two RAG2F instances with different configs
            rag2f1 = await RAG2F.create(config_path=config1_path)
            rag2f2 = await RAG2F.create(config_path=config2_path)

            # Each should have its own configuration
            assert rag2f1.spock.get_rag2f_config("embedder_default") == "embedder1"
            assert rag2f2.spock.get_rag2f_config("embedder_default") == "embedder2"

            # Verify they are different Spock instances
            assert rag2f1.spock is not rag2f2.spock
        finally:
            os.unlink(config1_path)
            os.unlink(config2_path)
