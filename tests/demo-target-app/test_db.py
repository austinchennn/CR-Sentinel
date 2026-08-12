"""Covers demo_target_app/db.py, which has no dedicated unit tests in
services/demo-target-app/tests/ (existing tests only exercise handlers
against tests/conftest.py's FakeRepository, never CockroachRepository
itself)."""
import time

from demo_target_app.db import CockroachRepository, now_ms


def test_log_request_inserts_all_fields_and_commits(fake_conn):
    repo = CockroachRepository(fake_conn)

    repo.log_request(
        src_ip="203.0.113.5", method="POST", path="/login", query_params="a=1",
        body_snippet="{}", user_agent="pytest", status_code=200, user_id="u-1001",
        response_time_ms=12,
    )

    statement, params = fake_conn.executed[0]
    assert "INSERT INTO request_logs" in statement
    assert params[1:] == ("203.0.113.5", "POST", "/login", "a=1", "{}", "pytest", 200, "u-1001", 12)
    assert fake_conn.committed == 1


def test_log_request_uses_defaults_for_optional_fields(fake_conn):
    repo = CockroachRepository(fake_conn)

    repo.log_request(src_ip="203.0.113.5", method="GET", path="/admin")

    _, params = fake_conn.executed[0]
    assert params[1:] == ("203.0.113.5", "GET", "/admin", "", "", "", 200, None, 0)


def test_get_account_by_user_id_found(fake_conn):
    fake_conn.queue_fetchone(("u-1001", "alice", False, None))
    repo = CockroachRepository(fake_conn)

    account = repo.get_account_by_user_id("u-1001")

    assert account == {"user_id": "u-1001", "username": "alice", "locked": False, "locked_reason": None}
    statement, params = fake_conn.executed[0]
    assert "SELECT user_id, username, locked, locked_reason FROM accounts WHERE user_id = %s" in statement
    assert params == ("u-1001",)


def test_get_account_by_user_id_not_found(fake_conn):
    repo = CockroachRepository(fake_conn)

    assert repo.get_account_by_user_id("ghost") is None


def test_get_account_by_username_found(fake_conn):
    fake_conn.queue_fetchone(("u-1002", "bob", True, "brute force"))
    repo = CockroachRepository(fake_conn)

    account = repo.get_account_by_username("bob")

    assert account["locked"] is True
    assert account["locked_reason"] == "brute force"
    statement, params = fake_conn.executed[0]
    assert "WHERE username = %s" in statement
    assert params == ("bob",)


def test_lock_account_updates_and_commits(fake_conn):
    repo = CockroachRepository(fake_conn)

    repo.lock_account("u-1002", "brute force detected")

    statement, params = fake_conn.executed[0]
    assert "UPDATE accounts" in statement
    assert "locked = true" in statement
    assert params == ("brute force detected", "u-1002")
    assert fake_conn.committed == 1


def test_upsert_account_inserts_with_conflict_clause(fake_conn):
    repo = CockroachRepository(fake_conn)

    repo.upsert_account("u-1001", "alice", locked=False, locked_reason=None)

    statement, params = fake_conn.executed[0]
    assert "INSERT INTO accounts" in statement
    assert "ON CONFLICT (user_id) DO UPDATE" in statement
    assert params == ("u-1001", "alice", False, None)
    assert fake_conn.committed == 1


def test_is_ip_blacklisted_true_when_row_found(fake_conn):
    fake_conn.queue_fetchone((1,))
    repo = CockroachRepository(fake_conn)

    assert repo.is_ip_blacklisted("198.51.100.9") is True


def test_is_ip_blacklisted_false_when_no_row(fake_conn):
    repo = CockroachRepository(fake_conn)

    assert repo.is_ip_blacklisted("203.0.113.5") is False


def test_get_active_rate_limit_returns_limit_when_present(fake_conn):
    fake_conn.queue_fetchone((10,))
    repo = CockroachRepository(fake_conn)

    assert repo.get_active_rate_limit("203.0.113.5") == 10


def test_get_active_rate_limit_returns_none_when_absent(fake_conn):
    repo = CockroachRepository(fake_conn)

    assert repo.get_active_rate_limit("203.0.113.5") is None


def test_count_recent_requests_returns_count(fake_conn):
    fake_conn.queue_fetchone((7,))
    repo = CockroachRepository(fake_conn)

    count = repo.count_recent_requests("203.0.113.5", window_seconds=60)

    assert count == 7
    statement, params = fake_conn.executed[0]
    assert "FROM request_logs" in statement
    assert params == ("203.0.113.5", 60)


def test_count_recent_requests_returns_zero_when_no_row(fake_conn):
    repo = CockroachRepository(fake_conn)

    assert repo.count_recent_requests("203.0.113.5") == 0


def test_connect_reads_env_vars_and_wraps_psycopg2_connection(crdb_env, monkeypatch):
    import psycopg2

    calls = []

    def fake_connect(**kwargs):
        calls.append(kwargs)
        return "the-connection"

    monkeypatch.setattr(psycopg2, "connect", fake_connect)

    repo = CockroachRepository.connect()

    assert repo._conn == "the-connection"
    assert calls[0]["host"] == "db.example.com"
    assert calls[0]["user"] == "app"
    assert calls[0]["password"] == "s3cret"
    assert calls[0]["port"] == "26257"
    assert calls[0]["dbname"] == "cr_sentinel"
    assert calls[0]["sslmode"] == "verify-full"


def test_now_ms_returns_current_time_in_milliseconds():
    before = int(time.time() * 1000)
    result = now_ms()
    after = int(time.time() * 1000)

    assert before <= result <= after
