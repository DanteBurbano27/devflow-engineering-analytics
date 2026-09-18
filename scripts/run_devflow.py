"""Run the DevFlow repository ingestion pipeline."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from orchestration.pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    """Build the local pipeline command-line parser."""
    parser = argparse.ArgumentParser(
        description="Run GitHub repository ingestion through local persistence."
    )
    parser.add_argument(
        "--config",
        required=True,
        type=Path,
        help="Path to the repository configuration JSON file.",
    )
    parser.add_argument(
        "--output-root",
        required=True,
        type=Path,
        help="Root directory for raw, normalized and manifest outputs.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Execute the pipeline and print its automation-safe JSON result."""
    args = build_parser().parse_args(argv)
    result = run_pipeline(
        config_path=args.config,
        output_root=args.output_root,
    )
    print(json.dumps(result.to_record(), ensure_ascii=False))
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
