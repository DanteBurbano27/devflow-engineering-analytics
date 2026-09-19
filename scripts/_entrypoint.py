"""Bootstrap direct script execution from the repository checkout."""

from __future__ import annotations

import sys
from pathlib import Path


def add_repository_root_to_path() -> None:
    """Make project packages importable when a script is run by file path."""
    repository_root = str(Path(__file__).resolve().parent.parent)
    if repository_root not in sys.path:
        sys.path.insert(0, repository_root)
