"""Bootstrap hook for Azure OpenAI Embedder plugin.

This hook demonstrates how to use Spock configuration in a plugin.
"""

import logging
from rag2f.core.morpheus.decorators import hook

logger = logging.getLogger(__name__)


@hook("rag2f_bootstrap_embedders", priority=10)
def bootstrap_azure_openai_embedder(embedders_registry, rag2f):
    """Bootstrap Azure OpenAI embedder from Spock configuration.
    
    This hook loads the AzureOpenAIEmbedder using configuration from
    Spock (either JSON or environment variables).
    
    Configuration is retrieved using the plugin ID: 'azure_openai_embedder'
    
    Required configuration:
    - azure_endpoint: Azure OpenAI endpoint URL
    - api_key: API key for authentication
    - api_version: API version
    - deployment: Model deployment name
    - size: Embedding vector dimension
    
    Example JSON configuration:
    {
      "plugins": {
        "azure_openai_embedder": {
          "azure_endpoint": "https://your-resource.openai.azure.com",
          "api_key": "sk-...",
          "api_version": "2024-02-15-preview",
          "deployment": "text-embedding-ada-002",
          "size": 1536
        }
      }
    }
    
    Example environment variables:
    RAG2F__PLUGINS__AZURE_OPENAI_EMBEDDER__AZURE_ENDPOINT=https://...
    RAG2F__PLUGINS__AZURE_OPENAI_EMBEDDER__API_KEY=sk-...
    RAG2F__PLUGINS__AZURE_OPENAI_EMBEDDER__API_VERSION=2024-02-15-preview
    RAG2F__PLUGINS__AZURE_OPENAI_EMBEDDER__DEPLOYMENT=text-embedding-ada-002
    RAG2F__PLUGINS__AZURE_OPENAI_EMBEDDER__SIZE=1536
    
    Args:
        embedders_registry: Dictionary to populate with embedders
        rag2f: RAG2F instance providing access to Spock configuration
        
    Returns:
        Updated embedders_registry with Azure OpenAI embedder
    """
    plugin_id = "azure_openai_embedder"
    
    # Check if configuration exists for this plugin
    config = rag2f.spock.get_plugin_config(plugin_id)
    
    if not config:
        logger.warning(
            "No configuration found for plugin '%s'. "
            "Embedder will not be registered. "
            "Provide configuration via JSON or environment variables.",
            plugin_id
        )
        return embedders_registry
    
    try:
        # Import embedder (lazy import to avoid issues if dependencies not installed)
        from plugins.azure_openai_embedder.embedder import AzureOpenAIEmbedder
        
        # Initialize embedder with Spock configuration
        embedder = AzureOpenAIEmbedder(rag2f=rag2f, plugin_id=plugin_id)
        
        # Register embedder with a key
        # You can use the key from config or a default one
        embedder_key = rag2f.spock.get_rag2f_config("embedder_standard", default="azure_openai")
        
        embedders_registry[embedder_key] = embedder
        
        logger.info(
            "Azure OpenAI embedder registered as '%s' (size=%d, deployment=%s)",
            embedder_key,
            embedder.size,
            config.get("deployment")
        )
        
    except ImportError as e:
        logger.error(
            "Failed to import AzureOpenAIEmbedder. "
            "Ensure 'openai' package is installed: %s",
            e
        )
    except ValueError as e:
        logger.error(
            "Failed to initialize AzureOpenAIEmbedder due to configuration error: %s",
            e
        )
    except Exception as e:
        logger.error(
            "Unexpected error while bootstrapping Azure OpenAI embedder: %s",
            e,
            exc_info=True
        )
    
    return embedders_registry
