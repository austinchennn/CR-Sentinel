"""Covers seed_accounts.seed() and its `if __name__ == "__main__"` guard,
which services/demo-target-app/tests/ doesn't test directly (SEED_ACCOUNTS/
WEAK_CREDENTIALS are only used indirectly via the `repo` fixture)."""
import runpy
import sys

from demo_target_app.seed_accounts import SEED_ACCOUNTS, seed


class _FakeRepo:
    def __init__(self):
        self.upserted = []

    def upsert_account(self, **kwargs):
        self.upserted.append(kwargs)


def test_seed_upserts_every_seed_account():
    repo = _FakeRepo()

    seed(repo)

    assert len(repo.upserted) == len(SEED_ACCOUNTS)
    assert repo.upserted[0]["username"] == "alice"


def test_dunder_main_guard_connects_and_seeds(crdb_env, monkeypatch, capsys):
    import psycopg2

    fake_conn = object()
    monkeypatch.setattr(psycopg2, "connect", lambda **kwargs: fake_conn)

    upserted = []
    import demo_target_app.db as db_mod

    monkeypatch.setattr(db_mod.CockroachRepository, "upsert_account", lambda self, **kwargs: upserted.append(kwargs))
    monkeypatch.delitem(sys.modules, "demo_target_app.seed_accounts", raising=False)

    runpy.run_module("demo_target_app.seed_accounts", run_name="__main__")

    assert len(upserted) == len(SEED_ACCOUNTS)
    assert f"seeded {len(SEED_ACCOUNTS)} accounts" in capsys.readouterr().out
