"""Custom exceptions raised by the GitHub API client."""


class GitHubAPIError(RuntimeError):
    """Base exception for GitHub API client failures."""


class GitHubAuthenticationError(GitHubAPIError):
    """Raised when GitHub rejects the authentication credentials."""


class GitHubNotFoundError(GitHubAPIError):
    """Raised when the requested GitHub resource does not exist."""


class GitHubRateLimitError(GitHubAPIError):
    """Raised when GitHub rejects a request due to a rate limit."""

    def __init__(
        self,
        message: str,
        *,
        remaining: str | None = None,
        reset_at: str | None = None,
        retry_after: str | None = None,
    ) -> None:
        """Initialize the exception with GitHub rate-limit metadata."""
        super().__init__(message)

        self.remaining = remaining
        self.reset_at = reset_at
        self.retry_after = retry_after
