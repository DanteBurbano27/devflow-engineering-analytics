# DevFlow Intelligence — Project Scope

## 1. Project overview

DevFlow Intelligence is a batch Data Engineering platform designed to collect, store, transform and analyze public software development activity from GitHub repositories.

The platform will integrate data from the GitHub REST API and GH Archive to build an analytical warehouse containing information about:

* Pull requests.
* Pull request reviews.
* Issues.
* Repository activity.
* Contributors.
* Software delivery metrics.

The final result will allow engineering managers and technical teams to understand how development workflows behave over time.

---

## 2. Business problem

GitHub contains valuable operational information about software development, but the data is distributed across multiple endpoints and event types.

Engineering managers often need to answer questions such as:

* How long does a pull request take to receive its first review?
* How long does a pull request take to be merged?
* How many pull requests remain open for too long?
* What percentage of closed pull requests are merged?
* How long does it take to resolve an issue?
* Which repositories have the highest activity?
* How many contributors are active each week?

GitHub's interface allows users to inspect individual repositories, but it is not designed as a centralized analytical warehouse for historical comparisons.

DevFlow Intelligence will consolidate this information into structured analytical tables.

---

## 3. Project objective

Build a reproducible batch data pipeline that:

1. Extracts public repository activity from GitHub.
2. Preserves raw source data for traceability.
3. Loads the data into Google BigQuery.
4. Cleans and transforms the data using dbt.
5. Creates a basic dimensional model.
6. Generates software delivery metrics.
7. Validates data quality.
8. Automates pipeline execution using Apache Airflow.
9. Presents the results through an analytical dashboard.

---

## 4. MVP data sources

### 4.1 GitHub REST API

The GitHub REST API will be used to extract detailed information about:

* Repositories.
* Pull requests.
* Pull request reviews.
* Issues.

### 4.2 GH Archive

GH Archive will be used to extract public GitHub events such as:

* `PullRequestEvent`
* `PushEvent`
* `IssuesEvent`
* `IssueCommentEvent`
* `ReleaseEvent`

---

## 5. Repositories included

The MVP will analyze the following public repositories:

* `apache/airflow`
* `dbt-labs/dbt-core`
* `duckdb/duckdb`
* `pandas-dev/pandas`
* `prefecthq/prefect`

During development, the first technical tests will use only:

* `apache/airflow`

After the pipeline works correctly with one repository, the remaining repositories will be added through configuration.

---

## 6. Historical scope

The initial MVP will process:

* 30 days of historical data.
* Daily incremental executions after the initial load.

A configurable backfill process will allow data to be reprocessed for a specific date range.

Example:

```text
Start date: 2026-06-01
End date: 2026-06-30
```

The project will not attempt to process the complete history of GitHub.

---

## 7. Entities included

### 7.1 Repository

Stores general information about each repository.

Minimum fields:

* Repository ID.
* Repository name.
* Owner.
* Main language.
* Creation date.
* Last update date.
* Number of stars.
* Number of forks.
* Archived status.

### 7.2 Pull request

Stores information about each pull request.

Minimum fields:

* Pull request ID.
* Pull request number.
* Repository.
* Author.
* Title.
* State.
* Draft status.
* Creation timestamp.
* Update timestamp.
* Close timestamp.
* Merge timestamp.
* Number of commits.
* Number of comments.
* Number of changed files.
* Additions.
* Deletions.

### 7.3 Pull request review

Stores reviews submitted to pull requests.

Minimum fields:

* Review ID.
* Repository.
* Pull request number.
* Reviewer.
* Review state.
* Submission timestamp.

### 7.4 Issue

Stores GitHub issues that are not pull requests.

Minimum fields:

* Issue ID.
* Issue number.
* Repository.
* Author.
* Title.
* State.
* Creation timestamp.
* Update timestamp.
* Close timestamp.
* Number of comments.
* Labels.

### 7.5 Repository event

