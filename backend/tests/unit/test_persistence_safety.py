"""
DispenseIQ — Database Persistence Target Safety Tests

Validates structural URL parsing and destination verification to guarantee that
test suites and destructive fixture cleanups can NEVER execute against remote
or production databases, even when presented with misleading credentials,
query strings, or similar substrings.
"""

from __future__ import annotations

from typing import Final

import pytest
from sqlalchemy.engine.url import make_url

# Explicit local allowlist for PostgreSQL test targets
ALLOWED_TEST_HOSTS: Final[frozenset[str]] = frozenset({
    "localhost",
    "127.0.0.1",
    "::1",
    "dispenselens-postgres",  # Docker Compose container name
    "postgres",               # Docker Compose service name in Docker network
})

ALLOWED_TEST_DB_EXACT: Final[frozenset[str]] = frozenset({
    "test",
    "dispenselens_test",
})

ALLOWED_TEST_DB_PREFIXES: Final[tuple[str, ...]] = ("test_", "test-")
ALLOWED_TEST_DB_SUFFIXES: Final[tuple[str, ...]] = ("_test", "-test")

# Query parameters that libpq / psycopg can use to redirect the effective host, database, or connection service
FORBIDDEN_DESTINATION_QUERY_KEYS: Final[frozenset[str]] = frozenset({
    "host",
    "hostaddr",
    "port",
    "dbname",
    "database",
    "service",
    "servicefile",
    "passfile",
    "target_session_attrs",
})


def assert_safe_test_database(url: str, dev_url: str | None = None) -> None:
    """Validate that the given database URL points to an approved local test destination.

    Must be executed before any database connection or destructive test operation.
    Fails closed if the destination is remote, missing, malformed, targets a non-test database
    (such as the plain development 'dispenselens' database), targets the same database as
    the development DATABASE_URL, or attempts connection redirection via query parameters.
    Does NOT echo credential-bearing URLs in rejection messages.

    Raises:
        RuntimeError: If the target does not conform to the local test safety policy.
    """
    if not url or not isinstance(url, str) or not url.strip():
        raise RuntimeError("Database safety check failed: DATABASE_URL is empty or not provided.")

    try:
        parsed = make_url(url.strip())
    except Exception as exc:
        raise RuntimeError("Database safety check failed: DATABASE_URL is malformed.") from exc

    # 1. Scheme check: must be PostgreSQL
    drivername = (parsed.drivername or "").lower()
    if not (drivername.startswith("postgresql") or drivername.startswith("postgres")):
        raise RuntimeError(
            f"Database safety check failed: driver '{drivername}' is not PostgreSQL."
        )

    # 2. Host check: must be present and in the explicit local allowlist
    host = parsed.host
    if not host:
        raise RuntimeError("Database safety check failed: database host is missing.")

    host_lower = host.lower()
    if host_lower not in ALLOWED_TEST_HOSTS:
        raise RuntimeError(
            f"Database safety check failed: host '{host_lower}' is not an approved local test host."
        )

    # 3. Database check: must be present and conform to disposable test database policy
    database = parsed.database
    if not database:
        raise RuntimeError("Database safety check failed: database name is missing.")

    db_lower = database.strip().lower()
    is_valid_db = (
        db_lower in ALLOWED_TEST_DB_EXACT
        or db_lower.startswith(ALLOWED_TEST_DB_PREFIXES)
        or db_lower.endswith(ALLOWED_TEST_DB_SUFFIXES)
    )

    if not is_valid_db:
        raise RuntimeError(
            f"Database safety check failed: database name '{db_lower}' does not meet "
            "the disposable test database naming policy."
        )

    # 4. Query parameters check: fail closed against connection redirection or unauthorized query params
    if parsed.query:
        for q_key in parsed.query.keys():
            key_lower = str(q_key).strip().lower()
            if key_lower in FORBIDDEN_DESTINATION_QUERY_KEYS:
                raise RuntimeError(
                    f"Database safety check failed: query parameter '{key_lower}' is forbidden "
                    "because it can redirect the effective connection destination."
                )
        raise RuntimeError(
            "Database safety check failed: query parameters are not permitted on test database URLs."
        )

    # 5. Separation check: if development database URL is present, must not target the same database
    if dev_url and isinstance(dev_url, str) and dev_url.strip():
        try:
            parsed_dev = make_url(dev_url.strip())
            dev_host = (parsed_dev.host or "").lower()
            test_host = (parsed.host or "").lower()
            loopback_hosts = {"localhost", "127.0.0.1", "::1"}
            same_host = (
                (dev_host in loopback_hosts and test_host in loopback_hosts)
                or (dev_host == test_host)
            )
            dev_port = parsed_dev.port or 5432
            test_port = parsed.port or 5432
            dev_db = (parsed_dev.database or "").strip().lower()
            test_db = (parsed.database or "").strip().lower()
            if same_host and dev_port == test_port and dev_db == test_db:
                raise RuntimeError(
                    f"Database safety check failed: TEST_DATABASE_URL resolves to the same database target ('{test_db}') "
                    "as the development DATABASE_URL. A separate disposable test database is required."
                )
        except RuntimeError:
            raise
        except Exception:
            pass


