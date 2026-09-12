"""
DispenseIQ — Core Backend Configuration

Provides lazy access to application settings and environment variables.
"""

from __future__ import annotations

import os
from typing import Final

# Supported PostgreSQL schemes for SQLAlchemy with psycopg 3
POSTGRES_SCHEMES: Final[tuple[str, ...]] = (
    "postgresql+psycopg://",
    "postgresql://",
    "postgres://",
)


def get_database_url() -> str:
    """Retrieve and validate the configured PostgreSQL DATABASE_URL.

    Fails explicitly if DATABASE_URL is not set or if an unsupported database
    type (such as SQLite) is specified.

    Returns:
        A SQLAlchemy-compatible PostgreSQL connection string using psycopg 3.
    """
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL environment variable is not set. "
            "A valid PostgreSQL connection URL is required for database persistence operations."
        )

    lower_url = url.lower()
    if not any(lower_url.startswith(scheme) for scheme in POSTGRES_SCHEMES):
        raise ValueError(
            f"Unsupported database scheme in DATABASE_URL: '{url}'. "
            "Only PostgreSQL is authorized for DispenseLens persistence. "
            "SQLite or in-memory databases are strictly prohibited."
        )

    # Normalize standard postgresql:// or postgres:// to use psycopg 3 driver
    if lower_url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    elif lower_url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]

    return url
