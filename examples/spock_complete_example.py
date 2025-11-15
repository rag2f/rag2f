"""
Complete Example: RAG2F with Spock Configuration and Azure OpenAI Embedder

This example shows a complete setup using:
- Spock configuration system
- Azure OpenAI Embedder plugin
- Both JSON and environment variable configuration

Prerequisites:
1. Set up your config.json or environment variables
2. Ensure openai package is installed: pip install openai
"""

import asyncio
import logging
import os
from rag2f.core.rag2f import RAG2F

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def example_with_json_config():
    """
    Example 1: Using JSON configuration file
    
    Create a config.json file with:
    {
      "rag2f": {
        "embedder_standard": "azure_openai"
      },
      "plugins": {
        "azure_openai_embedder": {
          "azure_endpoint": "https://your-resource.openai.azure.com",
          "api_key": "your-api-key",
          "api_version": "2024-02-15-preview",
          "deployment": "text-embedding-ada-002",
          "size": 1536
        }
      }
    }
    """
    print("\n" + "="*70)
    print("Example 1: JSON Configuration")
    print("="*70)
    
    try:
        # Initialize RAG2F with config file
        rag2f = await RAG2F.create(config_path="config.json")
        
        # Check if embedder was registered
        if "azure_openai" in rag2f.embedder_registry:
            embedder = rag2f.embedder_registry["azure_openai"]
            print(f"✓ Azure OpenAI embedder registered")
            print(f"  Vector size: {embedder.size}")
            
            # Try to generate an embedding
            test_text = "Hello, Spock configuration system!"
            embedding = embedder.getEmbedding(test_text)
            print(f"✓ Generated embedding for test text")
            print(f"  Embedding length: {len(embedding)}")
            print(f"  First 5 values: {embedding[:5]}")
        else:
            print("✗ Azure OpenAI embedder not registered")
            print("  Check your configuration")
            
    except FileNotFoundError:
        print("✗ config.json not found")
        print("  Create config.json from config.example.json")
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)


async def example_with_env_vars():
    """
    Example 2: Using environment variables
    
    Set these environment variables:
    export RAG2F__RAG2F__EMBEDDER_STANDARD=azure_openai
    export RAG2F__PLUGINS__AZURE_OPENAI_EMBEDDER__AZURE_ENDPOINT=https://...
    export RAG2F__PLUGINS__AZURE_OPENAI_EMBEDDER__API_KEY=sk-xxx
    export RAG2F__PLUGINS__AZURE_OPENAI_EMBEDDER__API_VERSION=2024-02-15-preview
    export RAG2F__PLUGINS__AZURE_OPENAI_EMBEDDER__DEPLOYMENT=text-embedding-ada-002
    export RAG2F__PLUGINS__AZURE_OPENAI_EMBEDDER__SIZE=1536
    """
    print("\n" + "="*70)
    print("Example 2: Environment Variables")
    print("="*70)
    
    # Set example environment variables (in production, these would be set externally)
    os.environ["RAG2F__RAG2F__EMBEDDER_STANDARD"] = "azure_openai"
    
    # Note: You need to set these with real values
    required_vars = [
        "RAG2F__PLUGINS__AZURE_OPENAI_EMBEDDER__AZURE_ENDPOINT",
        "RAG2F__PLUGINS__AZURE_OPENAI_EMBEDDER__API_KEY",
        "RAG2F__PLUGINS__AZURE_OPENAI_EMBEDDER__API_VERSION",
        "RAG2F__PLUGINS__AZURE_OPENAI_EMBEDDER__DEPLOYMENT",
        "RAG2F__PLUGINS__AZURE_OPENAI_EMBEDDER__SIZE",
    ]
    
    all_set = all(var in os.environ for var in required_vars)
    
    if not all_set:
        print("ℹ  Set these environment variables to run this example:")
        for var in required_vars:
            status = "✓" if var in os.environ else "✗"
            print(f"  {status} {var}")
        return
    
    try:
        # Initialize RAG2F (will use env vars)
        rag2f = await RAG2F.create()
        
        # Check configuration
        embedder_name = rag2f.spock.get_rag2f_config("embedder_standard")
        print(f"✓ Configured embedder: {embedder_name}")
        
        # Check if embedder was registered
        if embedder_name in rag2f.embedder_registry:
            embedder = rag2f.embedder_registry[embedder_name]
            print(f"✓ Embedder registered with size: {embedder.size}")
        else:
            print("✗ Embedder not registered")
            
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
    finally:
        # Clean up
        if "RAG2F__RAG2F__EMBEDDER_STANDARD" in os.environ:
            del os.environ["RAG2F__RAG2F__EMBEDDER_STANDARD"]


