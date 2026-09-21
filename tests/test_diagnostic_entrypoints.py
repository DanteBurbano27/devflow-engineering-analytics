"""Regression tests for supported diagnostic invocation forms."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent


def run_diagnostic(
    command: list[str], *, invalid_base_url: bool = False
) -> subprocess.CompletedProcess[str]:
    """Run a diagnostic from the checkout without inheriting import helpers."""
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    if invalid_base_url:
        environment["GITHUB_API_BASE_URL"] = "http://api.github.com"

    return subprocess.run(
        [sys.executable, *command],
        cwd=REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


@pytest.mark.parametrize(
    "command",
    [
        ["scripts/check_environment.py"],
        ["-m", "scripts.check_environment"],
    ],
    ids=["direct", "module"],
)
def test_environment_diagnostic_supports_both_invocation_forms(
    command: list[str],
) -> None:
    """The environment diagnostic must run both directly and as a module."""
    result = run_diagnostic(command)

    assert result.returncode == 0, result.stderr
    assert "[SUCCESS] The development environment is ready." in result.stdout


@pytest.mark.parametrize(
    "command",
    [
        ["scripts/check_github_connection.py"],
        ["-m", "scripts.check_github_connection"],
    ],
    ids=["direct", "module"],
)
def test_github_diagnostic_imports_in_both_invocation_forms_without_network(
    command: list[str],
) -> None:
    """Both entrypoints must reach configuration without making a request."""
    result = run_diagnostic(command, invalid_base_url=True)
    combined_output = result.stdout + result.stderr

    assert result.returncode == 1
    assert "[ERROR] GitHub API base URL" in result.stdout
    assert "ModuleNotFoundError" not in combined_output
