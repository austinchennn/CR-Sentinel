"""Upserts SEED_ATTACK_SIGNATURES into attack_signatures, embedding each
description with the same Titan model PatrolAgentLambda uses at query
time (docs/01-architecture.md). Re-running this script is safe: (category,
description) has a unique index (migrations/001_core_tables.sql), so every
row is an upsert, never a duplicate -- PRD-01 functional requirement 5.

`psycopg2` is imported lazily inside `main()`, not at module load time,
so `seed()` -- the part with actual logic -- stays testable against a fake
connection without the driver installed (see tests/test_seed_attack_signatures.py).
"""
import logging

from .attack_signature_seed_data import SEED_ATTACK_SIGNATURES

logger = logging.getLogger(__name__)

UPSERT_SQL = """
    INSERT INTO attack_signatures (category, description, severity, embedding)
    VALUES (%s, %s, %s, %s)
    ON CONFLICT (category, description) DO UPDATE
        SET severity = excluded.severity,
            embedding = excluded.embedding
"""


def seed(conn, embed_fn, signatures=SEED_ATTACK_SIGNATURES):
    """embed_fn: str -> list[float]. Injected so tests can use a fake,
    deterministic embedder instead of calling Bedrock; production callers
    pass titan_embeddings.embed_text."""
    with conn.cursor() as cur:
        for sig in signatures:
            embedding = embed_fn(sig["description"])
            cur.execute(UPSERT_SQL, (sig["category"], sig["description"], sig["severity"], embedding))
    conn.commit()
    logger.info("seeded_attack_signatures count=%d", len(signatures))
    return len(signatures)


def main():
    import psycopg2

    from . import titan_embeddings
    from .config import CrdbAdminConfig

    config = CrdbAdminConfig.from_env()
    conn = psycopg2.connect(
        host=config.host,
        port=config.port,
        dbname=config.database,
        user=config.user,
        password=config.password,
        sslmode=config.sslmode,
    )
    seed(conn, titan_embeddings.embed_text)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
