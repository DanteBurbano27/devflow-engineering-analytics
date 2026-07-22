"""Custom exceptions raised by the GitHub API client."""


class GitHubAPIError(RuntimeError):
    """Base exception for GitHub API client failures."""


class GitHubAuthenticationError(GitHubAPIError):
    """Raised when GitHub rejects the authentication credentials."""


class GitHubNotFoundError(GitHubAPIError):
    """Raised when the requested GitHub resource does not exist."""


class GitHubRateLimitError(GitHubAPIError):
    """Raised when GitHub rejects a request due to a rate limit."""
