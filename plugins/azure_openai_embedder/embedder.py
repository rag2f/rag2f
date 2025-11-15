
from typing import List, Sequence, Optional
import json
import os
from pathlib import Path
from openai import AzureOpenAI
from rag2f.core.protocols.embedder import Embedder, Vector 


class AzureOpenAIEmbedder:
    """Embedder per Azure OpenAI usando la libreria `openai` (classe AzureOpenAI).
    
    La configurazione può essere fornita in tre modi (in ordine di priorità):
    1. Parametri espliciti passati al costruttore
    2. File JSON 'config.json' nella stessa directory del plugin
    3. Variabili d'ambiente (prefisso AZURE_OPENAI_)
    
    Parametri di configurazione:
      - azure_endpoint: es. 'https://<resource>.openai.azure.com'
      - api_key: AZURE_OPENAI_API_KEY
      - api_version: es. '2024-02-15-preview'
      - deployment: nome del deployment del modello di embedding
      - size: dimensione dell'output del vettore
      - timeout: timeout per le richieste (default: 30.0)
      - max_retries: numero massimo di retry (default: 2)
    """

    def __init__(self, *, config: Optional[dict] = None, config_file: Optional[str] = None) -> None:
        """
        Inizializza l'embedder SOLO da file di configurazione, variabili d'ambiente, o passando direttamente un oggetto config (dict).
        Args:
            config: dizionario di configurazione (stessa struttura di config.json)
            config_file: path al file di configurazione JSON (default: config.json nella stessa directory)
        """
        if config is not None:
            cfg = config
        else:
            cfg = self._load_config(config_file)
        self._size = cfg.get('size')
        self._deployment = cfg.get('deployment')
        endpoint = cfg.get('azure_endpoint')
        key = cfg.get('api_key')
        version = cfg.get('api_version')
        timeout_val = cfg.get('timeout', 30.0)
        max_retries_val = cfg.get('max_retries', 2)
        # Validazione parametri obbligatori
        if not all([endpoint, key, version, self._deployment, self._size]):
            missing = []
            if not endpoint: missing.append('azure_endpoint')
            if not key: missing.append('api_key')
            if not version: missing.append('api_version')
            if not self._deployment: missing.append('deployment')
            if not self._size: missing.append('size')
            raise ValueError(
                f"Parametri mancanti: {', '.join(missing)}. "
                "Forniscili tramite config.json, variabili d'ambiente o oggetto config."
            )
        self._client = AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=key,
            api_version=version,
            timeout=timeout_val,
            max_retries=max_retries_val,
        )
    
    def _load_config(self, config_file: Optional[str] = None) -> dict:
        """Carica la configurazione da file JSON o variabili d'ambiente.
        
        Args:
            config_file: Path al file JSON di configurazione
            
        Returns:
            Dizionario con i parametri di configurazione
        """
        config = {}
        
        # 1. Prova a caricare da file JSON
        if config_file is None:
            # Default: config.json nella stessa directory del file embedder.py
            plugin_dir = Path(__file__).parent
            config_file = plugin_dir / 'config.json'
        else:
            config_file = Path(config_file)
        
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
            except json.JSONDecodeError as e:
                raise ValueError(f"Errore nel parsing del file JSON {config_file}: {e}")
        
        # 2. Fallback a variabili d'ambiente (sovrascrivono solo se non presenti in config)
        env_mapping = {
            'azure_endpoint': 'AZURE_OPENAI_ENDPOINT',
            'api_key': 'AZURE_OPENAI_API_KEY',
            'api_version': 'AZURE_OPENAI_API_VERSION',
            'deployment': 'AZURE_OPENAI_DEPLOYMENT',
            'size': 'AZURE_OPENAI_SIZE',
            'timeout': 'AZURE_OPENAI_TIMEOUT',
            'max_retries': 'AZURE_OPENAI_MAX_RETRIES',
        }
        
        for config_key, env_var in env_mapping.items():
            if config_key not in config and env_var in os.environ:
                value = os.environ[env_var]
                # Converti tipi numerici
                if config_key in ('size', 'max_retries'):
                    config[config_key] = int(value)
                elif config_key == 'timeout':
                    config[config_key] = float(value)
                else:
                    config[config_key] = value
        
        return config

    @property
    def size(self) -> int:
        return self._size

    def getEmbedding(self, text: str) -> Vector:
        resp = self._client.embeddings.create(model=self._deployment, input=text)
        return list(resp.data[0].embedding)
