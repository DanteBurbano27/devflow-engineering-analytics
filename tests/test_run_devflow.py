"""Tests for the DevFlow pipeline command-line interface."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ingestion.common.logging import configure_logging
from orchestration.pipeline import PipelineResult, PipelineStatus
from scripts import run_devflow


@pytest.mark.parametrize(
    ("status", "expected_code"),
    [
        (PipelineStatus.SUCCESS, 0),
        (PipelineStatus.PARTIAL_SUCCESS, 2),
        (PipelineStatus.FAILED, 1),
    ],
)
def test_main_prints_json_result_and_returns_pipeline_exit_code(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    status: PipelineStatus,
    expected_code: int,
) -> None:
    """The module entry point must provide stable machine-readable output."""
    started_at = datetime(2026, 9, 18, 14, 0, 0, tzinfo=UTC)
    extracted_at = datetime(2026, 9, 18, 14, 0, 1, tzinfo=UTC)
    observed: dict[str, Path] = {}

    def fake_run_pipeline(*, config_path: Path, output_root: Path) -> PipelineResult:
        observed["config_path"] = config_path
        observed["output_root"] = output_root
        return PipelineResult(
            run_id="20260918T140001000000Z",
            started_at=started_at,
            extracted_at=extracted_at,
            status=status,
            repositories_succeeded=int(status != PipelineStatus.FAILED),
            repositories_failed=int(status != PipelineStatus.SUCCESS),
            raw_path=output_root / "raw.jsonl",
            normalized_path=output_root / "normalized.jsonl",
            analytics_path=output_root / "analytics.json",
            manifest_path=output_root / "manifest.json",
            stages=(),
        )

    monkeypatch.setattr(run_devflow, "run_pipeline", fake_run_pipeline)
    config_path = tmp_path / "repositories.json"
    output_root = tmp_path / "data"

    exit_code = run_devflow.main(
        ["--config", str(config_path), "--output-root", str(output_root)]
    )

    output = json.loads(capsys.readouterr().out)
    assert exit_code == expected_code
    assert observed == {"config_path": config_path, "output_root": output_root}
    assert output["status"] == status.value
    assert output["exit_code"] == expected_code
    assert output["run_id"] == "20260918T140001000000Z"


def test_main_keeps_structured_logs_out_of_json_stdout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Logs must use stderr so stdout remains one machine-readable document."""
    started_at = datetime(2026, 9, 18, 15, 0, 0, tzinfo=UTC)
    configure_logging()

    def fake_run_pipeline(*, config_path: Path, output_root: Path) -> PipelineResult:
        logging.getLogger("devflow.test").warning("pipeline diagnostic")
        return PipelineResult(
            run_id="20260918T150000000000Z",
            started_at=started_at,
            extracted_at=started_at,
            status=PipelineStatus.SUCCESS,
            repositories_succeeded=1,
            repositories_failed=0,
            raw_path=output_root / "raw.jsonl",
            normalized_path=output_root / "normalized.jsonl",
            analytics_path=output_root / "analytics.json",
            manifest_path=output_root / "manifest.json",
            stages=(),
        )

    monkeypatch.setattr(run_devflow, "run_pipeline", fake_run_pipeline)

    exit_code = run_devflow.main(
        [
            "--config",
            str(tmp_path / "repositories.json"),
            "--output-root",
            str(tmp_path / "data"),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out)["status"] == "success"
    assert "pipeline diagnostic" not in captured.out
    assert "pipeline diagnostic" in captured.err
