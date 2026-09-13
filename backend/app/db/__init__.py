"""DispenseIQ — Database package."""

from app.db.database import Base, get_engine, reset_engine
from app.db.session import get_db, get_session_factory, session_scope


def __getattr__(name: str):
    if name == "CaseRepository":
        from app.db.repository import CaseRepository

        return CaseRepository
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "Base",
    "get_engine",
    "reset_engine",
    "get_session_factory",
    "session_scope",
    "get_db",
    "CaseRepository",
]