# ===========================================================================
# Connection-Free Safety Unit Tests
# ===========================================================================

def test_approved_local_destinations_pass():
    """Approved local hosts and disposable database names must pass cleanly."""
    valid_urls = [
        "postgresql+psycopg://dispenselens_user:dispenselens_dev_password@localhost:5432/dispenselens_test",
        "postgresql+psycopg://user:pass@127.0.0.1:5432/dispenselens_test",
        "postgresql+psycopg://user:pass@[::1]:5432/dispenselens_test",
        "postgresql+psycopg://user:pass@dispenselens-postgres:5432/dispenselens_test",
        "postgresql+psycopg://user:pass@postgres:5432/dispenselens_test",
        "postgresql+psycopg://user:pass@localhost:5432/test",
        "postgresql+psycopg://user:pass@localhost:5432/test_case_db",
        "postgresql+psycopg://user:pass@localhost:5432/dispenselens_test",
        "postgresql+psycopg://user:pass@127.0.0.1/test-db",
        "postgresql+psycopg://user:pass@127.0.0.1/db-test",
    ]
    for url in valid_urls:
        assert_safe_test_database(url)  # Must not raise


def test_reproduction_finding_r1_remote_contest_url_rejected():
    """Reviewer reproduction URL (remote host with 'contest' database) must be rejected."""
    url = "postgresql+psycopg://user:password@production.example.com/contest"
    with pytest.raises(RuntimeError) as exc_info:
        assert_safe_test_database(url)

    err_msg = str(exc_info.value)
    assert "production.example.com" in err_msg
    assert "password" not in err_msg  # Credentials must NEVER be leaked


def test_remote_host_with_disposable_db_name_rejected():
    """A remote host must be rejected even if the database name is 'test' or 'dispenselens_test'."""
    remote_urls = [
        "postgresql+psycopg://user:secret@production.example.com:5432/dispenselens_test",
        "postgresql+psycopg://user:secret@aws-rds.postgres.com/test",
        "postgresql+psycopg://user:secret@192.168.1.100/test_db",
        "postgresql+psycopg://user:secret@db.internal.corp/dispenselens_test",
    ]
    for url in remote_urls:
        with pytest.raises(RuntimeError) as exc_info:
            assert_safe_test_database(url)
        err_msg = str(exc_info.value)
        assert "not an approved local test host" in err_msg
        assert "secret" not in err_msg


def test_misleading_credentials_or_query_parameters_do_not_trick_guard():
    """Substrings in user, password, or query params must not fool host inspection."""
    adversarial_urls = [
        # 'localhost' and 'postgres' embedded in password or user
        "postgresql+psycopg://localhost_admin:postgres_pass@production.example.com:5432/test",
        "postgresql+psycopg://user:localhost_pass@production.company.com/test_db",
        # 'test' in host, 'localhost' in query param
        "postgresql+psycopg://user:pass@test-server.remote.io:5432/dispenselens_test?host=localhost",
    ]
    for url in adversarial_urls:
        with pytest.raises(RuntimeError) as exc_info:
            assert_safe_test_database(url)
        assert "not an approved local test host" in str(exc_info.value)


