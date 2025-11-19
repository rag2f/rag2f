"""Integration test for Spock configuration with RAG2F."""

import os
import json
import tempfile
import pytest
from rag2f.core.rag2f import RAG2F


class TestSpockRAG2FIntegration:
    """Test Spock integration with RAG2F."""
    
    @pytest.mark.asyncio
    async def test_rag2f_with_json_config(self):
        """Test RAG2F initialization with JSON configuration."""
        config_data = {
            "rag2f": {
                "embedder_standard": "test_embedder",            },
            "plugins": {
                "test_plugin": {
                    "api_key": "test-key-123"
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_path = f.name
        
        try:
            # Create RAG2F with config
            rag2f = await RAG2F.create(config_path=config_path)
            
            # Verify Spock is loaded
            assert rag2f.spock.is_loaded
            
            # Verify configuration is accessible
            assert rag2f.spock.get_rag2f_config("embedder_standard") == "test_embedder"
            assert rag2f.spock.get_plugin_config("test_plugin", "api_key") == "test-key-123"
        finally:
            os.unlink(config_path)
    
    @pytest.mark.asyncio
    async def test_rag2f_with_env_config(self):
        """Test RAG2F initialization with environment variables."""
        os.environ["RAG2F__RAG2F__EMBEDDER_STANDARD"] = "env_embedder"
        os.environ["RAG2F__PLUGINS__MY_PLUGIN__API_KEY"] = "env-secret"
        
        try:
            rag2f = await RAG2F.create()
            
            assert rag2f.spock.is_loaded
            assert rag2f.spock.get_rag2f_config("embedder_standard") == "env_embedder"
            assert rag2f.spock.get_plugin_config("my_plugin", "api_key") == "env-secret"
        finally:
            del os.environ["RAG2F__RAG2F__EMBEDDER_STANDARD"]
            del os.environ["RAG2F__PLUGINS__MY_PLUGIN__API_KEY"]
    
    @pytest.mark.asyncio
    async def test_rag2f_config_priority(self):
        """Test that environment variables override JSON in RAG2F."""
        config_data = {
            "rag2f": {
                "embedder_standard": "json_embedder"
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_path = f.name
        
        os.environ["RAG2F__RAG2F__EMBEDDER_STANDARD"] = "env_embedder"
        
        try:
            rag2f = await RAG2F.create(config_path=config_path)
            
            # Environment should win
            assert rag2f.spock.get_rag2f_config("embedder_standard") == "env_embedder"
        finally:
            os.unlink(config_path)
            del os.environ["RAG2F__RAG2F__EMBEDDER_STANDARD"]
    
    @pytest.mark.asyncio
    async def test_multiple_rag2f_instances_isolated_config(self):
        """Test that multiple RAG2F instances have isolated Spock configurations."""
        config1_data = {
            "rag2f": {
                "embedder_standard": "embedder1"
            }
        }
        
        config2_data = {
            "rag2f": {
                "embedder_standard": "embedder2"
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f1:
            json.dump(config1_data, f1)
            config1_path = f1.name
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f2:
            json.dump(config2_data, f2)
            config2_path = f2.name
        
        try:
            # Create two RAG2F instances with different configs
            rag2f1 = await RAG2F.create(config_path=config1_path)
            rag2f2 = await RAG2F.create(config_path=config2_path)
            
            # Each should have its own configuration
            assert rag2f1.spock.get_rag2f_config("embedder_standard") == "embedder1"
            assert rag2f2.spock.get_rag2f_config("embedder_standard") == "embedder2"
            
            # Verify they are different Spock instances
            assert rag2f1.spock is not rag2f2.spock
        finally:
            os.unlink(config1_path)
            os.unlink(config2_path)
