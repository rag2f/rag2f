import logging
from typing import Optional

from dotenv import load_dotenv

from rag2f.core.johnny5 import Johnny5
from rag2f.core.morpheus.morpheus import Morpheus

logger = logging.getLogger(__name__)
load_dotenv()


class RAG2F:
    """Core facade for the RAG2F application.

    RAG2F delegates input handling to a Johnny5 instance. Johnny5 is a small
    helper class with deterministic, side-effect-free methods which makes unit
    testing of input handling easier.
    
    Each RAG2F instance maintains its own unique Morpheus instance for
    orchestrating knowledge transformations.
    """

    def __init__(self, plugins_folder: str | None = None):
        self.johnny = Johnny5(rag2f_instance=self)
        self.morpheus = Morpheus(plugins_folder=plugins_folder)
        logger.debug("RAG2F instance created.")

    @classmethod
    async def create(cls, plugins_folder: str | None = None):
        """Factory method per creare e inizializzare RAG2F."""
        instance = cls(plugins_folder=plugins_folder)
        await instance.morpheus.find_plugins()
        return instance


    def input_text_foreground(self, text: str) -> str:
        processed = self.johnny.handle_text_foreground(text)
        logger.debug("RAG2F.input_text processed=%r", processed)
        print(f"Processing text: {processed}")
        return processed
