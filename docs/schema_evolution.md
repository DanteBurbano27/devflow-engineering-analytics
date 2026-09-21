# Schema Evolution Strategy

## Overview
This document outlines the versioning, deprecation, and backward compatibility strategy for the `RepositoryMetadata` contract in DevFlow Intelligence. The current schema is defined as **v1.0.0**.

## Versioning Model
We employ Semantic Versioning (SemVer) for the data contract:
- **MAJOR (vX.0.0)**: Breaking changes (e.g., removing a field, changing data types, or adding non-nullable fields without defaults).
- **MINOR (v1.X.0)**: Backward-compatible additions (e.g., adding nullable fields).
- **PATCH (v1.0.X)**: Non-breaking bug fixes (e.g., updating descriptions, refining quality rules internally).

## Backward Compatibility
To ensure the Ingestion Layer and Analytics Plane can deploy independently:
1. The Ingestion Layer must not drop any fields specified in the current major version.
2. If the Ingestion Layer needs to add a new metric or field, it must be nullable or have a clear default in order to bump the MINOR version.
3. The Analytics pipeline will tolerate extra unknown fields from the Ingestion Layer but will strictly enforce the required schema fields.

## Breaking Changes & Deprecation
1. A field slated for removal must first be marked as `DEPRECATED` in the documentation and warnings emitted in the data quality logs.
2. The deprecation window will last for one full release cycle (minimum 30 days).
3. Once the deprecation window is closed, a MAJOR version bump occurs, and the field is physically removed from `RepositoryContract`.
