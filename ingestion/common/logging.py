"""Structured logging utilities for DevFlow Intelligence."""

from __future__ import annotations

import json
import logging
import re
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

_REDACTED = "[REDACTED]"
_SENSITIVE_KEY_PARTS = (
    "api-key",
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "password",
    "secret",
    "token",
)
_SENSITIVE_TEXT_PATTERNS = (
    re.compile(
        r"(?i)\b(authorization[\"']?\s*[:=]\s*[\"']?)"
        r"(?:bearer\s+)?[^\s,;}\"']+"
    ),
    re.compile(
        r"(?i)\b((?:api[-_\s]?key|credential|password|secret|token)"
        r"[\"']?\s*[:=]\s*[\"']?)[^\s,;}\"']+"
    ),
)

_STANDARD_LOG_RECORD_FIELDS = frozenset(logging.makeLogRecord({}).__dict__) | frozenset(
    {
        "message",
        "asctime",
    }
)


class JsonFormatter(logging.Formatter):
    """Format log records as JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        """Convert a log record into a serialized JSON object."""
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created,
                tz=UTC,
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": _redact_text(record.getMessage()),
        }

        for key, value in record.__dict__.items():
            if key in _STANDARD_LOG_RECORD_FIELDS:
                continue

            if key.startswith("_"):
                continue

            payload[key] = _redact(value, key=key)

        if record.exc_info:
            payload["exception"] = _redact_text(self.formatException(record.exc_info))

        return json.dumps(
            payload,
            ensure_ascii=False,
            default=str,
        )


def _redact(value: Any, *, key: str | None = None) -> Any:
    """Recursively redact values whose field names commonly contain secrets."""
    if key is not None and any(part in key.casefold() for part in _SENSITIVE_KEY_PARTS):
        return _REDACTED
    if isinstance(value, Mapping):
        return {
            item_key: _redact(item, key=str(item_key))
            for item_key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    return value


def _redact_text(value: str) -> str:
    """Redact common inline secret assignments from free-form text."""
    redacted = value
    for pattern in _SENSITIVE_TEXT_PATTERNS:
        redacted = pattern.sub(r"\1[REDACTED]", redacted)
    return redacted


def configure_logging(level: str = "INFO") -> None:
    """Configure application logging to write JSON records to stderr."""
    normalized_level = level.strip().upper()
    numeric_level = getattr(logging, normalized_level, None)

    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid logging level: {level}")

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(numeric_level)
