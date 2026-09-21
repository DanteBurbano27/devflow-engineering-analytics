# DevFlow Intelligence

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Tests: Pytest](https://img.shields.io/badge/tests-pytest-green.svg)](https://docs.pytest.org/)

DevFlow Intelligence is a V1 batch data pipeline for comparing maintenance activity across public GitHub repositories. It calls the GitHub REST API, preserves raw and normalized snapshots, enforces a typed contract and 16 data-quality rules, calculates repository and fleet metrics, and publishes a run manifest plus an analytics report.

## What is implemented

| Capability | Status | Evidence |
|---|---|---|
| Local GitHub ingestion, normalization, quality, analytics, and partitioned JSON output | **Implemented and tested** | `orchestration/pipeline.py`, offline test suite, and [verified public API run](docs/execution_evidence.md) |
| Retry, pagination, rate-limit handling, atomic publication, and secret-safe errors | **Implemented and tested** | `ingestion/github/`, unit and regression tests |
| BigQuery insert adapter | **Implemented and mock-tested** | `ingestion/bigquery/repository_sink.py`; it is not composed into the local pipeline |
| BigQuery SQL models | **Static-tested, warehouse-ready artifacts** | `analytics/sql/`; they have not been executed against a deployed dataset |
| BigQuery infrastructure and scheduled orchestration | **Not deployed** | Optional V2 work |
| Looker Studio dashboard | **Planned V2** | No dashboard is claimed for V1 |

## Architecture

```mermaid
flowchart LR
    GH[GitHub REST API] --> CLIENT[API client<br/>auth, pagination, retries]
    CLIENT --> RAW[Raw JSONL snapshot]
    RAW --> NORM[Normalized repository records]
    NORM --> CONTRACT[Typed contract]
    CONTRACT --> DQ[16 quality rules<br/>14 record + 2 batch]
    DQ --> METRICS[Repository and fleet metrics]
    METRICS --> REPORT[Analytics report + manifest]

    REPORT -. optional adapter; not wired in V1 .-> BQADAPTER[Mock-tested BigQuery adapter]
    BQADAPTER -. deployment required .-> SQL[Static-tested BigQuery SQL models]
    SQL -. planned V2 .-> DASH[Looker Studio]
```

The solid path is publicly reproducible. The dashed path describes optional warehouse integration artifacts and future deployment work.

## Reproduce the verified path

Prerequisites: Python 3.12 or newer and Git.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --disable-pip-version-check -r requirements-lock.txt

# One public repository; no token is required.
python -m scripts.run_devflow `
  --config config/repositories.evidence.json `
  --output-root data
```

Anonymous GitHub API access has a lower rate limit. Set `GITHUB_TOKEN` in the environment for authenticated requests; never commit it. The command prints one machine-readable result to stdout and structured operational logs to stderr. See [execution evidence](docs/execution_evidence.md) for sanitized output from an actual run.

Run the same quality gates used by CI:

```powershell
python -m compileall analytics ingestion orchestration scripts
python -m ruff check .
python -m ruff format --check .
python -m pytest
```

## Key engineering decisions

1. **Raw and normalized snapshots are separate.** Source responses remain available for audit while downstream code consumes a stable 21-field contract.
2. **Run context is shared.** One UTC extraction timestamp and run ID flow through extraction, quality, metrics, reports, and manifests.
3. **Publication is atomic and collision-safe.** Run-specific paths and a manifest-directory reservation prevent silent overwrite.
4. **Quality is deterministic.** The engine evaluates exactly 14 record rules and 2 batch rules without mutating input records.
5. **Warehouse claims stop at the tested boundary.** The BigQuery adapter uses a typed client protocol and mock tests; SQL tests validate contract shape and critical statements statically. No cloud deployment is claimed.

## Business problem and metric definitions

Engineering managers comparing multiple repositories need a consistent view of maintenance activity, open-issue volume, community interest, and technology distribution. DevFlow standardizes the GitHub fields and calculates these analytical signals:

- `ACTIVE`: pushed within the last 90 days and neither archived nor disabled.
- `STALE`: pushed 91 to 180 days ago.
- `INACTIVE`: no push for more than 180 days, or no recorded push.
- `ARCHIVED` and `DISABLED`: explicit GitHub repository states.
- `fork_to_star_ratio`, `issue_to_star_ratio`, and `issue_to_fork_ratio`: descriptive ratios with zero-safe behavior; they do not prove contribution or project quality.
- `issue_density_per_mb`: open-issue volume normalized by repository size.
- `community_interest_score`: a transparent portfolio heuristic, `(stars * 1.0) + (forks * 2.0) + (subscribers * 1.5)`, not a causal business metric.
- `recency_bucket`, `repository_age_days`, and `size_category`: deterministic segmentation fields.

The 90/180-day thresholds and weighted score are project-defined analytical rules, not GitHub standards.

## Data quality framework

The default ruleset contains exactly 16 rules:

- 14 record-level checks cover identity, names, owner consistency, required-field nullability, visibility, counters, URLs, branches, and timestamp validity.
- 2 batch-level checks reject duplicate repository IDs and case-insensitive duplicate full names.
- `ERROR` issues block analytical promotion; `WARNING` issues are retained as observations.

Run the diagnostic with:

```powershell
python scripts/check_data_quality.py
```

## Output layout

Each run writes immutable, date- and run-partitioned files:

```text
data/
├── raw/github/repositories/extraction_date=YYYY-MM-DD/run_id=<UTC_ID>/repositories.jsonl
├── normalized/github/repositories/extraction_date=YYYY-MM-DD/run_id=<UTC_ID>/repositories.jsonl
├── analytics/github/repositories/extraction_date=YYYY-MM-DD/run_id=<UTC_ID>/report.json
└── manifests/github/repositories/extraction_date=YYYY-MM-DD/run_id=<UTC_ID>/manifest.json
```

Generated data is intentionally ignored by Git. The committed evidence document contains only a sanitized transcript, file tree, and representative aggregate report fields.

## BigQuery boundary

`ingestion/bigquery/repository_sink.py` prepares normalized rows, converts timestamps to UTC RFC 3339 values, uses deterministic insert IDs, and sanitizes provider failures. Tests inject a mock client; the V1 orchestration does not instantiate a Google Cloud client or call this sink.

`analytics/sql/` contains BigQuery-dialect staging, intermediate, dimension, fact, and aggregate models. Static acceptance tests check schema alignment, snapshot preservation, latest-row selection, and zero-safe ratio expressions. They do not compile or execute SQL in BigQuery. Dataset creation, permissions, deployment, scheduling, and costs remain external work.

## Repository structure

```text
analytics/       contracts, 16-rule quality engine, metrics, SQL models
ingestion/       GitHub client/service/batch persistence and BigQuery adapter
orchestration/   local end-to-end pipeline and stage results
scripts/         pipeline entrypoint, diagnostics, and benchmark
config/          safe repository-list examples
tests/           offline unit, integration, contract, regression, and acceptance tests
docs/            architecture, lineage, runbook, limitations, and execution evidence
```

## Security and reliability

- No known credentials, local `.env` file, service-account key, or generated API payload is tracked.
- Tokens are read from environment variables and redacted from structured messages and provider errors.
- Anonymous access sends no `Authorization` header.
- CI uses read-only repository permissions and disables persisted checkout credentials.
- Unit and analytical tests make no network or cloud calls; real API execution is a separate documented demonstration.

## Roadmap

- [x] GitHub repository ingestion and metadata normalization
- [x] Typed analytical contract and 16-rule quality gate
- [x] Derived repository metrics and fleet aggregation
- [x] Raw, normalized, analytics, and manifest publication
- [x] Offline tests and GitHub Actions quality gates
- [x] Mock-tested BigQuery insert adapter and static-tested SQL models
- [ ] Execute and validate SQL against a provisioned BigQuery dataset
- [ ] Deploy managed scheduling with Airflow or Dagster
- [ ] Build the Looker Studio dashboard (planned V2)
