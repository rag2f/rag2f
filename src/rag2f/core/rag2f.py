"""Core RAG2F facade.

This module defines the main entry point used by applications and tests.
"""

import logging
from typing import Any

from dotenv import load_dotenv

from rag2f.core.indiana_jones.indiana_jones import IndianaJones
from rag2f.core.johnny5.johnny5 import Johnny5
from rag2f.core.morpheus.morpheus import Morpheus
from rag2f.core.optimus_prime.optimus_prime import OptimusPrime
from rag2f.core.spock.spock import Spock
from rag2f.core.xfiles.xfiles import XFiles

logger = logging.getLogger(__name__)
load_dotenv()


class RAG2F:
    """Core facade for the RAG2F application."""

    def __init__(self, *args, **kwargs):
        """Prevent direct construction; use `await RAG2F.create(...)` instead."""
        raise RuntimeError("Use: instance = await RAG2F.create(...)")

    def _initialize(self, *, plugins_folder: str | None = None, config_path: str | None = None):
        """Initialize RAG2F internal components.

        Args:
            plugins_folder: Path to plugins directory
            config_path: Path to JSON configuration file
        """
        self.spock = Spock(config_path=config_path)
        self.johnny5 = Johnny5(rag2f_instance=self)
        self.indiana_jones = IndianaJones(rag2f_instance=self)
        self.morpheus = Morpheus(self, plugins_folder=plugins_folder)
        self.optimus_prime = OptimusPrime(spock=self.spock)
        self.xfiles = XFiles(spock=self.spock)

        # Alias
        self.config_manager = self.spock
        self.input_manager = self.johnny5
        self.retrieve_manager = self.indiana_jones
        self.plugin_manager = self.morpheus
        self.embedder_manager = self.optimus_prime
        self.repository_manager = self.xfiles
        logger.debug("RAG2F instance created.")

    @classmethod
    async def create(
        cls,
        *,
        plugins_folder: str | None = None,
        config_path: str | None = None,
        config: dict[str, Any] | None = None,
    ):
        """Factory method to create and initialize RAG2F.

        Args:
            plugins_folder: Path to plugins directory
            config_path: Path to JSON configuration file
            config: Optional configuration dictionary
        """
        instance = cls.__new__(cls)  # bypass __init__
        instance._initialize(plugins_folder=plugins_folder, config_path=config_path)
        # Load configuration first
        instance.spock.load(config=config)
        # Then discover and activate plugins
        await instance.morpheus.find_plugins()
        return instance

    def input_text_foreground(self, text: str) -> str:
        """Process input text through the foreground pipeline.

        Args:
            text: User input text.

        Returns:
            The processed result.
        """
        processed = self.johnny5.handle_text_foreground(text)
        logger.debug("RAG2F.input_text processed=%r", processed)
        return processed
