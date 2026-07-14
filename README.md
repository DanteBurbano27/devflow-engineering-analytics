# DevFlow Intelligence

Data Engineering pipeline for collecting, transforming and analyzing public software development activity from GitHub.

## Business problem

Engineering managers need reliable metrics to understand how software delivery workflows behave across repositories.

GitHub exposes operational data such as pull requests, reviews, issues and repository events, but this information is distributed across multiple API endpoints and is not immediately suitable for historical analytics.

DevFlow Intelligence consolidates this information into an analytical data warehouse to answer questions such as:

* How long does a pull request take to receive its first review?
* How long does a pull request take to be merged?
* Which repositories have the highest number of stale pull requests?
* How many issues are opened and closed each week?
* How many contributors are active in each repository?
* What percentage of closed pull requests are successfully merged?

## Planned architecture

```text
GitHub REST API + GH Archive
              ↓
       Python ingestion
              ↓
         Raw storage
              ↓
           BigQuery
              ↓
             dbt
              ↓
      Analytical data marts
              ↓
        Looker Studio
```

## Technology stack

* Python
* SQL
* GitHub REST API
* GH Archive
* Google BigQuery
* dbt Core
* Apache Airflow
* Docker
* Pytest
* GitHub Actions
* Looker Studio

## Project status

The project is currently under development.

### Current phase

* [x] Repository structure
* [ ] Project scope
* [ ] Architecture design
* [ ] GitHub API ingestion
* [ ] BigQuery raw layer
* [ ] dbt transformations
* [ ] Dimensional model
* [ ] Airflow orchestration
* [ ] Data quality tests
* [ ] Analytics dashboard

## Initial repositories

The MVP will analyze public activity from:

* `apache/airflow`
* `dbt-labs/dbt-core`
* `duckdb/duckdb`
* `pandas-dev/pandas`
* `prefecthq/prefect`

## Repository structure

```text
devflow-engineering-analytics/
├── ingestion/
├── dags/
├── dbt_devflow/
├── tests/
├── sql/
├── data/
├── docs/
├── scripts/
├── docker/
└── .github/workflows/
```

## Project objective

This project is being developed as a practical Data Engineering portfolio project focused on:

* API extraction.
* Batch pipelines.
* Incremental data loads.
* Idempotency.
* Data quality.
* Dimensional modeling.
* Pipeline orchestration.
* Technical documentation.

## Project documentation

- [Project scope](docs/project_scope.md)
- [System architecture](docs/architecture/system_architecture.md)