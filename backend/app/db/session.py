"""
Dispense Lens - Database Session Management

Provides transactional session scopes and session factory utilities.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy.orm import Session, sessionmaker

from app.db.database import get_engine


def get_session_factory() -> sessionmaker[Session]:
    """Return a sessionmaker bound to the lazy database engine."""
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of database operations.

    Commits on success and rolls back automatically on error.
    """
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """Dependency generator for FastAPI route session injection."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()
