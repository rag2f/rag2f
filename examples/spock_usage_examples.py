"""
Example: Using Spock Configuration System with RAG2F

This example demonstrates how to use Spock to configure RAG2F and plugins.
"""

import asyncio
import logging
from rag2f.core.rag2f import RAG2F

# Configure logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def example_json_config():
    """Example 1: Using JSON configuration file."""
    print("\n" + "="*70)
    print("EXAMPLE 1: JSON Configuration")
    print("="*70)
    
    # Create RAG2F with JSON configuration
    # The config.json file contains all settings for RAG2F and plugins
    rag2f = await RAG2F.create(config_path="config.example.json")
    
    # Access core RAG2F configuration
    embedder_standard = rag2f.spock.get_rag2f_config("embedder_standard")
    log_level = rag2f.spock.get_rag2f_config("log_level")
    
    print(f"Standard embedder: {embedder_standard}")
    print(f"Log level: {log_level}")
    
    # Access plugin configuration
    azure_config = rag2f.spock.get_plugin_config("azure_openai_embedder")
    print(f"Azure OpenAI config keys: {list(azure_config.keys())}")
    
    # Get all configuration
    all_config = rag2f.spock.get_all_config()
    print(f"Total plugins configured: {len(all_config.get('plugins', {}))}")


async def example_env_config():
    """Example 2: Using environment variables."""
    print("\n" + "="*70)
    print("EXAMPLE 2: Environment Variables Configuration")
    print("="*70)
    
    import os
    
    # Set configuration via environment variables
    os.environ["RAG2F__RAG2F__EMBEDDER_STANDARD"] = "custom_embedder"
    os.environ["RAG2F__RAG2F__MAX_RETRIES"] = "5"
    os.environ["RAG2F__PLUGINS__MY_PLUGIN__API_KEY"] = "secret-key-123"
    os.environ["RAG2F__PLUGINS__MY_PLUGIN__TIMEOUT"] = "45.0"
    
    try:
        # Create RAG2F without JSON config - uses env vars only
        rag2f = await RAG2F.create()
        
        # Access configuration from env vars
        embedder = rag2f.spock.get_rag2f_config("embedder_standard")
        max_retries = rag2f.spock.get_rag2f_config("max_retries")
        
        print(f"Embedder from env: {embedder}")
        print(f"Max retries from env: {max_retries} (type: {type(max_retries).__name__})")
        
        # Access plugin config from env
        plugin_api_key = rag2f.spock.get_plugin_config("my_plugin", "api_key")
        plugin_timeout = rag2f.spock.get_plugin_config("my_plugin", "timeout")
        
        print(f"Plugin API key: {plugin_api_key}")
        print(f"Plugin timeout: {plugin_timeout} (type: {type(plugin_timeout).__name__})")
        
    finally:
        # Clean up environment variables
        del os.environ["RAG2F__RAG2F__EMBEDDER_STANDARD"]
        del os.environ["RAG2F__RAG2F__MAX_RETRIES"]
        del os.environ["RAG2F__PLUGINS__MY_PLUGIN__API_KEY"]
        del os.environ["RAG2F__PLUGINS__MY_PLUGIN__TIMEOUT"]


async def example_mixed_config():
    """Example 3: Mixing JSON and environment variables (env overrides)."""
    print("\n" + "="*70)
    print("EXAMPLE 3: Mixed Configuration (JSON + ENV)")
    print("="*70)
    
    import os
    
    # Set an environment variable that will override JSON
    os.environ["RAG2F__RAG2F__EMBEDDER_STANDARD"] = "env_override_embedder"
    
    try:
        # Create RAG2F with both JSON and env vars
        rag2f = await RAG2F.create(config_path="config.example.json")
        
        # This value comes from env var (overrides JSON)
        embedder = rag2f.spock.get_rag2f_config("embedder_standard")
        print(f"Embedder (env overrides JSON): {embedder}")
        
        # This value comes from JSON (no env var override)
        log_level = rag2f.spock.get_rag2f_config("log_level")
        print(f"Log level (from JSON): {log_level}")
        
    finally:
        del os.environ["RAG2F__RAG2F__EMBEDDER_STANDARD"]


async def example_multiple_instances():
    """Example 4: Multiple RAG2F instances with different configurations."""
    print("\n" + "="*70)
    print("EXAMPLE 4: Multiple RAG2F Instances")
    print("="*70)
    
    # Create first instance with one configuration
    rag2f1 = await RAG2F.create(config_path="config.example.json")
    
    # Set runtime configuration for second instance via env
    import os
    os.environ["RAG2F__RAG2F__EMBEDDER_STANDARD"] = "instance2_embedder"
    
    try:
        # Create second instance (will use env var)
        rag2f2 = await RAG2F.create()
        
        # Each instance has its own configuration
        config1 = rag2f1.spock.get_rag2f_config("embedder_standard")
        config2 = rag2f2.spock.get_rag2f_config("embedder_standard")
        
        print(f"Instance 1 embedder: {config1}")
        print(f"Instance 2 embedder: {config2}")
        print(f"Configurations are isolated: {config1 != config2}")
        
        # Verify they are different Spock instances
        print(f"Different Spock instances: {rag2f1.spock is not rag2f2.spock}")
        
    finally:
        del os.environ["RAG2F__RAG2F__EMBEDDER_STANDARD"]


async def example_default_values():
    """Example 5: Using default values for missing configuration."""
    print("\n" + "="*70)
    print("EXAMPLE 5: Default Values")
    print("="*70)
    
    # Create RAG2F without any configuration
    rag2f = await RAG2F.create()
    
    # Get values with defaults (they don't exist in config)
    timeout = rag2f.spock.get_rag2f_config("timeout", default=30.0)
    debug = rag2f.spock.get_plugin_config("my_plugin", "debug", default=False)
    
    print(f"Timeout (default): {timeout}")
    print(f"Debug mode (default): {debug}")


async def example_runtime_modification():
    """Example 6: Runtime configuration modification."""
    print("\n" + "="*70)
    print("EXAMPLE 6: Runtime Modification")
    print("="*70)
    
    rag2f = await RAG2F.create()
    
    # Set configuration at runtime (not persisted)
    rag2f.spock.set_rag2f_config("dynamic_setting", "runtime_value")
    rag2f.spock.set_plugin_config("runtime_plugin", "feature_flag", True)
    
    # Retrieve runtime values
    dynamic = rag2f.spock.get_rag2f_config("dynamic_setting")
    feature = rag2f.spock.get_plugin_config("runtime_plugin", "feature_flag")
    
    print(f"Dynamic setting: {dynamic}")
    print(f"Feature flag: {feature}")
    print("(Note: These are runtime-only and won't be persisted)")


async def main():
    """Run all examples."""
    print("\n" + "="*70)
    print("RAG2F SPOCK CONFIGURATION SYSTEM - EXAMPLES")
    print("="*70)
    
    try:
        await example_json_config()
    except Exception as e:
        logger.error(f"Example 1 failed: {e}")
    
    try:
        await example_env_config()
    except Exception as e:
        logger.error(f"Example 2 failed: {e}")
    
    try:
        await example_mixed_config()
    except Exception as e:
        logger.error(f"Example 3 failed: {e}")
    
    try:
        await example_multiple_instances()
    except Exception as e:
        logger.error(f"Example 4 failed: {e}")
    
    try:
        await example_default_values()
    except Exception as e:
        logger.error(f"Example 5 failed: {e}")
    
    try:
        await example_runtime_modification()
    except Exception as e:
        logger.error(f"Example 6 failed: {e}")
    
    print("\n" + "="*70)
    print("All examples completed!")
    print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
