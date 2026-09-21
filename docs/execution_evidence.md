# Verified local execution

This evidence was captured from an actual anonymous GitHub REST API run on 2026-09-21 UTC. It exercises the implemented V1 path from API request through raw and normalized persistence, contract validation, all 16 quality rules, metric calculation, analytics publication, and manifest enrichment. It does not exercise BigQuery or Looker Studio.

## Command

```powershell
$env:GITHUB_TOKEN = ""
python -m scripts.run_devflow `
  --config config/repositories.evidence.json `
  --output-root data
```

## Safe configuration

```json
{
  "repositories": [
    {
      "owner": "DanteBurbano27",
      "name": "devflow-engineering-analytics"
    }
  ]
}
```

## Sanitized console result

The request returned HTTP 200 on its first attempt. The terminal result was:

```json
{
  "status": "success",
  "exit_code": 0,
  "repositories_succeeded": 1,
  "repositories_failed": 0,
  "stages": [
    {"name": "configuration", "status": "success"},
    {"name": "client", "status": "success"},
    {"name": "service", "status": "success"},
    {"name": "batch", "status": "success"},
    {"name": "quality", "status": "success"},
    {"name": "analytics", "status": "success"}
  ],
  "error_type": null,
  "error_message": null
}
```

The run ID and timestamps are omitted because they are generated for every execution. No token, request header, or raw API payload is included in this document.

## Generated file structure

```text
data/
├── raw/github/repositories/extraction_date=2026-09-21/run_id=<UTC_ID>/repositories.jsonl
├── normalized/github/repositories/extraction_date=2026-09-21/run_id=<UTC_ID>/repositories.jsonl
├── analytics/github/repositories/extraction_date=2026-09-21/run_id=<UTC_ID>/report.json
└── manifests/github/repositories/extraction_date=2026-09-21/run_id=<UTC_ID>/manifest.json
```

## Representative report excerpt

```json
{
  "meta": {
    "total_input_records": 1,
    "processed_records": 1
  },
  "quality": {
    "summary": {
      "is_valid": true,
      "has_errors": false,
      "has_warnings": false,
      "total_records": 1,
      "passed_records": 1,
      "failed_records": 0,
      "rules_evaluated": 16,
      "error_count": 0,
      "warning_count": 0
    }
  },
  "portfolio": {
    "summary_metrics": {
      "total_repositories": 1
    },
    "activity_health": {
      "active_count": 1
    },
    "languages": [
      {
        "language": "Python",
        "repository_count": 1
      }
    ]
  }
}
```

The full generated files remain local and ignored because GitHub API responses are mutable snapshots. This stable excerpt proves the stage outcomes and output contract without presenting volatile repository counters as permanent portfolio results.
