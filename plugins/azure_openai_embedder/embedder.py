
from typing import List, Sequence
from openai import AzureOpenAI
from rag2f.core.protocols.embedder import Embedder, Vector 


class AzureOpenAIEmbedder:
    """Embedder per Azure OpenAI usando la libreria `openai` (classe AzureOpenAI).
    
    Richiede:
      - azure_endpoint: es. 'https://<resource>.openai.azure.com'
      - api_key: AZURE_OPENAI_API_KEY
      - api_version: es. '2024-02-15-preview' (usa quella del tuo resource provider)
      - deployment: nome del deployment del modello di embedding (NON il nome del modello)
      - size: dimensione attesa dell'output
    """

    def __init__(
        self,
        *,
        azure_endpoint: str,
        api_key: str,
        api_version: str,
        deployment: str,
        size: int,
        timeout: float = 30.0,
        max_retries: int = 2,
    ) -> None:
        self._size = size
        self._deployment = deployment
        self._client = AzureOpenAI(
            azure_endpoint=azure_endpoint,
            api_key=api_key,
            api_version=api_version,
            timeout=timeout,
            max_retries=max_retries,
        )

    @property
    def size(self) -> int:
        return self._size

    def getEmbedding(self, text: str) -> Vector:
        resp = self._client.embeddings.create(model=self._deployment, input=text)
        return list(resp.data[0].embedding)
