"""Tests for structured application logging."""

import json
import logging

from ingestion.common.logging import JsonFormatter


def test_json_formatter_includes_context_fields() -> None:
    """Structured logs must contain standard and contextual fields."""
    record = logging.LogRecord(
        name="ingestion.github.client",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="GitHub request completed.",
        args=(),
        exc_info=None,
    )

    record.operation = "github_get"
    record.status_code = 200

    formatted_log = JsonFormatter().format(record)
    payload = json.loads(formatted_log)

    assert payload["level"] == "INFO"
    assert payload["logger"] == "ingestion.github.client"
    assert payload["message"] == "GitHub request completed."
    assert payload["operation"] == "github_get"
    assert payload["status_code"] == 200
    assert "timestamp" in payload
