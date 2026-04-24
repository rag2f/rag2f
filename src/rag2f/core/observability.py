"""Observability helpers for correlation and safe structured logging."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

_OBSERVATION_CONTEXT: ContextVar[dict[str, str] | None] = ContextVar(
    "rag2f_observation_context", default=None
)

_SENSITIVE_MARKERS = (
    "api_key",
    "authorization",
    "credential",
    "password",
    "secret",
    "token",
)


def get_observation_context() -> dict[str, str]:
    """Return the current observation context."""
    current = _OBSERVATION_CONTEXT.get()
    if current is None:
        return {}
    return dict(current)


def get_correlation_id() -> str | None:
    """Return the current correlation id when available."""
    return get_observation_context().get("correlation_id")


@contextmanager
def observation_scope(**fields: str | None) -> Iterator[dict[str, str]]:
    """Bind observation fields for the current execution context."""
    current = get_observation_context()
    updated = {key: value for key, value in current.items() if value is not None}

    for key, value in fields.items():
        if value is None:
            updated.pop(key, None)
        else:
            updated[key] = str(value)

    if not updated.get("correlation_id"):
        updated["correlation_id"] = uuid.uuid4().hex

    token = _OBSERVATION_CONTEXT.set(updated)
    try:
        yield dict(updated)
    finally:
        _OBSERVATION_CONTEXT.reset(token)


def is_sensitive_key(key: str) -> bool:
    """Return True when a key likely carries sensitive information."""
    normalized = key.lower()
    return any(marker in normalized for marker in _SENSITIVE_MARKERS)


def redact_value(key: str, value: Any) -> str:
    """Return a safe string representation for a value."""
    if is_sensitive_key(key):
        return "<redacted>"
    if value is None:
        return "None"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value
    return f"<{type(value).__name__}>"


def sanitize_fields(fields: Mapping[str, Any]) -> dict[str, str]:
    """Return fields converted to safe string values."""
    return {key: redact_value(key, value) for key, value in fields.items() if value is not None}


def _serialize_fields(fields: Mapping[str, Any]) -> tuple[str, tuple[str, ...]]:
    serialized = sanitize_fields(fields)
    if not serialized:
        return "", ()
    message = " ".join(f"{key}=%s" for key in serialized)
    return message, tuple(serialized.values())


def log_event(logger: logging.Logger, level: int, event: str, **fields: Any) -> None:
    """Emit a structured log line with the current observation context."""
    if level == logging.DEBUG and not logger.isEnabledFor(logging.DEBUG):
        return

    merged_fields = get_observation_context()
    merged_fields.update(sanitize_fields(fields))
    message, values = _serialize_fields(merged_fields)

    if message:
        logger.log(level, f"event=%s {message}", event, *values)
        return
    logger.log(level, "event=%s", event)


def debug_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    """Emit a DEBUG structured log line."""
    log_event(logger, logging.DEBUG, event, **fields)


def info_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    """Emit an INFO structured log line."""
    log_event(logger, logging.INFO, event, **fields)


def warning_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    """Emit a WARNING structured log line."""
    log_event(logger, logging.WARNING, event, **fields)


def error_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    """Emit an ERROR structured log line."""
    log_event(logger, logging.ERROR, event, **fields)


def exception_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    """Emit an ERROR structured log line with stack trace."""
    merged_fields = get_observation_context()
    merged_fields.update(sanitize_fields(fields))
    message, values = _serialize_fields(merged_fields)

    if message:
        logger.exception(f"event=%s {message}", event, *values)
        return
    logger.exception("event=%s", event)
