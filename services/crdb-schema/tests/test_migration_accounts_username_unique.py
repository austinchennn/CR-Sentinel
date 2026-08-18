from pathlib import Path

MIGRATION = Path(__file__).resolve().parents[1] / "migrations" / "002_accounts_username_unique.sql"


def test_migration_file_exists():
    assert MIGRATION.exists()


def test_creates_idempotent_unique_index_on_username():
    text = MIGRATION.read_text()
    assert "CREATE UNIQUE INDEX IF NOT EXISTS accounts_username_key" in text
    assert "ON accounts (username);" in text


def test_no_statement_is_missing_if_not_exists():
    text = MIGRATION.read_text()
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CREATE ") and "IF NOT EXISTS" not in stripped:
            raise AssertionError(f"non-idempotent CREATE statement: {stripped!r}")


def test_seed_accounts_have_no_duplicate_usernames():
    """Confirms the new unique index is safe to apply against
    demo-target-app's seed data (the only current accounts writer) --
    if this ever fails, the migration would fail to apply against a
    freshly seeded cluster."""
    import sys

    demo_app_root = Path(__file__).resolve().parents[2] / "demo-target-app"
    sys.path.insert(0, str(demo_app_root))
    from demo_target_app.seed_accounts import SEED_ACCOUNTS

    usernames = [account["username"] for account in SEED_ACCOUNTS]
    assert len(usernames) == len(set(usernames))
