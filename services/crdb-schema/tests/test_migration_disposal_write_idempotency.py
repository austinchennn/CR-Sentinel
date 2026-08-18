from pathlib import Path

MIGRATION = Path(__file__).resolve().parents[1] / "migrations" / "003_disposal_write_idempotency.sql"

TABLES = ("agent_episodes", "task_queue", "alert_log")


def test_migration_file_exists():
    assert MIGRATION.exists()


def test_adds_idempotency_key_column_to_all_three_tables():
    text = MIGRATION.read_text()
    for table in TABLES:
        assert f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS idempotency_key STRING;" in text


def test_creates_unique_index_on_idempotency_key_for_all_three_tables():
    text = MIGRATION.read_text()
    for table in TABLES:
        assert f"CREATE UNIQUE INDEX IF NOT EXISTS {table}_idempotency_key_key ON {table} (idempotency_key);" in text


def test_no_statement_is_missing_if_not_exists():
    text = MIGRATION.read_text()
    for line in text.splitlines():
        stripped = line.strip()
        if (stripped.startswith("CREATE ") or stripped.startswith("ALTER TABLE")) and "IF NOT EXISTS" not in stripped:
            raise AssertionError(f"non-idempotent statement: {stripped!r}")
