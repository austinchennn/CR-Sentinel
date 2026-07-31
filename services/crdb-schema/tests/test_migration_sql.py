from pathlib import Path

MIGRATION = Path(__file__).resolve().parents[1] / "migrations" / "001_core_tables.sql"

REQUIRED_TABLES = [
    "request_logs",
    "attack_signatures",
    "agent_episodes",
    "ip_blacklist",
    "ip_rate_limit",
    "accounts",
    "task_queue",
    "alert_log",
]


def test_migration_file_exists():
    assert MIGRATION.exists()


def test_every_required_table_is_created_idempotently():
    text = MIGRATION.read_text()
    for table in REQUIRED_TABLES:
        assert f"CREATE TABLE IF NOT EXISTS {table} (" in text, f"missing idempotent create for {table}"


def test_vector_indexes_are_idempotent_and_present_for_both_memory_tables():
    text = MIGRATION.read_text()
    assert "CREATE VECTOR INDEX IF NOT EXISTS attack_signatures_embedding_idx ON attack_signatures (embedding);" in text
    assert "CREATE VECTOR INDEX IF NOT EXISTS agent_episodes_embedding_idx ON agent_episodes (embedding);" in text


def test_embedding_columns_use_1024_dimensions_matching_titan_v2():
    from crdb_schema.titan_embeddings import EMBEDDING_DIMENSIONS

    text = MIGRATION.read_text()
    assert text.count(f"VECTOR({EMBEDDING_DIMENSIONS})") == 2


def test_seeding_upsert_key_exists():
    text = MIGRATION.read_text()
    assert "CREATE UNIQUE INDEX IF NOT EXISTS attack_signatures_category_description_key" in text
    assert "ON attack_signatures (category, description);" in text


def test_no_statement_is_missing_if_not_exists():
    # Every CREATE TABLE / CREATE INDEX / CREATE VECTOR INDEX in this file
    # must be idempotent -- a bare CREATE would break PRD-01's "re-runnable
    # migration" requirement the moment someone re-runs it.
    text = MIGRATION.read_text()
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CREATE ") and "IF NOT EXISTS" not in stripped:
            raise AssertionError(f"non-idempotent CREATE statement: {stripped!r}")