async def example_config_inspection():
    """
    Example 3: Inspecting configuration
    
    Shows how to inspect and debug configuration.
    """
    print("\n" + "="*70)
    print("Example 3: Configuration Inspection")
    print("="*70)
    
    try:
        # Try with example config
        rag2f = await RAG2F.create(config_path="config.example.json")
        
        # Get all configuration
        all_config = rag2f.spock.get_all_config()
        
        print("\n📋 RAG2F Configuration:")
        for key, value in all_config.get("rag2f", {}).items():
            print(f"  {key}: {value}")
        
        print("\n📦 Plugins Configuration:")
        for plugin_id, plugin_config in all_config.get("plugins", {}).items():
            print(f"\n  Plugin: {plugin_id}")
            for key, value in plugin_config.items():
                # Mask sensitive values
                display_value = "***" if "key" in key.lower() else value
                print(f"    {key}: {display_value}")
        
        print("\n🔌 Registered Embedders:")
        for name, embedder in rag2f.embedder_registry.items():
            print(f"  {name}: {type(embedder).__name__}")
            
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)


async def example_multiple_instances():
    """
    Example 4: Multiple RAG2F instances with different configurations
    
    Shows how to run multiple RAG2F instances simultaneously.
    """
    print("\n" + "="*70)
    print("Example 4: Multiple Instances")
    print("="*70)
    
    # Set different configs via environment
    os.environ["RAG2F__RAG2F__EMBEDDER_STANDARD"] = "instance_a"
    
    try:
        # Instance A - uses environment variables
        instance_a = await RAG2F.create()
        config_a = instance_a.spock.get_rag2f_config("embedder_standard")
        
        # Clear env for instance B
        del os.environ["RAG2F__RAG2F__EMBEDDER_STANDARD"]
        
        # Instance B - uses JSON config
        instance_b = await RAG2F.create(config_path="config.example.json")
        config_b = instance_b.spock.get_rag2f_config("embedder_standard")
        
        print(f"Instance A embedder: {config_a}")
        print(f"Instance B embedder: {config_b}")
        print(f"Instances are isolated: {instance_a.spock is not instance_b.spock}")
        
        # Each instance has its own plugin registry
        print(f"\nInstance A embedders: {list(instance_a.embedder_registry.keys())}")
        print(f"Instance B embedders: {list(instance_b.embedder_registry.keys())}")
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)


async def example_error_handling():
    """
    Example 5: Error handling and validation
    
    Shows what happens with invalid or missing configuration.
    """
    print("\n" + "="*70)
    print("Example 5: Error Handling")
    print("="*70)
    
    # Test 1: Missing config file
    print("\n1. Missing config file:")
    try:
        rag2f = await RAG2F.create(config_path="/nonexistent/config.json")
        print("  ✓ RAG2F created (missing config is not fatal)")
        print(f"  ℹ  Config loaded: {rag2f.spock.is_loaded}")
    except Exception as e:
        print(f"  ✗ Error: {e}")
    
    # Test 2: Invalid JSON
    print("\n2. Invalid JSON:")
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write("{ invalid json }")
        invalid_config_path = f.name
    
    try:
        rag2f = await RAG2F.create(config_path=invalid_config_path)
        print("  ✗ Should have raised error")
    except ValueError as e:
        print(f"  ✓ Caught error: {str(e)[:50]}...")
    finally:
        os.unlink(invalid_config_path)
    
    # Test 3: Missing required plugin configuration
    print("\n3. Missing plugin configuration:")
    try:
        rag2f = await RAG2F.create()
        
        # Try to get config for non-configured plugin
        config = rag2f.spock.get_plugin_config("nonexistent_plugin")
        print(f"  ✓ Returns empty config: {config}")
        
        # Try to get with default
        value = rag2f.spock.get_plugin_config("nonexistent_plugin", "key", default="default_value")
        print(f"  ✓ Returns default: {value}")
        
    except Exception as e:
        print(f"  ✗ Error: {e}")


async def main():
    """Run all examples."""
    print("\n" + "="*70)
    print("RAG2F SPOCK CONFIGURATION - COMPLETE EXAMPLES")
    print("="*70)
    
    # Run examples
    await example_with_json_config()
    await example_with_env_vars()
    await example_config_inspection()
    await example_multiple_instances()
    await example_error_handling()
    
    print("\n" + "="*70)
    print("All examples completed!")
    print("="*70)
    print("\n💡 Tips:")
    print("  - Use JSON for complex configuration")
    print("  - Use ENV vars for secrets and overrides")
    print("  - Each RAG2F instance has isolated configuration")
    print("  - Check config.example.json and .env.example for templates")
    print("  - Read SPOCK_CONFIGURATION.md for full documentation")
    print()


if __name__ == "__main__":
    asyncio.run(main())