Stores selected public events from GH Archive.

Minimum fields:

* Event ID.
* Event type.
* Repository.
* Actor.
* Event creation timestamp.
* Raw event payload.
* Ingestion timestamp.

---

## 8. Business metrics

### 8.1 Pull request cycle time

Measures the time between the creation and merge of a pull request.

```text
pull_request_cycle_time =
merged_at - created_at
```

Only merged pull requests will have this metric.

Unit:

```text
Hours
```

---

### 8.2 Time to first review

Measures the time between pull request creation and its first submitted review.

```text
time_to_first_review =
first_review_at - pull_request_created_at
```

Pull requests without reviews will keep this value as null.

Unit:

```text
Hours
```

---

### 8.3 Pull request merge rate

Measures the percentage of closed pull requests that were merged.

```text
merge_rate =
merged_pull_requests / closed_pull_requests
```

Unit:

```text
Percentage
```

---

### 8.4 Stale pull requests

A pull request will initially be considered stale when:

* Its state is open.
* It has remained open for more than 14 days.

```text
is_stale =
state = open
AND current_date - created_at > 14 days
```

The 14-day threshold is a business rule and may be changed through configuration in later versions.

---

### 8.5 Issue resolution time

Measures the time between issue creation and issue closure.

```text
issue_resolution_time =
closed_at - created_at
```

Only closed issues will have this metric.

Unit:

```text
Hours
```

---

### 8.6 Active contributors

Measures the number of distinct users who generated relevant activity during a period.

Relevant activity may include:

* Creating a pull request.
* Submitting a review.
* Creating an issue.
* Generating a selected repository event.

Default reporting period:

```text
One day or one week
```

---

### 8.7 Repository activity volume

Measures the number of selected GitHub events generated by each repository.

The metric may be grouped by:

* Date.
* Week.
* Repository.
* Event type.

---

## 9. Technical scope

The MVP will include:

* Python-based API extraction.
* Environment-variable configuration.
* GitHub API pagination.
* HTTP timeout handling.
* Basic retry handling.
* GitHub rate limit handling.
* JSON and JSON Lines processing.
* Raw data preservation.
* Google BigQuery storage.
* Incremental loads.
* Watermark management.
* Record deduplication.
* Pipeline execution auditing.
* dbt staging models.
* dbt intermediate models.
* Analytical marts.
* Basic dimensional modeling.
* dbt data tests.
* Python unit tests.
* Apache Airflow orchestration.
* Docker Compose local environment.
* GitHub Actions continuous integration.
* Looker Studio dashboard.
* Technical documentation.

---

## 10. Data architecture layers

### 10.1 Raw layer

Purpose:

* Preserve source data.
* Maintain traceability.
* Support reprocessing.
* Avoid applying business logic during ingestion.

Expected BigQuery dataset:

```text
devflow_raw
```

### 10.2 Staging layer

Purpose:

* Rename fields.
* Convert data types.
* Normalize timestamps.
* Standardize values.
* Remove technical duplicates.

Expected BigQuery dataset:

```text
devflow_staging
```

### 10.3 Analytics layer

Purpose:

* Build dimensions.
* Build fact tables.
* Calculate business metrics.
* Provide tables ready for dashboards.

Expected BigQuery dataset:

```text
devflow_analytics
```

### 10.4 Audit layer

Purpose:

* Register pipeline executions.
* Store row counts.
* Track successful and failed executions.
* Maintain watermarks.

Expected BigQuery dataset:

```text
devflow_audit
```

---

## 11. MVP dimensional model

### Dimensions

* `dim_date`
* `dim_repository`
* `dim_contributor`
* `dim_event_type`
* `dim_pull_request_status`

### Fact tables

* `fct_pull_request`
* `fct_pull_request_review`
* `fct_issue`
* `fct_repository_event`

### Analytical marts

* `mart_repository_daily_metrics`
* `mart_pull_request_performance`
* `mart_data_quality_summary`

