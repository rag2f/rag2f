"""Core RAG2F facade.

This module defines the main entry point used by applications and tests.
"""

import logging
from typing import Any

from dotenv import load_dotenv

from rag2f.core.a_team.a_team import ATeam
from rag2f.core.flux_capacitor.flux_capacitor import FluxCapacitor
from rag2f.core.indiana_jones.indiana_jones import IndianaJones
from rag2f.core.johnny5.johnny5 import Johnny5
from rag2f.core.morpheus.morpheus import Morpheus
from rag2f.core.observability import debug_event, observation_scope
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
        # Alias early for components that expect config_manager during construction.
        self.johnny5 = Johnny5(rag2f_instance=self)
        self.indiana_jones = IndianaJones(rag2f_instance=self)
        self.morpheus = Morpheus(self, plugins_folder=plugins_folder)
        self.a_team = ATeam(rag2f_instance=self, spock=self.spock)
        self.flux_capacitor = FluxCapacitor(rag2f_instance=self)
        self.optimus_prime = OptimusPrime(spock=self.spock)
        self.xfiles = XFiles(spock=self.spock)

        # Alias
        self.config_manager = self.spock
        self.input_manager = self.johnny5
        self.retrieve_manager = self.indiana_jones
        self.plugin_manager = self.morpheus
        self.agent_manager = self.a_team
        self.task_manager = self.flux_capacitor
        self.embedder_manager = self.optimus_prime
        self.repository_manager = self.xfiles
        debug_event(
            logger,
            "rag2f_initialized",
            plugins_folder=plugins_folder,
            config_path=config_path,
        )

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
        with observation_scope(component="rag2f.create"):
            debug_event(
                logger,
                "rag2f_create_start",
                plugins_folder=plugins_folder,
                config_path=config_path,
                config_provided=config is not None,
            )
            instance = cls.__new__(cls)  # bypass __init__
            instance._initialize(plugins_folder=plugins_folder, config_path=config_path)
            instance.spock.load(config=config)
            await instance.morpheus.find_plugins()
            debug_event(
                logger,
                "rag2f_create_complete",
                plugin_count=len(instance.morpheus.plugins),
            )
            return instance

    def input_text_foreground(self, text: str) -> str:
        """Process input text through the foreground pipeline.

        Args:
            text: User input text.

        Returns:
            The processed result.
        """
        with observation_scope(operation="input_text_foreground"):
            debug_event(
                logger,
                "rag2f_input_text_foreground_start",
                input_length=len(text) if text is not None else 0,
            )
            processed = self.johnny5.execute_handle_text_foreground(text)
            debug_event(
                logger,
                "rag2f_input_text_foreground_complete",
                status=processed.status,
                track_id=processed.track_id,
            )
            return processed
