import pytest

from crdb_schema.config import CrdbAdminConfig


def test_from_env_uses_required_vars_and_defaults(crdb_admin_env):
    config = CrdbAdminConfig.from_env()

    assert config.host == "admin.example.com"
    assert config.user == "admin"
    assert config.password == "s3cret"
    assert config.port == "26257"
    assert config.database == "cr_sentinel"
    assert config.sslmode == "verify-full"


def test_from_env_respects_overrides(crdb_admin_env, monkeypatch):
    monkeypatch.setenv("CRDB_ADMIN_PORT", "5432")
    monkeypatch.setenv("CRDB_ADMIN_DATABASE", "custom_db")
    monkeypatch.setenv("CRDB_ADMIN_SSLMODE", "disable")

    config = CrdbAdminConfig.from_env()

    assert config.port == "5432"
    assert config.database == "custom_db"
    assert config.sslmode == "disable"


def test_from_env_raises_when_required_var_missing(monkeypatch):
    monkeypatch.delenv("CRDB_ADMIN_HOST", raising=False)
    monkeypatch.delenv("CRDB_ADMIN_USER", raising=False)
    monkeypatch.delenv("CRDB_ADMIN_PASSWORD", raising=False)

    with pytest.raises(KeyError):
        CrdbAdminConfig.from_env()