---

## 12. Data quality rules

The MVP will validate at least the following rules:

* Primary entity identifiers must not be null.
* Dimensional keys must be unique.
* Pull request states must contain accepted values.
* Issue states must contain accepted values.
* `merged_at` must not be earlier than `created_at`.
* `closed_at` must not be earlier than `created_at`.
* `first_review_at` must not be earlier than pull request creation.
* Calculated durations must not be negative.
* Future source timestamps must be flagged.
* Duplicate business keys must be detected.
* Pull request reviews must reference an existing pull request.

---

## 13. Pipeline frequency

The production-style workflow will be designed as a daily batch pipeline.

Expected schedule:

```text
Once per day
```

The pipeline must also support:

* Manual execution.
* Historical backfill.
* Reprocessing after failure.

Real-time processing is not required.

---

## 14. MVP dashboard

The analytical dashboard will contain three sections.

### Executive summary

* Pull requests created.
* Pull requests merged.
* Merge rate.
* Average pull request cycle time.
* Average time to first review.
* Active contributors.

### Pull request flow

* Pull requests by state.
* Pull request cycle time by repository.
* Stale pull requests.
* Pull requests created and merged over time.

### Issues and repository activity

* Issues opened and closed.
* Average issue resolution time.
* Events by type.
* Activity by repository.

---

## 15. Out of scope

The following components will not be included in the MVP:

* Private GitHub repositories.
* GitHub organization administration.
* Real-time streaming.
* Apache Kafka.
* Apache Spark.
* Kubernetes.
* Machine learning models.
* Employee performance scoring.
* Ranking individual developers.
* Natural language processing of comments.
* Sentiment analysis.
* Production cloud deployment of Airflow.
* Terraform infrastructure.
* Multi-cloud support.
* Data from GitLab or Bitbucket.
* Full GitHub historical processing.
* Financial cost optimization at enterprise scale.
* Automated alerting systems.
* Personally identifiable information enrichment.

---

## 16. Ethical considerations

The project will only process publicly accessible GitHub information.

The platform is intended to analyze engineering workflows and repository activity. It must not be presented as a tool for evaluating individual employee performance.

Contributor-level information will only support aggregate metrics such as:

* Number of active contributors.
* Number of unique reviewers.
* Distribution of repository activity.

The project will avoid conclusions about individual productivity or employee quality.

---

## 17. Success criteria

The MVP will be considered complete when:

1. Data can be extracted from the selected GitHub repositories.
2. The extraction supports API pagination.
3. Raw records are stored with ingestion metadata.
4. Data can be loaded into BigQuery without uncontrolled duplication.
5. Incremental execution is controlled through watermarks.
6. dbt models produce clean analytical tables.
7. The dimensional model is documented.
8. Data quality tests execute automatically.
9. Airflow orchestrates the complete pipeline.
10. A dashboard displays the defined business metrics.
11. The project can be reproduced using documented instructions.
12. The repository does not expose credentials or tokens.

---

## 18. MVP limitations

The MVP has the following known limitations:

* GitHub API rate limits may restrict extraction volume.
* Public repositories may have different activity patterns.
* GH Archive data can be large and must be filtered before loading.
* Some pull requests may not contain reviews.
* Deleted or unavailable users may appear with incomplete information.
* Public project activity does not represent the complete software delivery process.
* Deployment and commit events do not necessarily indicate production releases.
* Metrics depend on the definitions established in this document.

---

## 19. Future improvements

Possible future versions may include:

* Additional repositories.
* Configurable repository groups.
* Deployment frequency metrics.
* Release frequency metrics.
* Pull request size classification.
* Data freshness alerts.
* Slack or email notifications.
* Cloud-based Airflow deployment.
* Terraform infrastructure.
* Additional software delivery platforms.
* Slowly changing dimensions.
* Historical snapshots.
* Cost and performance monitoring.