def test_non_disposable_database_names_on_local_host_rejected():
    """Non-test database names (like 'contest', 'dispenselens', or 'production') must be rejected even on localhost."""
    non_test_urls = [
        "postgresql+psycopg://user:pass@localhost:5432/contest",
        "postgresql+psycopg://user:pass@localhost:5432/production",
        "postgresql+psycopg://user:pass@localhost:5432/dispenselens",  # Plain development db rejected
        "postgresql+psycopg://user:pass@127.0.0.1:5432/attest",
        "postgresql+psycopg://user:pass@127.0.0.1:5432/latest",
        "postgresql+psycopg://user:pass@localhost:5432/my_project",
        "postgresql+psycopg://user:pass@localhost:5432/prod_test_database",  # 'test' in middle, not prefix/suffix
    ]
    for url in non_test_urls:
        with pytest.raises(RuntimeError) as exc_info:
            assert_safe_test_database(url)
        assert "does not meet the disposable test database naming policy" in str(exc_info.value)


def test_plain_development_database_name_dispenselens_rejected():
    """The plain development database name 'dispenselens' must no longer pass test safety checks."""
    dev_urls = [
        "postgresql+psycopg://dispenselens_user:dispenselens_dev_password@localhost:5432/dispenselens",
        "postgresql+psycopg://user:pass@127.0.0.1:5432/dispenselens",
        "postgresql+psycopg://user:pass@dispenselens-postgres:5432/dispenselens",
    ]
    for url in dev_urls:
        with pytest.raises(RuntimeError) as exc_info:
            assert_safe_test_database(url)
        assert "database name 'dispenselens' does not meet the disposable test database naming policy" in str(exc_info.value)


def test_same_target_as_development_database_rejected():
    """TEST_DATABASE_URL resolving to the same database target as development DATABASE_URL must be rejected."""
    dev_url = "postgresql+psycopg://dispenselens_user:dispenselens_dev_password@localhost:5432/dispenselens_test"
    test_url_same_host = "postgresql+psycopg://dispenselens_user:dispenselens_dev_password@localhost:5432/dispenselens_test"
    test_url_loopback = "postgresql+psycopg://user:pass@127.0.0.1:5432/dispenselens_test"

    with pytest.raises(RuntimeError, match="resolves to the same database target"):
        assert_safe_test_database(test_url_same_host, dev_url=dev_url)

    with pytest.raises(RuntimeError, match="resolves to the same database target"):
        assert_safe_test_database(test_url_loopback, dev_url=dev_url)

    # Different database targets must pass
    different_dev_url = "postgresql+psycopg://user:pass@localhost:5432/dispenselens"
    assert_safe_test_database(test_url_same_host, dev_url=different_dev_url)


def test_missing_host_rejected():
    """URLs lacking a host (e.g. domain sockets or malformed syntax) must fail closed."""
    with pytest.raises(RuntimeError, match="database host is missing"):
        assert_safe_test_database("postgresql+psycopg:///dispenselens_test")


def test_missing_database_name_rejected():
    """URLs without a database path must fail closed."""
    with pytest.raises(RuntimeError, match="database name is missing"):
        assert_safe_test_database("postgresql+psycopg://user:pass@localhost:5432/")
    with pytest.raises(RuntimeError, match="database name is missing"):
        assert_safe_test_database("postgresql+psycopg://user:pass@localhost:5432")


def test_empty_or_malformed_url_rejected():
    """Empty, None-like, or unparseable URLs fail closed."""
    with pytest.raises(RuntimeError, match="DATABASE_URL is empty"):
        assert_safe_test_database("")
    with pytest.raises(RuntimeError, match="DATABASE_URL is empty"):
        assert_safe_test_database("   ")
    with pytest.raises(RuntimeError, match="DATABASE_URL is malformed"):
        assert_safe_test_database("://")


def test_non_postgresql_scheme_rejected():
    """Non-PostgreSQL drivers must be rejected even on localhost/test."""
    with pytest.raises(RuntimeError, match="driver 'sqlite' is not PostgreSQL"):
        assert_safe_test_database("sqlite:///test.db")
    with pytest.raises(RuntimeError, match="driver 'mysql' is not PostgreSQL"):
        assert_safe_test_database("mysql://user:pass@localhost/test")


def test_error_messages_contain_no_credentials():
    """Verify that sensitive user passwords are never exposed in exception strings."""
    url = "postgresql+psycopg://super_secret_user:super_secret_password_123@remote.prod.com:5432/prod_db"
    with pytest.raises(RuntimeError) as exc_info:
        assert_safe_test_database(url)

    err = str(exc_info.value)
    assert "super_secret_password_123" not in err
    assert "super_secret_user" not in err


# ===========================================================================
# Inverse Adversarial Tests: Local URL Authority + Query-Level Redirection
# ===========================================================================

