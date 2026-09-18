# DevFlow Intelligence — Data Quality Framework

## 1. Overview and Principles

The DevFlow Intelligence Data Quality Framework provides programmatic, non-destructive data validation across the ingestion and transformation pipeline.

### Core Tenets
1. **Zero Mutation**: Data quality rules inspect data without altering field values or types.
2. **Explicit Severity Tiers**: Distinguishes between fatal contract violations (`ERROR`) and operational anomalies (`WARNING`).
3. **Reproducibility**: Rules are deterministic and do not depend on external network state or wall-clock timing.
4. **Cross-Record Integrity**: Evaluates both single-row constraints and batch-wide uniqueness (e.g. duplicate primary keys).

---

## 2. Severity Classification

```
┌─────────────────────────────────────────────────────────────┐
│                       QualitySeverity                       │
├─────────────────┬─────────────────────────┬─────────────────┤
│     ERROR       │         WARNING         │      INFO       │
├─────────────────┼─────────────────────────┼─────────────────┤
│ Rejects or      │ Flags anomalies that do │ Diagnostic      │
│ isolates record │ not invalidate schema   │ observation     │
│ (Breaks schema) │ (e.g. temporal oddity)  │                 │
└─────────────────┴─────────────────────────┴─────────────────┘
```

* **`ERROR`**: Serious schema, typing, identity, or negative numeric violations. Records with errors fail `is_valid` checks and must not be promoted to production marts without remediation.
* **`WARNING`**: Plausible anomalies (e.g., repository pushed before official creation timestamp, non-standard URL scheme, empty disk size). Does not reject the record but generates diagnostic telemetry.
* **`INFO`**: Informational observations about volume, defaults applied, or fleet patterns.

---

## 3. Data Quality Rule Catalog

### 3.1 Record-Level Validation Rules

| Rule ID | Rule Name | Severity | Field | Validation Condition |
|---|---|---|---|---|
| `DQ-NULL-001` | Required Fields Nullability | `ERROR` | multiple | Asserts non-nullness of mandatory repository attributes. |
| `DQ-ID-001` | Valid Positive Repository ID | `ERROR` | `repository_id` | Must be an integer strictly greater than 0. |
| `DQ-NAME-003` | Non-Empty Repository Name | `ERROR` | `repository_name` | Must be a non-empty string. |
| `DQ-NAME-001` | Non-Empty Full Name | `ERROR` | `full_name` | Must be a non-empty string. |
| `DQ-NAME-002` | Full Name Format Pattern | `ERROR` | `full_name` | Must match canonical `owner/repo` pattern. |
| `DQ-OWNER-001` | Non-Empty Owner Login | `ERROR` | `owner_login` | Must be a non-empty string. |
| `DQ-CONS-001` | Owner and Full Name Consistency | `ERROR` | `full_name` | `full_name` must start with `owner_login + '/'`. |
| `DQ-BRANCH-001` | Non-Empty Default Branch | `ERROR` | `default_branch` | Must be a non-empty string. |
| `DQ-METRIC-001` | Non-Negative Numeric Metrics | `ERROR` | `*_count`, `size_kb` | Stars, forks, issues, subscribers, and size cannot be negative. |
| `DQ-VIS-001` | Expected Visibility Domain | `ERROR` | `visibility` | Must be one of `public`, `private`, or `internal`. |
| `DQ-TIME-001` | Extracted At Timestamp Presence | `ERROR` | `extracted_at` | Lineage timestamp must be present and valid UTC ISO 8601. |
| `DQ-TIME-002` | Chronological Order Consistency | `ERROR` | `created_at`, `updated_at` | Validates $created\_at \le updated\_at$ and $created\_at \le extracted\_at$. |
| `DQ-TIME-003` | Pushed At Timestamp Plausibility | `WARNING` | `pushed_at` | Flags when $pushed\_at < created\_at$. |
| `DQ-URL-001` | Valid HTML URL Scheme | `WARNING` | `html_url` | Must begin with `http://` or `https://`. |

### 3.2 Batch-Level Integrity Rules

| Rule ID | Rule Name | Severity | Target Field | Validation Condition |
|---|---|---|---|---|
| `DQ-DUP-001` | Unique Repository ID Across Batch | `ERROR` | `repository_id` | Verifies that `repository_id` appears at most once in an extraction batch. |
| `DQ-DUP-002` | Unique Full Name Across Batch | `ERROR` | `full_name` | Verifies case-insensitive uniqueness of `full_name` across the batch. |

---

## 4. Quality Result Structure

Execution returns a consolidated, queryable `QualityResult` dataclass:

```python
@dataclass(frozen=True, slots=True)
class QualityResult:
    total_records: int
    passed_records: int
    failed_records: int
    rules_evaluated: int
    issues: tuple[QualityIssue, ...]
    evaluated_at: datetime
```

### Key Methods
* `result.is_valid`: Returns `True` if `error_count == 0`.
* `result.get_issues_by_severity(QualitySeverity.ERROR)`: Returns list of fatal issues.
* `result.get_issues_for_record(record_id)`: Slices issues specific to a given repository.
* `result.to_dict()`: Serializes quality metrics for ingestion into audit tables (e.g. `devflow_audit.data_quality_execution`).

---

## 5. Diagnostic Runbook

To execute the data quality test runner on the command line:

```powershell
python scripts/check_data_quality.py
```

Expected exit codes:
* `0`: All quality rules evaluated successfully without unhandled execution failures.
* `1`: Unhandled pipeline exception during evaluation.
