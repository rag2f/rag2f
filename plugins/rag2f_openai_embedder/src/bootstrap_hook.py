
import logging
from rag2f.core.morpheus.decorators import hook, PillHook
from .plugin_context import get_plugin_id

logger = logging.getLogger(__name__)


@hook("rag2f_bootstrap_embedders", priority=10)
def bootstrap_openai_embedder(embedders_registry, rag2f):
    """Bootstrap OpenAI embedder from Spock configuration.
    
    This hook loads the OpenAIEmbedder using configuration from
    Spock (either JSON or environment variables).
    
    Configuration is retrieved using the plugin ID: 'openai_embedder'
    
    Required configuration:
    - api_key: OpenAI API key
    - model: Model name (e.g., 'text-embedding-3-small', 'text-embedding-3-large', 'text-embedding-ada-002')
    - size: Embedding vector dimension
    
    Example JSON configuration:
    {
      "plugins": {
        "openai_embedder": {
          "api_key": "sk-...",
          "model": "text-embedding-3-small",
          "size": 1536
        }
      }
    }
    
    Example environment variables:
    RAG2F__PLUGINS__OPENAI_EMBEDDER__API_KEY=sk-...
    RAG2F__PLUGINS__OPENAI_EMBEDDER__MODEL=text-embedding-3-small
    RAG2F__PLUGINS__OPENAI_EMBEDDER__SIZE=1536
    
    Args:
        embedders_registry: Dictionary to populate with embedders
        rag2f: RAG2F instance providing access to Spock configuration
        
    Returns:
        Updated embedders_registry with OpenAI embedder
    """

    logger.debug(f"🔍 Hook object: {bootstrap_openai_embedder}")  

    # Get plugin_id from the RAG2F instance
    plugin_id = get_plugin_id(rag2f)
    
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
        from .embedder import OpenAIEmbedder
        
        # Initialize embedder with Spock configuration
        embedder = OpenAIEmbedder(config)
        
        embedders_registry[plugin_id] = embedder
        
        logger.info(
            "OpenAI embedder registered as '%s' (size=%d, model=%s)",
            plugin_id,
            embedder.size,
            config.get("model")
        )
        
    except ImportError as e:
        logger.error(
            "Failed to import OpenAIEmbedder. "
            "Ensure 'openai' package is installed: %s",
            e
        )
    except ValueError as e:
        logger.error(
            "Failed to initialize OpenAIEmbedder due to configuration error: %s",
            e
        )
    except Exception as e:
        logger.error(
            "Unexpected error bootstrapping OpenAI embedder: %s",
            e
        )
    
    return embedders_registry
