"""Storage contract for normalized repository records."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class RepositoryWriteResult:
    """Summary returned by a repository record sink."""

    rows_attempted: int
    rows_written: int


class RepositoryRecordSink(Protocol):
    """Destination-independent contract for repository records."""

    def write(
        self,
        records: Sequence[Mapping[str, Any]],
        *,
        run_id: str,
    ) -> RepositoryWriteResult:
        """Persist normalized records for one extraction run."""
        ...
