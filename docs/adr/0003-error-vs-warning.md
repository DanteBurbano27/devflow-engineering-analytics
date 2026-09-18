# ADR 0003: ERROR vs WARNING Quality Thresholds

## Context
Not all data anomalies should drop the record from the data warehouse.

## Decision
We implement a two-tier quality severity model:
- **ERROR**: Critical flaws (e.g., negative size, missing name) that immediately reject the record.
- **WARNING**: Anomalous but mathematically acceptable flaws (e.g., huge repository sizes). The record is accepted but logged.

## Consequences
- Preserves maximum data availability while blocking poison pills.
