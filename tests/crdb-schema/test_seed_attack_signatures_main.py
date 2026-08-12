"""Covers seed_attack_signatures.main() and its `if __name__ == "__main__"`
guard, which services/crdb-schema/tests/test_seed_attack_signatures.py
doesn't exercise (it only calls seed() directly against a fake connection).
"""
import runpy
import sys

import crdb_schema.seed_attack_signatures as seed_mod
from crdb_schema import titan_embeddings
from crdb_schema.attack_signature_seed_data import SEED_ATTACK_SIGNATURES


def _patch_pipeline(monkeypatch, fake_conn):
    import psycopg2

    connect_calls = []

    def fake_connect(**kwargs):
        connect_calls.append(kwargs)
        return fake_conn

    monkeypatch.setattr(psycopg2, "connect", fake_connect)
    monkeypatch.setattr(titan_embeddings, "embed_text", lambda text: [1.0])
    return connect_calls


def test_main_connects_with_admin_config_and_seeds_every_signature(crdb_admin_env, monkeypatch, fake_conn):
    connect_calls = _patch_pipeline(monkeypatch, fake_conn)

    seed_mod.main()

    assert connect_calls[0]["host"] == "admin.example.com"
    assert connect_calls[0]["user"] == "admin"
    assert len(fake_conn.executed) == len(SEED_ATTACK_SIGNATURES)
    assert fake_conn.committed == 1


def test_dunder_main_guard_runs_main(crdb_admin_env, monkeypatch, fake_conn):
    _patch_pipeline(monkeypatch, fake_conn)
    monkeypatch.delitem(sys.modules, "crdb_schema.seed_attack_signatures", raising=False)

    runpy.run_module("crdb_schema.seed_attack_signatures", run_name="__main__")

    assert len(fake_conn.executed) == len(SEED_ATTACK_SIGNATURES)