def test_query_parameter_host_override_on_local_authority_rejected():
    """A URL with an approved local authority plus query-level 'host' must be rejected before connection."""
    urls = [
        "postgresql+psycopg://user:pass@localhost:5432/test_db?host=production.example.com",
        "postgresql+psycopg://user:pass@127.0.0.1:5432/dispenselens_test?host=remote.database.net",
        "postgresql+psycopg://user:pass@localhost:5432/dispenselens_test?host=localhost",  # query override forbidden
    ]
    for url in urls:
        with pytest.raises(RuntimeError) as exc_info:
            assert_safe_test_database(url)
        err = str(exc_info.value)
        assert "query parameter 'host' is forbidden" in err
        assert "pass" not in err


def test_query_parameter_hostaddr_override_on_local_authority_rejected():
    """A URL with an approved local authority plus remote 'hostaddr' must be rejected before connection."""
    urls = [
        "postgresql+psycopg://user:pass@localhost:5432/test_db?hostaddr=203.0.113.10",
        "postgresql+psycopg://user:pass@127.0.0.1:5432/dispenselens_test?hostaddr=198.51.100.25",
    ]
    for url in urls:
        with pytest.raises(RuntimeError) as exc_info:
            assert_safe_test_database(url)
        err = str(exc_info.value)
        assert "query parameter 'hostaddr' is forbidden" in err


def test_query_parameter_dbname_override_on_local_authority_rejected():
    """A URL with an approved local authority plus query-level 'dbname'/'database' must be rejected."""
    urls = [
        "postgresql+psycopg://user:pass@localhost:5432/test_db?dbname=production",
        "postgresql+psycopg://user:pass@localhost:5432/test_db?database=prod_db",
        "postgresql+psycopg://user:pass@localhost:5432/test_db?dbname=dispenselens_test",  # cannot bypass via query
    ]
    for url in urls:
        with pytest.raises(RuntimeError) as exc_info:
            assert_safe_test_database(url)
        err = str(exc_info.value)
        assert ("query parameter 'dbname' is forbidden" in err or
                "query parameter 'database' is forbidden" in err)


def test_query_parameter_service_override_on_local_authority_rejected():
    """A URL with an approved local authority plus query-level 'service' must be rejected."""
    urls = [
        "postgresql+psycopg://user:pass@localhost:5432/test_db?service=prod_service",
        "postgresql+psycopg://user:pass@localhost:5432/test_db?servicefile=/etc/pg_service.conf",
    ]
    for url in urls:
        with pytest.raises(RuntimeError) as exc_info:
            assert_safe_test_database(url)
        err = str(exc_info.value)
        assert ("query parameter 'service' is forbidden" in err or
                "query parameter 'servicefile' is forbidden" in err)


def test_query_parameter_port_or_target_session_attrs_rejected():
    """Query-level destination redirection via port or target_session_attrs must be rejected."""
    urls = [
        "postgresql+psycopg://user:pass@localhost:5432/test_db?port=5433",
        "postgresql+psycopg://user:pass@localhost:5432/test_db?target_session_attrs=primary",
    ]
    for url in urls:
        with pytest.raises(RuntimeError) as exc_info:
            assert_safe_test_database(url)
        err = str(exc_info.value)
        assert ("query parameter 'port' is forbidden" in err or
                "query parameter 'target_session_attrs' is forbidden" in err)


def test_arbitrary_query_parameters_fail_closed():
    """Any other query parameters on test database URLs fail closed."""
    urls = [
        "postgresql+psycopg://user:pass@localhost:5432/dispenselens_test?sslmode=disable",
        "postgresql+psycopg://user:pass@localhost:5432/dispenselens_test?connect_timeout=10",
        "postgresql+psycopg://user:pass@localhost:5432/dispenselens_test?application_name=test",
    ]
    for url in urls:
        with pytest.raises(RuntimeError, match="query parameters are not permitted on test database URLs"):
            assert_safe_test_database(url)


def test_adversarial_query_redirection_exposes_no_credentials():
    """Adversarial query redirection URLs must never leak credentials in exception strings."""
    url = "postgresql+psycopg://top_secret_user:super_secret_pw_999@localhost:5432/test_db?host=production.example.com&dbname=prod"
    with pytest.raises(RuntimeError) as exc_info:
        assert_safe_test_database(url)
    err = str(exc_info.value)
    assert "super_secret_pw_999" not in err
    assert "top_secret_user" not in err
