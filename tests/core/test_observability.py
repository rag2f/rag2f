"""Tests for observability helpers and structured logging integration."""

import logging
from pathlib import Path

from rag2f.core.morpheus.decorators.hook import PillHook
from rag2f.core.morpheus.morpheus import Morpheus
from rag2f.core.observability import debug_event, get_correlation_id, observation_scope
from rag2f.core.spock.spock import Spock


class _PluginStub:
    """Minimal plugin stub used for Morpheus logging tests."""

    @staticmethod
    def plugin_specific_error_message() -> str:
        """Return a stable support hint."""
        return "contact plugin creator"


def test_observation_scope_assigns_correlation_id():
    """Observation scope should provide a reusable correlation id."""
    with observation_scope(plugin_id="demo_plugin") as context:
        assert context["plugin_id"] == "demo_plugin"
        assert context["correlation_id"] == get_correlation_id()


def test_debug_event_redacts_sensitive_fields(caplog):
    """Structured logs should redact sensitive field values."""
    test_logger = logging.getLogger("tests.observability")
    caplog.set_level(logging.DEBUG, logger="tests.observability")

    with observation_scope(correlation_id="cid-123"):
        debug_event(test_logger, "demo_event", api_key="secret-key", plain_value="ok")

    assert "event=demo_event" in caplog.text
    assert "correlation_id=cid-123" in caplog.text
    assert "<redacted>" in caplog.text
    assert "secret-key" not in caplog.text


def test_spock_env_log_redacts_secret_values(caplog, monkeypatch):
    """Environment-derived secrets must not be written to logs."""
    caplog.set_level(logging.DEBUG, logger="rag2f.core.spock.spock")
    monkeypatch.setenv("RAG2F__PLUGINS__MY_PLUGIN__API_KEY", "super-secret")

    spock = Spock()
    spock.load()

    assert spock.get_plugin_config("my_plugin", "api_key") == "super-secret"
    assert "event=spock_env_applied" in caplog.text
    assert "super-secret" not in caplog.text
    assert "<redacted>" in caplog.text


def test_morpheus_logs_stack_trace_on_hook_failure(caplog, tmp_path: Path):
    """Hook failures should emit structured errors with stack traces."""

    def broken_hook(phone, *, rag2f):
        raise RuntimeError("boom")

    hook = PillHook("test_hook", broken_hook, priority=10)
    hook.plugin_id = "broken_plugin"

    morpheus = Morpheus(object(), plugins_folder=str(tmp_path / "unused_plugins"))
    morpheus.hooks = {"test_hook": [hook]}
    morpheus.plugins = {"broken_plugin": _PluginStub()}

    caplog.set_level(logging.WARNING, logger="rag2f.core.morpheus.morpheus")
    result = morpheus.execute_hook("test_hook", "payload", rag2f=None)

    assert result == "payload"

    failure_records = [
        record for record in caplog.records if "event=hook_execution_failed" in record.getMessage()
    ]
    assert failure_records
    assert failure_records[0].exc_info is not None
    assert "event=hook_execution_support_hint" in caplog.text
