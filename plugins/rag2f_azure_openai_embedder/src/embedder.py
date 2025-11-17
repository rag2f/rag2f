
from typing import List, Sequence, Optional
import logging
from openai import AzureOpenAI
from rag2f.core.protocols.embedder import Embedder, Vector

logger = logging.getLogger(__name__)


class AzureOpenAIEmbedder:
    """Embedder for Azure OpenAI using the `openai` library (AzureOpenAI class).
    
    Configuration is managed through RAG2F's Spock configuration system.
    The plugin retrieves its configuration via the RAG2F instance using the plugin ID.
    
    Required configuration parameters:
      - azure_endpoint: e.g., 'https://<resource>.openai.azure.com'
      - api_key: Azure OpenAI API key
      - api_version: e.g., '2024-02-15-preview'
      - deployment: Name of the embedding model deployment
      - size: Dimension of the output vector
      - timeout: Request timeout (default: 30.0)
      - max_retries: Maximum number of retries (default: 2)
    
    Configuration can be provided via:
    1. JSON file (specified in RAG2F initialization)
    2. Environment variables with prefix RAG2F__PLUGINS__<PLUGIN_ID>__
    
    Example environment variables:
      RAG2F__PLUGINS__AZURE_OPENAI_EMBEDDER__AZURE_ENDPOINT=https://...
      RAG2F__PLUGINS__AZURE_OPENAI_EMBEDDER__API_KEY=sk-xxx
      RAG2F__PLUGINS__AZURE_OPENAI_EMBEDDER__API_VERSION=2024-02-15-preview
      RAG2F__PLUGINS__AZURE_OPENAI_EMBEDDER__DEPLOYMENT=text-embedding-ada-002
      RAG2F__PLUGINS__AZURE_OPENAI_EMBEDDER__SIZE=1536
    """

    def __init__(self, config: dict):
        """Initialize the embedder using a configuration dictionary.
        
        Args:
            config: Dictionary containing configuration parameters
        """
        self._config = config
        # Extract and validate required parameters
        self._azure_endpoint = config.get('azure_endpoint')
        self._api_key = config.get('api_key')
        self._api_version = config.get('api_version')
        self._deployment = config.get('deployment')
        self._size = config.get('size')
        # Optional parameters with defaults
        self._timeout = config.get('timeout', 90.0)
        self._max_retries = config.get('max_retries', 2)
        # Validate required parameters
        missing = []
        if not self._azure_endpoint:
            missing.append('azure_endpoint')
        if not self._api_key:
            missing.append('api_key')
        if not self._api_version:
            missing.append('api_version')
        if not self._deployment:
            missing.append('deployment')
        if not self._size:
            missing.append('size')
        if missing:
            raise ValueError(
                f"Missing required configuration parameters: {', '.join(missing)}. "
                "Provide them via JSON config file or environment variables."
            )
        # Ensure size is an integer
        try:
            self._size = int(self._size)
        except (ValueError, TypeError):
            raise ValueError(f"Parameter 'size' must be an integer, got: {self._size}")
        # Ensure timeout is a float
        try:
            self._timeout = float(self._timeout)
        except (ValueError, TypeError):
            raise ValueError(f"Parameter 'timeout' must be a number, got: {self._timeout}")
        # Ensure max_retries is an integer
        try:
            self._max_retries = int(self._max_retries)
        except (ValueError, TypeError):
            raise ValueError(f"Parameter 'max_retries' must be an integer, got: {self._max_retries}")
        # Initialize Azure OpenAI client
        self._client = AzureOpenAI(
            azure_endpoint=self._azure_endpoint,
            api_key=self._api_key,
            api_version=self._api_version,
            timeout=self._timeout,
            max_retries=self._max_retries,
        )
        logger.info(
            "AzureOpenAIEmbedder initialized with deployment '%s'",
            self._deployment
        )

    @property
    def size(self) -> int:
        """Return the embedding vector size."""
        return self._size

    def getEmbedding(self, text: str) -> Vector:
        """Generate embedding vector for the given text.
        
        Args:
            text: Input text to embed
        Returns:
            List of floats representing the embedding vector
        """
        try:
            resp = self._client.embeddings.create(
                model=self._deployment,
                input=text
            )
            return list(resp.data[0].embedding)
        except Exception as e:
            logger.error(
                "Error generating embedding: %s",
                e
            )
            raise
