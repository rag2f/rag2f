import sys
import os
# Ensure `src` is on sys.path so imports like `from rag2f.core...` resolve during tests
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
if os.path.isdir(SRC):
	sys.path.insert(0, SRC)
sys.path.insert(0, ROOT)

# # Add workspace root for absolute plugin imports
# WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
# if WORKSPACE_ROOT not in sys.path:
# 	sys.path.insert(0, WORKSPACE_ROOT)

from plugins.rag2f_azure_openai_embedder.src.plugin_context import reset_plugin_id
from rag2f.core.rag2f import RAG2F
import pytest
import pytest_asyncio
from rich.traceback import install
from rag2f.core.morpheus.morpheus import Morpheus
from rag2f.core.spock.spock import Spock
from tests.utils import PATH_MOCK 




# Enable readable tracebacks in development / test environments.
# Can be disabled with PYTEST_RICH=0
if os.getenv("PYTEST_RICH", "1") == "1":
	install(
		show_locals=True,     # show local variables for each frame
		width=None,           # use terminal width
		word_wrap=True,       # wrap long lines
		extra_lines=1,        # some context around lines
		suppress=["/usr/lib/python3","site-packages"],  # hide "noisy" third-party frames
	)

import logging
logging.basicConfig(level=logging.DEBUG)

@pytest_asyncio.fixture(scope="session")
async def rag2f_azure_openai_embedder():	
	config = Spock.default_config()
	config["plugins"]["rag2f_azure_openai_embedder"] = {
		"azure_endpoint": "https://your-resource.openai.azure.com",
		"api_key": "your-api-key-here",
		"api_version": "2024-02-15-preview",
		"deployment": "text-embedding-ada-002",
		"size": 1536
	}
	
	instance = await RAG2F.create(plugins_folder=f"plugins/",config=config, config_path="plugins/test.json")
	
	# Reset AFTER to prevent contaminating subsequent tests
	reset_plugin_id()
	
	return instance