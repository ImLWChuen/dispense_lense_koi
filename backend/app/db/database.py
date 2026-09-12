"""
DispenseIQ — Database Engine and Metadata

Declares the SQLAlchemy Declarative Base and lazy engine initialization.
"""

from __future__ import annotations

from typing import Any
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_database_url


class Base(DeclarativeBase):
    """Base declarative class for DispenseIQ ORM entities."""
    pass


_engine: Engine | None = None


def get_engine(**engine_kwargs: Any) -> Engine:
    """Lazily create and return the global SQLAlchemy engine.

    Requires DATABASE_URL to be set to a valid PostgreSQL connection string.
    """
    global _engine
    if _engine is None:
        url = get_database_url()
        _engine = create_engine(url, pool_pre_ping=True, **engine_kwargs)
    return _engine


def reset_engine() -> None:
    """Dispose and clear cached global engine (for clean test isolation)."""
    global _engine
    if _engine is not None:
        _engine.dispose()
        _engine = None
