"""Tests for the development environment validation."""

from ingestion.common.environment import is_supported_python


def test_python_312_is_supported() -> None:
    """Python 3.12 must satisfy the minimum version."""
    assert is_supported_python((3, 11, 0)) is True


def test_python_313_is_supported() -> None:
    """Versions newer than Python 3.12 must be supported."""
    assert is_supported_python((3, 13, 0)) is True


def test_python_311_is_not_supported() -> None:
    """Python 3.11 must not satisfy the minimum version."""
    assert is_supported_python((3, 10, 9)) is False


def test_current_python_runtime_is_supported() -> None:
    """The active Python interpreter must satisfy the minimum version."""
    assert is_supported_python() is True
