"""
Structured logging and correlation identifier context.

Uses contextvars so each request keeps an isolated correlation_id available to
loggers without threading globals through every call stack.
"""

from __future__ import annotations

import contextvars
import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any, Final

correlation_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id",
    default=None,
)

_SKIP_LOGRECORD_KEYS: Final[frozenset[str]] = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "message",
        "taskName",
    }
)


def get_correlation_id() -> str | None:
    """Return the correlation identifier for the current context, if any."""
    return correlation_id_ctx.get()


def set_correlation_id(value: str | None) -> contextvars.Token[str | None]:
    """Bind a correlation identifier for the current context."""
    return correlation_id_ctx.set(value)


def reset_correlation_id(token: contextvars.Token[str | None]) -> None:
    """Restore the previous correlation identifier."""
    correlation_id_ctx.reset(token)


class JsonLogFormatter(logging.Formatter):
    """Emit one JSON object per log line for production log aggregation."""

    def format(self, record: logging.LogRecord) -> str:
        correlation_id = get_correlation_id()
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if correlation_id is not None:
            payload["correlation_id"] = correlation_id
        for key, value in record.__dict__.items():
            if key in _SKIP_LOGRECORD_KEYS or key.startswith("_"):
                continue
            payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level_name: str) -> None:
    """Configure root logging to stdout with JSON formatting."""
    level = getattr(logging, level_name.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    root.addHandler(handler)
