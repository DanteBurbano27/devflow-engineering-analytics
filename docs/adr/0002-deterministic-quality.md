# ADR 0002: Deterministic Data Quality

## Context
Data quality checks need to run at scale on large batches of repository data.

## Decision
All data quality rules within `DataQualityEngine` must be deterministic, stateless, and operate on a single record at a time (or batch without external network lookups).

## Consequences
- Fast evaluation (sub-millisecond).
- Easy to test using golden datasets.
- No external dependencies (e.g., database lookups) during the quality phase.
