"""Manual verification for PRD-01 acceptance criterion 3: run one real
vector-search query against a live cluster and eyeball that results rank
by similarity sensibly. Not part of the automated test suite -- needs a
live cluster and Bedrock model access, both of which are only available
once PRD-00 is provisioned.

Usage:
    CRDB_ADMIN_HOST=... CRDB_ADMIN_USER=... CRDB_ADMIN_PASSWORD=... \\
        python -m scripts.verify_semantic_recall "UnIoN sElEcT 1,2,3-- obfuscated sql injection"

Expect the top results to be the sqli-category rows from
crdb_schema/attack_signature_seed_data.py, ranked ahead of unrelated
categories -- that's the "召回质量" PRD-01 asks to eyeball.
"""
import sys

import psycopg2

from crdb_schema import titan_embeddings
from crdb_schema.config import CrdbAdminConfig

DEFAULT_QUERY_TEXT = "UnIoN sElEcT 1,2,3-- obfuscated sql injection"


def main():
    text = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_QUERY_TEXT
    embedding = titan_embeddings.embed_text(text)
    vector_literal = "[" + ", ".join(repr(float(x)) for x in embedding) + "]"

    config = CrdbAdminConfig.from_env()
    conn = psycopg2.connect(
        host=config.host,
        port=config.port,
        dbname=config.database,
        user=config.user,
        password=config.password,
        sslmode=config.sslmode,
    )
    with conn.cursor() as cur:
        cur.execute(
            "SELECT category, description, embedding <-> %s AS distance "
            "FROM attack_signatures ORDER BY embedding <-> %s LIMIT 5",
            (vector_literal, vector_literal),
        )
        for category, description, distance in cur.fetchall():
            print(f"{distance:.4f}  {category:12s}  {description}")


if __name__ == "__main__":
    main()
