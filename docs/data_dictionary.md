# Data Dictionary

## Core Entity: RepositoryRecord (v1.0.0)

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `repository_id` | `int` | No | GitHub repository unique ID |
| `repository_name` | `str` | No | Short repository name |
| `full_name` | `str` | No | Full canonical name (owner/repo) |
| `owner_login` | `str` | No | Repository owner username or org |
| `description` | `str` | Yes | Repository description text |
| `visibility` | `str` | No | Visibility: public, private, or internal |
| `default_branch` | `str` | No | Default git branch name |
| `language` | `str` | Yes | Primary programming language |
| `is_fork` | `bool` | No | Whether repository is a fork |
| `is_archived` | `bool` | No | Whether repository is archived |
| `is_disabled` | `bool` | No | Whether repository is disabled |
| `created_at` | `datetime` | No | UTC timestamp when repository was created |
| `updated_at` | `datetime` | No | UTC timestamp when repository was updated |
| `pushed_at` | `datetime` | Yes | UTC timestamp of last push (null if none) |
| `stars_count` | `int` | No | Number of GitHub stars (non-negative) |
| `forks_count` | `int` | No | Number of repository forks (non-negative) |
| `open_issues_count` | `int` | No | Number of open issues (non-negative) |
| `subscribers_count` | `int` | No | Number of watchers (non-negative) |
| `size_kb` | `int` | No | Repository size in KB (non-negative) |
| `html_url` | `str` | No | Canonical GitHub web URL |
| `extracted_at` | `datetime` | No | UTC timestamp when data was ingested |

## Derived Analytical Fields (RepositoryMetrics)

| Field | Type | Description |
|-------|------|-------------|
| `repository_age_days` | `float` | Number of days since repository creation |
| `issue_density_per_mb` | `float` | Number of open issues per MB of repository size |
| `issue_to_fork_ratio` | `float` | Ratio of open issues to forks |
| `recency_bucket` | `str` | Categorization of repository activity (e.g., LAST_7_DAYS) |
| `size_category` | `str` | Size classification (e.g., SMALL, MEDIUM, LARGE) |
