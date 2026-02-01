"""Test helpers and shared constants."""

PATH_MOCK = "tests/mocks"


def get_mock_plugin_info():
    """Return basic metadata about the mock plugin used in tests."""
    return {"id": "mock_plugin", "hooks": 7}
