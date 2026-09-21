# ADR 0001: Separation of Raw vs Normalized Data

## Context
The ingestion layer fetches raw JSON from GitHub. The analytics layer requires strictly typed data.

## Decision
We enforce a strict boundary: the ingestion layer normalizes raw JSON into a Python dictionary or data class (`RepositoryMetadata`). The analytics layer accepts this normalized structure and validates it using `RepositoryContract`. Raw GitHub JSON is not parsed within the analytics layer.

## Consequences
- Clean separation of concerns.
- Analytics code is isolated from GitHub API payload changes as long as the ingestion layer honors the dictionary contract.
