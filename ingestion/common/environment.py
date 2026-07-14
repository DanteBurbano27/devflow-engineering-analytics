"""Utilities for validating the local Python environment."""

import sys
from collections.abc import Sequence

MINIMUM_PYTHON_VERSION = (3, 11)


def is_supported_python(
    version_info: Sequence[int] | None = None,
) -> bool:
    """Return whether the provided Python version is supported.

    When no version is provided, the currently running interpreter
    is validated.
    """
    current_version = version_info or sys.version_info
    major_minor = tuple(current_version[:2])

    return major_minor >= MINIMUM_PYTHON_VERSION
