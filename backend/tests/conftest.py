"""
Dispense Lens - Centralized Pytest Test Database Bootstrap

Provides safe, centralized configuration of the PostgreSQL test database target
using TEST_DATABASE_URL. Binds DATABASE_URL within the test runner to the validated
disposable test destination before the lazy SQLAlchemy engine is created.
Guarantees fail-closed safety if TEST_DATABASE_URL is missing, remote, redirected,
targets a non-disposable database, or targets the development database.
"""

from __future__ import annotations

import os
from typing import Final

import pytest

from app.db.database import reset_engine
from tests.unit.test_persistence_safety import assert_safe_test_database

# Capture development DATABASE_URL before test bootstrap binds to TEST_DATABASE_URL
_ORIGINAL_DEV_DATABASE_URL: Final[str | None] = os.environ.get("DATABASE_URL")


def bootstrap_test_database(dev_url: str | None = None) -> str:
    """Validate TEST_DATABASE_URL and bind it to DATABASE_URL for pytest execution.

    Fails closed if TEST_DATABASE_URL is missing, invalid, or conflicts with development.
    """
    test_url = os.environ.get("TEST_DATABASE_URL", "").strip()
    if not test_url:
        raise RuntimeError(
            "Database safety check failed: TEST_DATABASE_URL environment variable is not set. "
            "A valid PostgreSQL connection URL targeting an approved local test database "
            "(e.g. 'dispenselens_test') is required for database-backed tests."
        )

    # Validate test database destination safety and separation from development
    check_dev_url = dev_url if dev_url is not None else os.environ.get("DATABASE_URL")
    assert_safe_test_database(test_url, dev_url=check_dev_url)

    # Bind application's DATABASE_URL to the validated test destination
    os.environ["DATABASE_URL"] = test_url
    reset_engine()
    return test_url


@pytest.fixture(scope="session")
def test_database_url() -> str:
    """Session-scoped fixture providing the validated test database URL."""
    return bootstrap_test_database()
