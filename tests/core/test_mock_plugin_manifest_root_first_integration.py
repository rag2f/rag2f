"""Integration test for root-first manifest selection."""


def test_mock_plugin_manifest_root_first(rag2f):
    """Root-level plugin.json should take precedence over nested plugin.json."""
    # mock_plugin has both root plugin.json and nested_folder/plugin.json.
    # Root-first policy must pick the root.
    plugin = rag2f.morpheus.plugins["mock_plugin"]
    assert plugin.manifest.name == "Mock plugin"
    assert plugin.manifest.version == "0.0.0"
