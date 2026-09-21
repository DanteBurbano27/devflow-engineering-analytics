"""Tests for the development environment and runtime configuration."""

import pytest

from ingestion.common.config import ConfigurationError, Settings
from ingestion.common.environment import is_supported_python


def test_python_312_is_supported() -> None:
    """Python 3.12 must satisfy the minimum version."""
    assert is_supported_python((3, 12, 0)) is True


def test_python_313_is_supported() -> None:
    """Versions newer than Python 3.12 must be supported."""
    assert is_supported_python((3, 13, 0)) is True


def test_python_311_is_not_supported() -> None:
    """Python 3.11 must not satisfy the minimum version."""
    assert is_supported_python((3, 11, 9)) is False


def test_current_python_runtime_is_supported() -> None:
    """The active Python interpreter must satisfy the minimum version."""
    assert is_supported_python() is True


def test_settings_allow_anonymous_public_github_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A token is optional for public API requests with lower rate limits."""
    monkeypatch.setenv("GITHUB_TOKEN", "")

    assert Settings.from_env().github_token is None


@pytest.mark.parametrize(
    "base_url",
    [
        "http://api.github.com",
        "https://token@api.github.com",
        "https://api.github.com#fragment",
    ],
)
def test_settings_reject_unsafe_github_api_base_url(
    monkeypatch: pytest.MonkeyPatch,
    base_url: str,
) -> None:
    """Environment configuration must reject unsafe credential destinations."""
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setenv("GITHUB_API_BASE_URL", base_url)

    with pytest.raises(ConfigurationError, match="GitHub API base URL"):
        Settings.from_env()
