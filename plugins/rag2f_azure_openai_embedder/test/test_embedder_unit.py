"""
Unit tests for AzureOpenAIEmbedder.

Philosophy: Test YOUR code, not the OpenAI SDK.

These tests verify:
1. Configuration validation (YOUR logic)
2. Correct parameters passed to client (YOUR integration)
3. Custom error handling (if any)

We DON'T test:
- HTTP request/response format (that's OpenAI SDK's job)
- API error types (that's OpenAI SDK's job)
- Response parsing (mostly SDK's job)
"""
import pytest
from unittest.mock import patch, MagicMock


class TestAzureOpenAIEmbedderConfiguration:
    """Test configuration validation - this IS your code."""
    
    def test_missing_required_config_raises_error(self):
        """Verify YOUR validation logic catches missing params."""
        from plugins.rag2f_azure_openai_embedder.src.embedder import AzureOpenAIEmbedder
        
        incomplete_configs = [
            {},  # All missing
            {"azure_endpoint": "https://x.openai.azure.com"},  # Missing most
            {
                "azure_endpoint": "https://x.openai.azure.com",
                "api_key": "key",
                "api_version": "2024-02-15-preview",
                # Missing deployment and size
            },
        ]
        
        for config in incomplete_configs:
            with pytest.raises(ValueError) as exc_info:
                AzureOpenAIEmbedder(config)
            assert "Missing required" in str(exc_info.value)
    
    def test_invalid_size_type_raises_error(self):
        """Verify YOUR validation catches invalid size type."""
        from plugins.rag2f_azure_openai_embedder.src.embedder import AzureOpenAIEmbedder
        
        config = {
            "azure_endpoint": "https://x.openai.azure.com",
            "api_key": "key",
            "api_version": "2024-02-15-preview",
            "deployment": "model",
            "size": "not-a-number"  # Invalid
        }
        
        with pytest.raises(ValueError) as exc_info:
            AzureOpenAIEmbedder(config)
        assert "size" in str(exc_info.value).lower()
    
    def test_valid_config_initializes_correctly(self):
        """Verify embedder initializes with valid config."""
        from plugins.rag2f_azure_openai_embedder.src.embedder import AzureOpenAIEmbedder
        
        config = {
            "azure_endpoint": "https://test.openai.azure.com",
            "api_key": "test-key",
            "api_version": "2024-02-15-preview",
            "deployment": "text-embedding-ada-002",
            "size": 1536
        }
        
        with patch('plugins.rag2f_azure_openai_embedder.src.embedder.AzureOpenAI'):
            embedder = AzureOpenAIEmbedder(config)
            assert embedder.size == 1536
    
    def test_size_property_returns_configured_value(self):
        """Verify size property returns what was configured."""
        from plugins.rag2f_azure_openai_embedder.src.embedder import AzureOpenAIEmbedder
        
        for expected_size in [512, 1536, 3072]:
            config = {
                "azure_endpoint": "https://test.openai.azure.com",
                "api_key": "key",
                "api_version": "2024-02-15-preview",
                "deployment": "model",
                "size": expected_size
            }
            
            with patch('plugins.rag2f_azure_openai_embedder.src.embedder.AzureOpenAI'):
                embedder = AzureOpenAIEmbedder(config)
                assert embedder.size == expected_size


class TestAzureOpenAIEmbedderContract:
    """
    Test the CONTRACT with OpenAI SDK.
    
    This verifies YOUR code calls the SDK correctly.
    This IS valuable because it catches:
    - Typos in parameter names
    - Wrong parameter order
    - Forgetting to pass required params
    """
    
    @pytest.fixture
    def mock_client(self):
        """Create a mock OpenAI client."""
        with patch('plugins.rag2f_azure_openai_embedder.src.embedder.AzureOpenAI') as MockClient:
            mock_instance = MagicMock()
            mock_response = MagicMock()
            mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
            mock_instance.embeddings.create.return_value = mock_response
            MockClient.return_value = mock_instance
            yield MockClient, mock_instance
    
    def test_client_initialized_with_correct_params(self, mock_client):
        """Verify AzureOpenAI client receives correct init params."""
        from plugins.rag2f_azure_openai_embedder.src.embedder import AzureOpenAIEmbedder
        
        MockClient, _ = mock_client
        
        config = {
            "azure_endpoint": "https://my-resource.openai.azure.com",
            "api_key": "my-secret-key",
            "api_version": "2024-02-15-preview",
            "deployment": "my-deployment",
            "size": 1536,
            "timeout": 60.0,
            "max_retries": 3
        }
        
        AzureOpenAIEmbedder(config)
        
        # Verify YOUR code passes the right params to the SDK
        MockClient.assert_called_once_with(
            azure_endpoint="https://my-resource.openai.azure.com",
            api_key="my-secret-key",
            api_version="2024-02-15-preview",
            timeout=60.0,
            max_retries=3
        )
    
    def test_embedding_create_called_with_correct_params(self, mock_client):
        """Verify embeddings.create() receives correct params."""
        from plugins.rag2f_azure_openai_embedder.src.embedder import AzureOpenAIEmbedder
        
        _, mock_instance = mock_client
        
        config = {
            "azure_endpoint": "https://test.openai.azure.com",
            "api_key": "key",
            "api_version": "2024-02-15-preview",
            "deployment": "my-embedding-model",
            "size": 1536
        }
        
        embedder = AzureOpenAIEmbedder(config)
        embedder.getEmbedding("Hello, world!")
        
        # Verify YOUR code passes the right params
        mock_instance.embeddings.create.assert_called_once_with(
            model="my-embedding-model",
            input="Hello, world!"
        )
    
    def test_returns_embedding_as_list(self, mock_client):
        """Verify YOUR code converts embedding to list."""
        from plugins.rag2f_azure_openai_embedder.src.embedder import AzureOpenAIEmbedder
        
        _, mock_instance = mock_client
        
        # SDK might return various array-like types
        expected = [0.1, 0.2, 0.3]
        mock_instance.embeddings.create.return_value.data[0].embedding = expected
        
        config = {
            "azure_endpoint": "https://test.openai.azure.com",
            "api_key": "key",
            "api_version": "2024-02-15-preview",
            "deployment": "model",
            "size": 3
        }
        
        embedder = AzureOpenAIEmbedder(config)
        result = embedder.getEmbedding("test")
        
        # Verify it's a list (YOUR code does `list(...)`)
        assert isinstance(result, list)
        assert result == expected


