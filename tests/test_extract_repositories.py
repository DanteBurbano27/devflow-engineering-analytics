"""Tests for the repository batch command-line interface."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from ingestion.github.repository_batch import RepositoryBatchConfigurationError
from scripts import extract_repositories


@pytest.mark.parametrize(
    ("status", "expected_code"),
    [
        ("success", 0),
        ("partial_success", 2),
        ("failed", 1),
    ],
)
def test_main_returns_status_code_without_real_github_calls(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    status: str,
    expected_code: int,
) -> None:
    """The CLI must compose dependencies and map every batch status."""
    config = object()
    settings = SimpleNamespace(
        github_token="test-token",
        github_api_base_url="https://example.invalid",
        github_api_version="test-version",
        github_timeout_seconds=1.0,
        github_max_retries=0,
        github_backoff_seconds=0.0,
        log_level="INFO",
    )
    created: dict[str, object] = {}

    monkeypatch.setattr(
        extract_repositories.Settings,
        "from_env",
        classmethod(lambda cls: settings),
    )
    monkeypatch.setattr(
        extract_repositories,
        "configure_logging",
        lambda level: created.update(log_level=level),
    )
    monkeypatch.setattr(
        extract_repositories,
        "load_repository_config",
        lambda path: created.update(config_path=path) or config,
    )

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            created["client_kwargs"] = kwargs

    class FakeService:
        def __init__(self, client: object) -> None:
            created["client"] = client

    class FakeBatch:
        def __init__(self, service: object) -> None:
            created["service"] = service

        def run(self, batch_config: object, *, output_root: Path):
            created["batch_config"] = batch_config
            created["output_root"] = output_root
            return SimpleNamespace(
                run_id="20260723T120000000000Z",
                status=status,
                repositories_succeeded=1 if status != "failed" else 0,
                repositories_failed=0 if status == "success" else 1,
                manifest_path=output_root / "manifest.json",
            )

    monkeypatch.setattr(extract_repositories, "GitHubClient", FakeClient)
    monkeypatch.setattr(extract_repositories, "GitHubRepositoryService", FakeService)
    monkeypatch.setattr(extract_repositories, "GitHubRepositoryBatch", FakeBatch)

    config_path = tmp_path / "repositories.json"
    output_root = tmp_path / "data"
    exit_code = extract_repositories.main(
        ["--config", str(config_path), "--output-root", str(output_root)]
    )

    assert exit_code == expected_code
    assert created["config_path"] == config_path
    assert created["output_root"] == output_root
    assert created["batch_config"] is config
    assert created["log_level"] == "INFO"
    assert created["client_kwargs"] == {
        "token": "test-token",
        "base_url": "https://example.invalid",
        "api_version": "test-version",
        "timeout_seconds": 1.0,
        "max_retries": 0,
        "backoff_seconds": 0.0,
    }


def test_main_returns_one_for_invalid_configuration_without_creating_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Invalid local configuration must be checked before settings or clients."""
    client_created = False
    settings_loaded = False

    def unexpected_settings(cls: type) -> None:
        nonlocal settings_loaded
        settings_loaded = True
        raise AssertionError("Settings.from_env must not be called")

    monkeypatch.setattr(
        extract_repositories.Settings,
        "from_env",
        classmethod(unexpected_settings),
    )
    monkeypatch.setattr(extract_repositories, "configure_logging", lambda level: None)

    def invalid_config(path: Path):
        raise RepositoryBatchConfigurationError("Invalid repository configuration.")

    class UnexpectedClient:
        def __init__(self, **kwargs: object) -> None:
            nonlocal client_created
            client_created = True

    monkeypatch.setattr(extract_repositories, "load_repository_config", invalid_config)
    monkeypatch.setattr(extract_repositories, "GitHubClient", UnexpectedClient)

    exit_code = extract_repositories.main(
        [
            "--config",
            str(tmp_path / "invalid.json"),
            "--output-root",
            str(tmp_path / "data"),
        ]
    )

    assert exit_code == 1
    assert client_created is False
    assert settings_loaded is False


def test_main_reports_missing_configuration_as_input_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A missing input file must not be described as an output write failure."""
    settings_loaded = False

    def unexpected_settings(cls: type) -> None:
        nonlocal settings_loaded
        settings_loaded = True
        raise AssertionError("Settings.from_env must not be called")

    monkeypatch.setattr(
        extract_repositories.Settings,
        "from_env",
        classmethod(unexpected_settings),
    )

    exit_code = extract_repositories.main(
        [
            "--config",
            str(tmp_path / "missing.json"),
            "--output-root",
            str(tmp_path / "data"),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert settings_loaded is False
    assert "configuration could not be read" in output
    assert "output could not be written" not in output


def test_main_reports_malformed_json_line_before_loading_settings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Malformed JSON must report its line without exposing the document."""
    settings_loaded = False
    config_path = tmp_path / "malformed.json"
    config_path.write_text('{\n  "repositories": [\n}\n', encoding="utf-8")

    def unexpected_settings(cls: type) -> None:
        nonlocal settings_loaded
        settings_loaded = True
        raise AssertionError("Settings.from_env must not be called")

    monkeypatch.setattr(
        extract_repositories.Settings,
        "from_env",
        classmethod(unexpected_settings),
    )

    exit_code = extract_repositories.main(
        [
            "--config",
            str(config_path),
            "--output-root",
            str(tmp_path / "data"),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert settings_loaded is False
    assert "invalid JSON at line 3" in output
    assert '"repositories"' not in output


def test_main_reports_invalid_utf8_before_loading_settings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Invalid UTF-8 must be reported safely before credentials are loaded."""
    settings_loaded = False
    config_path = tmp_path / "invalid-utf8.json"
    config_path.write_bytes(b'\xff\xfe{"binary-content": "must-not-leak"}')

    def unexpected_settings(cls: type) -> None:
        nonlocal settings_loaded
        settings_loaded = True
        raise AssertionError("Settings.from_env must not be called")

    monkeypatch.setattr(
        extract_repositories.Settings,
        "from_env",
        classmethod(unexpected_settings),
    )

    exit_code = extract_repositories.main(
        [
            "--config",
            str(config_path),
            "--output-root",
            str(tmp_path / "data"),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert settings_loaded is False
    assert "valid UTF-8" in output
    assert "binary-content" not in output
    assert "must-not-leak" not in output
    assert "output could not be written" not in output
