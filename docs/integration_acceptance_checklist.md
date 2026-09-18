# DevFlow Intelligence — Integration Acceptance Checklist

This document establishes the technical criteria and boundary verification rules required to safely integrate the **Antigravity Analytics & Quality Layer** (`team/antigravity-analytics-quality`) with the **Codex Data Platform Layer** (`team/codex-data-platform`).

---

## 1. Branch & Worktree Integrity

- [x] **Branch Isolation**: Antigravity work is committed exclusively to `team/antigravity-analytics-quality`.
- [x] **Worktree Independence**: Antigravity executes in its dedicated worktree (`C:\DataEngineering\devflow-antigravity`).
- [x] **Upstream Alignment**: Antigravity branch is branched from `feature/dfi-006-repository-metadata`.
- [x] **No Direct Merges**: Neither team merges directly to `main` without mutual sign-off and Pull Request approval.
- [x] **Active PR Updated**: Pull Request #2 is updated directly via clean, semantic commits.

---

## 2. File Ownership Boundaries

Strict file demarcation prevents merge conflicts and maintains team accountability:

| Subsystem / File Pattern | Responsible Team | Antigravity Status | Codex Status |
|---|---|---|---|
| `analytics/**` | Antigravity | **Hardened & Finalized** | Read-only |
| `docs/analytics/**` | Antigravity | **Hardened & Finalized** | Read-only |
| `docs/integration_acceptance_checklist.md` | Antigravity | **Hardened & Finalized** | Read-only |
| `tests/test_analytics_*.py` | Antigravity | **Hardened & Finalized** | Read-only |
| `tests/test_contract_*.py` | Antigravity | **Hardened & Finalized** | Read-only |
| `tests/test_data_quality_*.py` | Antigravity | **Hardened & Finalized** | Read-only |
| `tests/test_metrics_*.py` | Antigravity | **Hardened & Finalized** | Read-only |
| `scripts/check_analytics.py` | Antigravity | **Hardened & Finalized** | Read-only |
| `scripts/check_data_quality.py` | Antigravity | **Hardened & Finalized** | Read-only |
| `ingestion/**` | Codex | Unmodified | Provided by data-platform layer |
| `storage/**` | Codex | Unmodified | In integration / Data-platform layer |
| `orchestration/**` | Codex | Unmodified | Planned / Data-platform layer |
| `observability/**` | Codex | Unmodified | Planned / Data-platform layer |
| `.github/**` | Codex | Unmodified | Provided by data-platform layer |
| `pyproject.toml` | Codex | Unmodified | Provided by data-platform layer |
| `requirements*.txt` | Codex | Unmodified | Provided by data-platform layer |
| `.env*`, `.gitignore` | Codex | Unmodified | Provided by data-platform layer |

- [x] **Zero Codex Files Modified**: `git diff origin/team/antigravity-analytics-quality` confirms zero touches to Codex-owned paths.

---

## 3. Contract & Schema Compatibility (`RepositoryMetadata`)

The analytics layer accepts either `ingestion.github.repository_metadata.RepositoryMetadata` instances or dictionary mappings adhering to the 21-field contract.

### Required Fields Specification

| # | Field Name | Python Type | Nullable | Validation Constraint |
|---|---|---|---|---|
| 1 | `repository_id` | `int` | No | Strict positive integer (`> 0`) |
| 2 | `repository_name` | `str` | No | Non-empty, stripped string |
| 3 | `full_name` | `str` | No | Canonical format `owner/repo` |
| 4 | `owner_login` | `str` | No | Non-empty string; matches `full_name` prefix |
| 5 | `description` | `str` | Yes | Nullable string; stripped |
| 6 | `visibility` | `str` | No | Domain: `'public'`, `'private'`, or `'internal'` |
| 7 | `default_branch` | `str` | No | Non-empty string (e.g. `'main'`, `'master'`) |
| 8 | `language` | `str` | Yes | Nullable string (e.g. `'Python'`, `'Go'`) |
| 9 | `is_fork` | `bool` | No | Strict boolean |
| 10 | `is_archived` | `bool` | No | Strict boolean |
| 11 | `is_disabled` | `bool` | No | Strict boolean |
| 12 | `created_at` | `datetime` | No | Timezone-aware UTC timestamp |
| 13 | `updated_at` | `datetime` | No | Timezone-aware UTC timestamp |
| 14 | `pushed_at` | `datetime` | Yes | Nullable timezone-aware UTC timestamp |
| 15 | `stars_count` | `int` | No | Non-negative integer (`>= 0`) |
| 16 | `forks_count` | `int` | No | Non-negative integer (`>= 0`) |
| 17 | `open_issues_count` | `int` | No | Non-negative integer (`>= 0`) |
| 18 | `subscribers_count` | `int` | No | Non-negative integer (`>= 0`) |
| 19 | `size_kb` | `int` | No | Non-negative integer (`>= 0`) |
| 20 | `html_url` | `str` | No | Valid HTTP/HTTPS web URL string |
| 21 | `extracted_at` | `datetime` | No | Timezone-aware UTC timestamp of pipeline run |

- [x] **Zero Schema Drift**: All 21 fields reflected in `ContractSchema.fields`.
- [x] **Contract Validation**: `RepositoryContract.validate()` rigorously verifies types, ranges, non-emptiness, and timezone awareness.

---

## 4. Raw-to-Normalized Data Handoff

