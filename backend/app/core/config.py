"""
DispenseIQ — Core Backend Configuration

Provides centralized, configurable access to application settings,
environment variables, and database connections with zero-dependency .env support.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Final

# Supported PostgreSQL schemes for SQLAlchemy with psycopg 3
POSTGRES_SCHEMES: Final[tuple[str, ...]] = (
    "postgresql+psycopg://",
    "postgresql://",
    "postgres://",
)

DEFAULT_CORS_ORIGINS: Final[list[str]] = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]


def _load_env_file() -> None:
    """Zero-dependency .env loader for developer onboarding convenience.

    Searches common workspace locations for a .env file and populates os.environ
    for any keys not already explicitly set in the shell environment.
    """
    cwd = Path.cwd()
    this_dir = Path(__file__).resolve().parent
    candidates = [
        cwd / ".env",
        cwd / "backend" / ".env",
        this_dir.parents[1] / ".env",  # backend/.env
        this_dir.parents[2] / ".env",  # repo root .env
    ]

    for candidate in candidates:
        if candidate.is_file():
            try:
                with open(candidate, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        key, _, val = line.partition("=")
                        key = key.strip()
                        val = val.strip()
                        # Strip outer matching quotes
                        if len(val) >= 2 and (
                            (val[0] == '"' and val[-1] == '"')
                            or (val[0] == "'" and val[-1] == "'")
                        ):
                            val = val[1:-1]
                        if key and key not in os.environ:
                            os.environ[key] = val
                break
            except Exception:
                pass


# Execute eager environment resolution on module load
_load_env_file()


@dataclass(frozen=True)
class Settings:
    """Application settings resolved from environment variables."""

    project_name: str = "DispenseLens API"
    project_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = field(default_factory=lambda: list(DEFAULT_CORS_ORIGINS))

    # Bounded LLM Configuration
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = 10.0

    @classmethod
    def load(cls) -> Settings:
        """Construct Settings instance from current environment variables."""
        _load_env_file()

        raw_cors = os.environ.get("CORS_ORIGINS", "").strip()
        if raw_cors:
            if raw_cors == "*":
                cors_origins = ["*"]
            else:
                cors_origins = [orig.strip() for orig in raw_cors.split(",") if orig.strip()]
        else:
            cors_origins = list(DEFAULT_CORS_ORIGINS)

        api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")
        model = os.environ.get("OPENAI_MODEL") or os.environ.get("LLM_MODEL") or "gpt-4o-mini"

        raw_timeout = os.environ.get("LLM_TIMEOUT_SECONDS", "10.0")
        try:
            timeout = float(raw_timeout)
        except ValueError:
            timeout = 10.0

        return cls(
            cors_origins=cors_origins,
            openai_api_key=api_key,
            openai_model=model,
            llm_timeout_seconds=timeout,
        )


def get_settings() -> Settings:
    """Retrieve application settings."""
    return Settings.load()


def get_database_url() -> str:
    """Retrieve and validate the configured PostgreSQL DATABASE_URL.

    Fails explicitly if DATABASE_URL is not set or if an unsupported database
    type (such as SQLite) is specified.

    Returns:
        A SQLAlchemy-compatible PostgreSQL connection string using psycopg 3.
    """
    _load_env_file()
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
