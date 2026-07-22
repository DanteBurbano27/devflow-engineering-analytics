"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


class ConfigurationError(RuntimeError):
    """Raised when the application configuration is invalid."""


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings required by the ingestion application."""

    github_token: str
    github_api_base_url: str
    github_api_version: str
    github_timeout_seconds: float

    @classmethod
    def from_env(cls) -> Settings:
        """Build application settings from environment variables."""
        load_dotenv()

        github_token = os.getenv("GITHUB_TOKEN", "").strip()

        if not github_token:
            raise ConfigurationError(
                "GITHUB_TOKEN is missing. Add it to the local .env file."
            )

        github_api_base_url = os.getenv(
            "GITHUB_API_BASE_URL",
            "https://api.github.com",
        ).strip()

        github_api_version = os.getenv(
            "GITHUB_API_VERSION",
            "2026-03-10",
        ).strip()

        timeout_raw = os.getenv(
            "GITHUB_TIMEOUT_SECONDS",
            "30",
        ).strip()

        try:
            github_timeout_seconds = float(timeout_raw)
        except ValueError as exc:
            raise ConfigurationError(
                "GITHUB_TIMEOUT_SECONDS must be a valid number."
            ) from exc

        if github_timeout_seconds <= 0:
            raise ConfigurationError(
                "GITHUB_TIMEOUT_SECONDS must be greater than zero."
            )

        return cls(
            github_token=github_token,
            github_api_base_url=github_api_base_url,
            github_api_version=github_api_version,
            github_timeout_seconds=github_timeout_seconds,
        )
