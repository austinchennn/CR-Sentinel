from datetime import datetime, timezone

from dashboard_api.db import DashboardRepository


def test_recent_logs_without_filters(fake_conn):
    fake_conn._results = [
        ("id-1", datetime.now(timezone.utc), "1.1.1.1", "GET", "/admin", "", "", "ua", 200, None, 5),
    ]
    repo = DashboardRepository(fake_conn)

    rows = repo.recent_logs()

    statement, params = fake_conn.executed[0]
    assert "FROM request_logs" in statement
    assert "WHERE" not in statement
    assert params == (100,)
    assert rows[0]["src_ip"] == "1.1.1.1"
    assert rows[0]["status_code"] == 200


def test_recent_logs_filters_by_ip_and_status_code(fake_conn):
    repo = DashboardRepository(fake_conn)

    repo.recent_logs(limit=10, ip="2.2.2.2", status_code=403)

    statement, params = fake_conn.executed[0]
    assert "src_ip = %s" in statement
    assert "status_code = %s" in statement
    assert params == ("2.2.2.2", 403, 10)


def test_active_blacklist_filters_expired(fake_conn):
    fake_conn._results = [("3.3.3.3", "high", None, "sqli")]
    repo = DashboardRepository(fake_conn)

    rows = repo.active_blacklist()

    statement, _ = fake_conn.executed[0]
    assert "block_until IS NULL OR block_until > now()" in statement
    assert rows[0]["ip"] == "3.3.3.3"
    assert rows[0]["block_until"] is None


def test_active_rate_limits(fake_conn):
    fake_conn._results = [("4.4.4.4", 10, datetime.now(timezone.utc))]
    repo = DashboardRepository(fake_conn)

    rows = repo.active_rate_limits()

    statement, _ = fake_conn.executed[0]
    assert "expires_at > now()" in statement
    assert rows[0]["limit_per_min"] == 10


def test_episodes_for_ip_orders_oldest_first(fake_conn):
    fake_conn._results = [
        (datetime.now(timezone.utc), "low", "scan", "probed /admin", "none"),
    ]
    repo = DashboardRepository(fake_conn)

    rows = repo.episodes_for_ip("5.5.5.5", limit=20)

    statement, params = fake_conn.executed[0]
    assert "WHERE ip = %s" in statement
    assert "ORDER BY ts ASC" in statement
    assert params == ("5.5.5.5", 20)
    assert rows[0]["attack_type"] == "scan"