class TestAzureOpenAIEmbedderEdgeCases:
    """Test edge cases that YOUR code should handle."""
    
    def test_empty_string_input(self):
        """Verify empty string is passed through (not rejected by YOUR code)."""
        from plugins.rag2f_azure_openai_embedder.src.embedder import AzureOpenAIEmbedder
        
        with patch('plugins.rag2f_azure_openai_embedder.src.embedder.AzureOpenAI') as MockClient:
            mock_instance = MagicMock()
            mock_instance.embeddings.create.return_value.data = [
                MagicMock(embedding=[0.0] * 1536)
            ]
            MockClient.return_value = mock_instance
            
            config = {
                "azure_endpoint": "https://test.openai.azure.com",
                "api_key": "key",
                "api_version": "2024-02-15-preview",
                "deployment": "model",
                "size": 1536
            }
            
            embedder = AzureOpenAIEmbedder(config)
            result = embedder.getEmbedding("")  # Empty string
            
            # Verify YOUR code doesn't block empty strings
            mock_instance.embeddings.create.assert_called_once_with(
                model="model",
                input=""
            )
    
    def test_sdk_exception_propagates(self):
        """Verify SDK exceptions bubble up (YOUR code re-raises)."""
        from plugins.rag2f_azure_openai_embedder.src.embedder import AzureOpenAIEmbedder
        
        with patch('plugins.rag2f_azure_openai_embedder.src.embedder.AzureOpenAI') as MockClient:
            mock_instance = MagicMock()
            mock_instance.embeddings.create.side_effect = Exception("API Error")
            MockClient.return_value = mock_instance
            
            config = {
                "azure_endpoint": "https://test.openai.azure.com",
                "api_key": "key",
                "api_version": "2024-02-15-preview",
                "deployment": "model",
                "size": 1536
            }
            
            embedder = AzureOpenAIEmbedder(config)
            
            with pytest.raises(Exception) as exc_info:
                embedder.getEmbedding("test")
            
            assert "API Error" in str(exc_info.value)


# =============================================================================
# OPTIONAL: Contract tests with real HTTP (keep if you want extra safety)
# =============================================================================
# These test the FULL integration but are essentially testing the SDK.
# Keep them only if:
# 1. You want to catch SDK breaking changes early
# 2. You're doing something non-standard with the SDK

import respx
import httpx


class TestAzureOpenAIEmbedderHTTPIntegration:
    """
    OPTIONAL: Full HTTP integration tests.
    
    These test the OpenAI SDK more than your code.
    Consider removing if you trust the SDK and want faster tests.
    """
    
    @respx.mock
    def test_full_integration_smoke_test(self):
        """
        One smoke test to verify the full stack works.
        
        This catches: SDK version incompatibilities, breaking changes.
        """
        from plugins.rag2f_azure_openai_embedder.src.embedder import AzureOpenAIEmbedder
        
        config = {
            "azure_endpoint": "https://test.openai.azure.com",
            "api_key": "test-key",
            "api_version": "2024-02-15-preview",
            "deployment": "text-embedding-ada-002",
            "size": 1536,
            "max_retries": 0
        }
        
        mock_response = {
            "object": "list",
            "data": [{"object": "embedding", "index": 0, "embedding": [0.1] * 1536}],
            "model": "text-embedding-ada-002",
            "usage": {"prompt_tokens": 8, "total_tokens": 8}
        }
        
        respx.post(url__regex=r".*").mock(
            return_value=httpx.Response(200, json=mock_response)
        )
        
        embedder = AzureOpenAIEmbedder(config)
        result = embedder.getEmbedding("Hello")
        
        assert len(result) == 1536
        assert isinstance(result, list)
