"""Tests for structured application logging."""

import json
import logging
import sys

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


def test_json_formatter_redacts_nested_secret_fields() -> None:
    """Structured context must redact common credential field names."""
    record = logging.LogRecord(
        name="ingestion.bigquery",
        level=logging.ERROR,
        pathname=__file__,
        lineno=20,
        msg="Write failed.",
        args=(),
        exc_info=None,
    )
    record.run_id = "run-123"
    record.context = {
        "access_token": "simulated-token",
        "api_key": "simulated-api-key",
        "nested": [{"Authorization": "Bearer simulated-secret"}],
        "safe": "visible",
    }

    payload = json.loads(JsonFormatter().format(record))

    assert payload["run_id"] == "run-123"
    assert payload["context"]["access_token"] == "[REDACTED]"
    assert payload["context"]["api_key"] == "[REDACTED]"
    assert payload["context"]["nested"][0]["Authorization"] == "[REDACTED]"
    assert payload["context"]["safe"] == "visible"
    assert "simulated-token" not in json.dumps(payload)
    assert "simulated-api-key" not in json.dumps(payload)
    assert "simulated-secret" not in json.dumps(payload)


def test_json_formatter_redacts_inline_secrets_from_message_and_exception() -> None:
    """Free-form messages and tracebacks must not expose assigned secrets."""
    try:
        raise RuntimeError("Authorization: Bearer exception-secret")
    except RuntimeError:
        record = logging.LogRecord(
            name="ingestion.bigquery",
            level=logging.ERROR,
            pathname=__file__,
            lineno=50,
            msg=(
                "Request failed with token=message-secret api-key: secondary-secret "
                'payload={"api_key":"json-secret"}'
            ),
            args=(),
            exc_info=sys.exc_info(),
        )

    payload = json.loads(JsonFormatter().format(record))

    assert payload["message"] == (
        "Request failed with token=[REDACTED] api-key: [REDACTED] "
        'payload={"api_key":"[REDACTED]"}'
    )
    assert "Authorization: [REDACTED]" in payload["exception"]
    assert "message-secret" not in json.dumps(payload)
    assert "secondary-secret" not in json.dumps(payload)
    assert "json-secret" not in json.dumps(payload)
    assert "exception-secret" not in json.dumps(payload)
