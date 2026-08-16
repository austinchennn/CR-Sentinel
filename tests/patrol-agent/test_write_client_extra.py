"""Covers CrdbWriteClient.connect(), which
services/patrol-agent/tests/test_write_client.py doesn't exercise (it
always constructs CrdbWriteClient directly with a fake connection)."""
from patrol_agent.write_client import CrdbWriteClient


def test_connect_reads_config_from_env_by_default(crdb_write_env, monkeypatch):
    import psycopg2

    calls = []

    def fake_connect(**kwargs):
        calls.append(kwargs)
        return "the-connection"

    monkeypatch.setattr(psycopg2, "connect", fake_connect)

    client = CrdbWriteClient.connect()

    assert client._conn == "the-connection"
    assert calls[0]["host"] == "write.example.com"
    assert calls[0]["user"] == "patrol_write"
    assert calls[0]["password"] == "s3cret"


def test_connect_accepts_an_explicit_config(monkeypatch):
    import psycopg2

    from patrol_agent.config import CrdbWriteConfig

    calls = []
    monkeypatch.setattr(psycopg2, "connect", lambda **kwargs: calls.append(kwargs) or "conn")

    config = CrdbWriteConfig(
        host="explicit.example.com", port="5432", database="db", user="u", password="p", sslmode="disable",
    )
    client = CrdbWriteClient.connect(config=config)

    assert client._conn == "conn"
    assert calls[0]["host"] == "explicit.example.com"
    assert calls[0]["sslmode"] == "disable"
