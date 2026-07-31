import pytest

from patrol_agent.errors import CrdbWriteError
from patrol_agent.write_client import CrdbWriteClient


def test_write_blacklist_upserts(fake_conn):
    client = CrdbWriteClient(fake_conn)
    client.write_blacklist("203.0.113.5", "high", "2026-08-01T00:00:00Z", "sqli")

    statement, params = fake_conn.executed[0]
    assert "INSERT INTO ip_blacklist" in statement
    assert "ON CONFLICT (ip) DO UPDATE" in statement
    assert params == ("203.0.113.5", "high", "2026-08-01T00:00:00Z", "sqli")
    assert fake_conn.committed == 1


def test_write_rate_limit_upserts(fake_conn):
    client = CrdbWriteClient(fake_conn)
    client.write_rate_limit("203.0.113.5", 10, "2026-08-01T00:00:00Z")

    statement, params = fake_conn.executed[0]
    assert "INSERT INTO ip_rate_limit" in statement
    assert params == ("203.0.113.5", 10, "2026-08-01T00:00:00Z")


def test_lock_account_updates_by_user_id(fake_conn):
    client = CrdbWriteClient(fake_conn)
    client.lock_account("u-1001", "credential stuffing")

    statement, params = fake_conn.executed[0]
    assert "UPDATE accounts" in statement
    assert params == ("credential stuffing", "u-1001")


def test_write_episode_inserts_with_embedding(fake_conn):
    client = CrdbWriteClient(fake_conn)
    embedding = [0.1, 0.2, 0.3]
    client.write_episode(
        ip="203.0.113.5",
        risk_level="high",
        attack_type="sqli",
        reasoning_summary="repeated sleep() timing probes",
        action_taken="blacklist",
        embedding=embedding,
    )

    statement, params = fake_conn.executed[0]
    assert "INSERT INTO agent_episodes" in statement
    assert params[1:] == ("203.0.113.5", "high", "sqli", "repeated sleep() timing probes", "blacklist", embedding)


def test_write_task_defaults_to_pending(fake_conn):
    client = CrdbWriteClient(fake_conn)
    client.write_task("harden_endpoint", {"path": "/admin"})

    statement, params = fake_conn.executed[0]
    assert "task_queue" in statement
    assert params[1:] == ("harden_endpoint", {"path": "/admin"})


def test_write_alert_inserts(fake_conn):
    client = CrdbWriteClient(fake_conn)
    client.write_alert("high", "IP 203.0.113.5 blacklisted for sqli")

    statement, params = fake_conn.executed[0]
    assert "alert_log" in statement
    assert params[1:] == ("high", "IP 203.0.113.5 blacklisted for sqli")


def test_write_failure_rolls_back_and_raises_crdb_write_error(fake_conn):
    fake_conn.fail_next = True
    client = CrdbWriteClient(fake_conn)

    with pytest.raises(CrdbWriteError):
        client.write_alert("high", "boom")

    assert fake_conn.rolled_back == 1
    assert fake_conn.committed == 0
