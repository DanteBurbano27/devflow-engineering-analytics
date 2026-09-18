# ADR 0001: Separation of Raw vs Normalized Data

## Context
Codex fetches raw JSON from GitHub. Antigravity requires strictly typed data.

## Decision
We enforce a strict boundary: Codex normalizes the raw JSON into a Python dictionary or Data Class (`RepositoryMetadata`). Antigravity accepts this normalized structure and validates it using `RepositoryContract`. We do not parse the raw GitHub JSON within the analytics layer.

## Consequences
- Clean separation of concerns.
- Analytics code is immune to GitHub API payload changes as long as Codex honors the dictionary contract.
