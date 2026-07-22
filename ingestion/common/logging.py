"""Structured logging utilities for DevFlow Intelligence."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

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
            "message": record.getMessage(),
        }

        for key, value in record.__dict__.items():
            if key in _STANDARD_LOG_RECORD_FIELDS:
                continue

            if key.startswith("_"):
                continue

            payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(
            payload,
            ensure_ascii=False,
            default=str,
        )


def configure_logging(level: str = "INFO") -> None:
    """Configure application logging to write JSON records to stdout."""
    normalized_level = level.strip().upper()
    numeric_level = getattr(logging, normalized_level, None)

    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid logging level: {level}")

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(numeric_level)