```
[Raw Ingestion JSON]
        │
        ▼ (Codex Ingestion)
[RepositoryMetadata instance]
        │
        ▼ (Antigravity Contract Gate)
[RepositoryContract.validate(metadata)]
        │
        ├──► Invalid: raises ContractValidationError(details=[...])
        │
        ▼ Valid
[RepositoryRecord (immutable dataclass)]
        │
        ▼
[DataQualityEngine.evaluate(records)]
        │
        ├──► Errors found (is_valid == False): Halts downstream promotion
        │
        ▼ Warnings only or clean
[RepositoryMetricCalculator.calculate(record)]
        │
        ▼
[PortfolioAnalyticsAggregator.aggregate(metrics_list)]
        │
        ├──► Local / API Output: PortfolioSummary.to_dict()
        └──► Warehouse Load: Google BigQuery (analytics/sql/**)
```

- [x] **Standard Handoff Protocol**: Analytics consumes `RepositoryMetadata` directly or via `.to_record()` dictionary output.
- [x] **Zero Side Effects**: Neither `RepositoryContract` nor `DataQualityEngine` mutates input data.

---

## 5. Data Quality Assurance Gates

- [x] **Rule Count**: 16 deterministic rules (14 record-level, 2 batch-level).
- [x] **Severity Separation**:
  - `ERROR`: Fatal contract breaches (negative numbers, empty mandatory identifiers, ID duplicates, temporal impossibilities like $created\_at > updated\_at$).
  - `WARNING`: Anomaly flags ($pushed\_at < created\_at$, non-HTTP URL scheme).
- [x] **Batch Evaluation**: Evaluates batch-wide uniqueness of `repository_id` and `full_name`.
- [x] **Audit Telemetry**: `QualityResult.to_dict()` outputs structured statistics for audit logging.

---

## 6. BigQuery SQL Warehouse Models

All SQL models in `analytics/sql/` are validated for Google Cloud BigQuery compatibility:

1. **`stg_github_repositories.sql`** (Staging):
   - Type casting and null coalescing.
   - 64-bit deterministic surrogate keys via `FARM_FINGERPRINT(CONCAT(CAST(repository_id AS STRING), '|', full_name))`.
   - Deduplication via `ROW_NUMBER() OVER (PARTITION BY repository_id ORDER BY extracted_at DESC, updated_at DESC) = 1`.
2. **`int_repository_activity.sql`** (Intermediate):
   - Zero-division safe ratios (`fork_to_star_ratio`, `issue_to_star_ratio`, `star_to_fork_ratio`, `issue_to_fork_ratio`, `issue_density_per_mb`) via `SAFE_DIVIDE`.
   - `recency_bucket`: `LAST_7_DAYS`, `LAST_30_DAYS`, `LAST_90_DAYS`, `LAST_180_DAYS`, `OVER_180_DAYS`, `NEVER_PUSHED`.
   - `activity_status`: `ACTIVE`, `STALE`, `INACTIVE`, `ARCHIVED`, `DISABLED`.
   - `community_interest_score`: Standardized weighted composite score.
3. **`dim_repositories.sql`** (Marts):
   - Conformed dimension clustered by `(language, visibility, owner_login)`.
4. **`fct_repository_snapshots.sql`** (Marts):
   - Fact table partitioned by `DATE(snapshot_timestamp)` and clustered by `(repository_id, language)`.
5. **`agg_language_summary.sql` & `agg_owner_summary.sql`** (Marts):
   - Aggregated fleet rollups using `QUALIFY ROW_NUMBER() ... = 1` for point-in-time accuracy.

---

## 7. Automated Test Suite & Code Quality

- [x] **Test Isolation**: 100% offline, zero network requests, zero GitHub tokens, zero cloud credentials.
- [x] **Synthetic Fixtures**: All tests run with deterministic synthetic data fixtures.
- [x] **Pytest Pass**: All 109+ tests pass in $< 1.0\text{s}$.
- [x] **Linter Compliance**: `ruff check .` passes with zero errors or warnings.
- [x] **Formatting Compliance**: `ruff format --check .` passes with line length $\le 88$.

---

## 8. Security & Environment Governance

- [x] **Zero Hardcoded Secrets**: No API tokens, passwords, or GCP service account keys in codebase.
- [x] **Environment Variable Ingestion**: Relies strictly on `GITHUB_TOKEN` from environment.
- [x] **Standard Library Core**: Analytics engine requires zero external packages beyond standard Python library, minimizing supply chain vulnerabilities.

---

## 9. Minimum Dataset Produced by Codex for End-to-End Validation

For the analytics and SQL layer to run without manual adjustments, Codex must provide an extraction batch fulfilling:

1. **Format**: Either a list of `RepositoryMetadata` Python objects or a JSON Lines / newline-delimited JSON payload matching `RepositoryRecord` fields.
2. **Cardinality**: At least 1 valid repository record (e.g. `apache/airflow` or synthetic test repo).
3. **Identity**: `repository_id` $> 0$, `full_name` formatted as `'<owner>/<repo>'`, matching `owner_login`.
4. **Timestamps**: `created_at`, `updated_at`, `extracted_at` as ISO 8601 strings with timezone offset (`'Z'` or `'+00:00'`).
5. **Metrics**: All count fields (`stars_count`, `forks_count`, `open_issues_count`, `subscribers_count`, `size_kb`) populated with non-negative integers.

---

## 10. Verification Sign-Off

| Milestone | Target | Status | Responsible |
|---|---|---|---|
| Phase 1: Analytics & Quality Engine | Complete analytical layer | **PASSED** | Antigravity Team |
| Phase 2B: Hardening & Integration Readiness | Contract tests, ratios, recency, SQL models, checklist | **PASSED** | Antigravity Team |
| Final Integration: Codex Data Platform | Ingestion, local storage, Python orchestration, CI, mock-tested BigQuery adapter | **PASSED LOCALLY** | Codex Team |
