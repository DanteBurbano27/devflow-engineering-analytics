"""Security checks for outbound API URLs."""

from __future__ import annotations

from urllib.parse import SplitResult, urlsplit


def normalize_https_base_url(value: str) -> str:
    """Validate and normalize an HTTPS API base URL."""
    normalized = value.strip().rstrip("/")
    parsed = _split_url(normalized)

    if parsed.scheme.casefold() != "https":
        raise ValueError("GitHub API base URL must use HTTPS.")
    if not parsed.hostname:
        raise ValueError("GitHub API base URL must include a host.")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("GitHub API base URL cannot include credentials.")
    if parsed.query or parsed.fragment:
        raise ValueError("GitHub API base URL cannot include a query or fragment.")

    return normalized


def has_same_https_origin(candidate: str, trusted_base_url: str) -> bool:
    """Return whether a URL uses the exact trusted HTTPS origin."""
    try:
        candidate_parts = _split_url(candidate)
        trusted_parts = _split_url(trusted_base_url)
        candidate_origin = _origin(candidate_parts)
        trusted_origin = _origin(trusted_parts)
    except ValueError:
        return False

    return (
        candidate_parts.username is None
        and candidate_parts.password is None
        and candidate_origin == trusted_origin
    )


def _split_url(value: str) -> SplitResult:
    """Split a URL and normalize parser errors to ValueError."""
    try:
        parsed = urlsplit(value)
        _ = parsed.port
    except ValueError as exc:
        raise ValueError("GitHub API URL is invalid.") from exc
    return parsed


def _origin(parts: SplitResult) -> tuple[str, str | None, int | None]:
    """Build a normalized origin tuple with the HTTPS default port."""
    scheme = parts.scheme.casefold()
    port = parts.port
    if scheme == "https" and port is None:
        port = 443
    return scheme, parts.hostname.casefold() if parts.hostname else None, port
