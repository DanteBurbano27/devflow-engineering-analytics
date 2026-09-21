# ADR 0001: Separation of Raw vs Normalized Data

## Context
The Ingestion Layer fetches raw JSON from GitHub. The Analytics Plane requires strictly typed data.

## Decision
We enforce a strict boundary: the Ingestion Layer normalizes the raw JSON into a Python dictionary or Data Class (`RepositoryMetadata`). The Analytics Plane accepts this normalized structure and validates it using `RepositoryContract`. We do not parse the raw GitHub JSON within the analytics layer.

## Consequences
- Clean separation of concerns.
- Analytics code is immune to GitHub API payload changes as long as the Ingestion Layer honors the dictionary contract.
