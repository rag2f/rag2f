import logging
from typing import Any, Optional, Dict
from dotenv import load_dotenv
from rag2f.core.johnny5.johnny5 import Johnny5
from rag2f.core.morpheus.morpheus import Morpheus
from rag2f.core.protocols import Embedder
from rag2f.core.spock.spock import Spock
from rag2f.core.optimus_prime.optimus_prime import OptimusPrime

logger = logging.getLogger(__name__)
load_dotenv()

class RAG2F:
    """Core facade for the RAG2F application.

    RAG2F delegates input handling to a Johnny5 instance. Johnny5 is a small
    helper class with deterministic, side-effect-free methods which makes unit
    testing of input handling easier.
    Each RAG2F instance maintains its own unique Morpheus instance for
    orchestrating knowledge transformations and Spock instance for configuration.
    """
    def __init__(self, plugins_folder: str | None = None, config_path: str | None = None):
        self.spock = Spock(config_path=config_path)
        self.johnny = Johnny5(rag2f_instance=self)
        self.morpheus = Morpheus(plugins_folder=plugins_folder)
        self.optimus_prime = OptimusPrime()
        logger.debug("RAG2F instance created.")

    @classmethod
    async def create(cls, *, plugins_folder: str | None = None, config_path: str | None = None, config: Optional[Dict[str, Any]] = None):
        """Factory method to create and initialize RAG2F.
        
        Args:
            plugins_folder: Path to plugins directory
            config_path: Path to JSON configuration file
        """
        instance = cls(plugins_folder=plugins_folder, config_path=config_path)
        # Load configuration first
        instance.spock.load(config=config)
        # Then discover and activate plugins
        await instance.morpheus.find_plugins()
        # Bootstrap embedders from plugins
        await instance._bootstrap_embedders()
        return instance

    async def _bootstrap_embedders(self) -> None:
        """Bootstrap embedders loaded from plugins.

        Populates embedder_registry with embedders provided by plugins
        via the hook mechanism.
        """
        logger.debug("Bootstrapping embedders from loaded plugins...")
        embedders = self.morpheus.execute_hook(
            "rag2f_bootstrap_embedders",
            self.optimus_prime.registry,
            rag2f=self,
        )
        # Register embedders using OptimusPrime
        self.optimus_prime.register_batch(embedders)
        registry_size = len(self.optimus_prime.list_keys()) if self.optimus_prime else 0
        logger.debug(
            "Bootstrapping embedders completed. Registry size=%d.",
            registry_size
        )

    def input_text_foreground(self, text: str) -> str:
        processed = self.johnny.handle_text_foreground(text)
        logger.debug("RAG2F.input_text processed=%r", processed)
        return processed
