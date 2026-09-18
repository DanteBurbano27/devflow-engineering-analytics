"""Static acceptance tests for the BigQuery-ready warehouse boundary."""

from pathlib import Path

from analytics.contracts.repository import RepositoryContract
from ingestion.bigquery.repository_sink import REPOSITORY_TABLE_SCHEMA

SQL_ROOT = Path("analytics/sql")


def test_bigquery_sink_schema_matches_repository_contract() -> None:
    """The cloud adapter must expose the analytical v1 contract plus run_id."""
    contract_fields = {field.name for field in RepositoryContract.get_schema().fields}
    sink_fields = {field["name"] for field in REPOSITORY_TABLE_SCHEMA}

    assert sink_fields == {"run_id", *contract_fields}


def test_snapshot_fact_preserves_history_while_dimension_selects_latest() -> None:
    """Staging and facts keep snapshots; only the dimension selects latest state."""
    staging = (SQL_ROOT / "staging/stg_github_repositories.sql").read_text(
        encoding="utf-8"
    )
    dimension = (SQL_ROOT / "marts/dim_repositories.sql").read_text(encoding="utf-8")
    fact = (SQL_ROOT / "marts/fct_repository_snapshots.sql").read_text(encoding="utf-8")

    assert "dedup_rank" not in staging
    assert "QUALIFY ROW_NUMBER()" in dimension
    assert "PARTITION BY repository_id" in dimension
    assert "snapshot_timestamp" in fact
    assert "FROM repository_activity" in fact


def test_sql_zero_denominator_semantics_match_python_metrics() -> None:
    """Warehouse ratios must use the Python layer's 0.0 fallback semantics."""
    intermediate = (SQL_ROOT / "intermediate/int_repository_activity.sql").read_text(
        encoding="utf-8"
    )

    assert intermediate.count("COALESCE(") >= 5
    assert intermediate.count("SAFE_DIVIDE(") >= 6
