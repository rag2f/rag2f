import logging
from typing import Optional
from dotenv import load_dotenv
from rag2f.core.johnny5.johnny5 import Johnny5
from rag2f.core.morpheus.morpheus import Morpheus
from rag2f.core.protocols import Embedder
from rag2f.core.spock.spock import Spock

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
        # Dictionary mapping strings to objects implementing Embedder
        self.embedder_registry: dict[str, Embedder] = {}
        logger.debug("RAG2F instance created.")

    @classmethod
    async def create(cls, plugins_folder: str | None = None, config_path: str | None = None):
        """Factory method to create and initialize RAG2F.
        
        Args:
            plugins_folder: Path to plugins directory
            config_path: Path to JSON configuration file
        """
        instance = cls(plugins_folder=plugins_folder, config_path=config_path)
        # Load configuration first
        instance.spock.load()
        # Then discover and activate plugins
        await instance.morpheus.find_plugins()
        # Bootstrap embedders from plugins
        await instance._bootstrap_embedders()
        return instance

    async def _bootstrap_embedders(self, *, allow_override: bool = False) -> None:
        """Bootstrap embedders loaded from plugins.

        Populates embedder_registry with embedders provided by plugins
        via the hook mechanism.
        """
        logger.debug("Bootstrapping embedders from loaded plugins...")
        embedders = self.morpheus.execute_hook(
            "rag2f_bootstrap_embedders",
            self.embedder_registry,
            rag2f=self,
        )
        # Normalize: accept None => {} and check for mapping
        if embedders is None:
            embedders = {}
        if not hasattr(embedders, "items"):
            raise TypeError(
                "The 'rag2f_bootstrap_embedders' hook must return a mapping (e.g., dict)."
            )
        # Copy-on-write: work on a copy, then swap the reference
        new_registry: dict[str, Embedder] = dict(self.embedder_registry)
        # Single pass: validate (key/value) + override policy + insert
        for key, embedder in embedders.items():
            # Validate key
            if not isinstance(key, str) or not key.strip():
                raise ValueError(f"Invalid embedder key: {key!r}")
            # Protocol compliance
            if not isinstance(embedder, Embedder):
                raise TypeError(
                    f"Embedder '{key}' does not implement the Embedder protocol"
                )
            # Override policy
            if not allow_override and key in new_registry:
                raise ValueError(
                    f"Override not allowed for already present key: {key!r}"
                )
            # Insert into the new copy
            new_registry[key] = embedder
        # Atomic swap of the reference (readers never see partial states)
        self.embedder_registry = new_registry
        logger.debug(
            "Bootstrapping embedders completed. Registry size=%d (+%d from hook).",
            len(self.embedder_registry),
            len(embedders),
        )

    def input_text_foreground(self, text: str) -> str:
        processed = self.johnny.handle_text_foreground(text)
        logger.debug("RAG2F.input_text processed=%r", processed)
        print(f"Processing text: {processed}")
        return processed
