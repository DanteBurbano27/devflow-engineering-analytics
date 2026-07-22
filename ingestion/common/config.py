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
    github_max_retries: int
    github_backoff_seconds: float
    log_level: str

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

        max_retries_raw = os.getenv(
            "GITHUB_MAX_RETRIES",
            "3",
        ).strip()

        backoff_raw = os.getenv(
            "GITHUB_BACKOFF_SECONDS",
            "1",
        ).strip()

        log_level = (
            os.getenv(
                "LOG_LEVEL",
                "INFO",
            )
            .strip()
            .upper()
        )

        try:
            github_timeout_seconds = float(timeout_raw)
        except ValueError as exc:
            raise ConfigurationError(
                "GITHUB_TIMEOUT_SECONDS must be a valid number."
            ) from exc

        try:
            github_max_retries = int(max_retries_raw)
        except ValueError as exc:
            raise ConfigurationError(
                "GITHUB_MAX_RETRIES must be a valid integer."
            ) from exc

        try:
            github_backoff_seconds = float(backoff_raw)
        except ValueError as exc:
            raise ConfigurationError(
                "GITHUB_BACKOFF_SECONDS must be a valid number."
            ) from exc

        if github_timeout_seconds <= 0:
            raise ConfigurationError(
                "GITHUB_TIMEOUT_SECONDS must be greater than zero."
            )

        if github_max_retries < 0:
            raise ConfigurationError("GITHUB_MAX_RETRIES cannot be negative.")

        if github_backoff_seconds < 0:
            raise ConfigurationError("GITHUB_BACKOFF_SECONDS cannot be negative.")

        valid_log_levels = {
            "DEBUG",
            "INFO",
            "WARNING",
            "ERROR",
            "CRITICAL",
        }

        if log_level not in valid_log_levels:
            raise ConfigurationError(
                "LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR or CRITICAL."
            )

        return cls(
            github_token=github_token,
            github_api_base_url=github_api_base_url,
            github_api_version=github_api_version,
            github_timeout_seconds=github_timeout_seconds,
            github_max_retries=github_max_retries,
            github_backoff_seconds=github_backoff_seconds,
            log_level=log_level,
        )
