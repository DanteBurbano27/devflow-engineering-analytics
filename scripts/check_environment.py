"""Validate the DevFlow Intelligence development environment."""

import sys
from importlib.metadata import PackageNotFoundError, version

from ingestion.common.environment import (
    MINIMUM_PYTHON_VERSION,
    is_supported_python,
)

REQUIRED_PACKAGES = [
    "requests",
    "pydantic",
    "python-dotenv",
    "google-cloud-bigquery",
    "google-cloud-storage",
    "pandas",
    "pyarrow",
    "pytest",
    "ruff",
]


def check_installed_packages() -> list[str]:
    """Print installed package versions and return missing packages."""
    missing_packages: list[str] = []

    print("\nInstalled dependencies:")

    for package_name in REQUIRED_PACKAGES:
        try:
            installed_version = version(package_name)
            print(f"  [OK] {package_name}=={installed_version}")
        except PackageNotFoundError:
            missing_packages.append(package_name)
            print(f"  [MISSING] {package_name}")

    return missing_packages


def main() -> int:
    """Run environment checks and return an operating-system exit code."""
    current_version = ".".join(map(str, sys.version_info[:3]))
    minimum_version = ".".join(map(str, MINIMUM_PYTHON_VERSION))

    print("DevFlow Intelligence - Environment Check")
    print("----------------------------------------")
    print(f"Python executable: {sys.executable}")
    print(f"Python version: {current_version}")
    print(f"Minimum version: {minimum_version}")

    if not is_supported_python():
        print("\n[ERROR] The Python version is not supported.")
        return 1

    print("[OK] Python version is supported.")

    missing_packages = check_installed_packages()

    if missing_packages:
        print("\n[ERROR] Some required packages are missing.")
        print("Run: python -m pip install -r requirements-dev.txt")
        return 1

    print("\n[SUCCESS] The development environment is ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
