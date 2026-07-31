# crdb-schema

CockroachDB schema, vector indexes, and attack-signature seed data for
CR-Sentinel's agentic memory model (see
`docs/prd/PRD-01-crdb-schema-memory.md` and `docs/01-architecture.md`
section 3). This is the schema `services/patrol-agent` (PRD-03) and
`services/demo-target-app` (PRD-02) both read/write against.

## Layout

```
migrations/
  001_core_tables.sql     All 8 tables + vector indexes, idempotent
crdb_schema/
  config.py                 CrdbAdminConfig -- DDL/seeding credentials
  titan_embeddings.py        embed_text() wrapping Bedrock Titan V2
  attack_signature_seed_data.py   The 17 seed descriptions (5 categories)
  seed_attack_signatures.py        Embeds + upserts the seed list
scripts/
  run_migrations.sh          Applies migrations/*.sql via cockroach sql
  verify_semantic_recall.py  Manual: run one real vector-search query
tests/                     Unit tests against fakes -- no live cluster needed
```

`psycopg2` and `boto3` are imported lazily inside the functions that need
them (`seed_attack_signatures.main()`, `titan_embeddings.embed_text()`),
not at module load time -- same convention as `demo_target_app/db.py` and
`patrol_agent/write_client.py` in the sibling services. The pure logic
(seed data validation, upsert SQL construction, Titan request/response
shape, migration file idempotency) is unit tested against fakes; anything
that needs a live cluster or real Bedrock access is a manual step below,
same split `demo-target-app`'s README uses for its own deploy steps.

## Applying the migration

Requires PRD-00 (cluster reachable, admin credentials available):

```bash
export CRDB_ADMIN_URL="postgresql://<user>:<password>@<host>:26257/cr_sentinel?sslmode=verify-full"
./scripts/run_migrations.sh
```

Idempotent -- every `CREATE TABLE`/`CREATE INDEX`/`CREATE VECTOR INDEX` in
`migrations/001_core_tables.sql` uses `IF NOT EXISTS` (enforced by
`tests/test_migration_sql.py`), so re-running it against an existing
cluster is safe.

## Seeding attack_signatures

```bash
pip install -r requirements.txt
export CRDB_ADMIN_HOST=... CRDB_ADMIN_USER=... CRDB_ADMIN_PASSWORD=...
# AWS credentials with bedrock:InvokeModel on amazon.titan-embed-text-v2:0
python -m crdb_schema.seed_attack_signatures
```

Re-running this is also safe: `(category, description)` has a unique
index, so every row is an upsert (`ON CONFLICT ... DO UPDATE`), never a
duplicate.

## What's genuinely unverified against a live cluster

Same honesty pattern as `services/patrol-agent/README.md` -- these are
called out rather than assumed correct, and are what PRD-01's acceptance
criteria actually require checking:

- `CREATE VECTOR INDEX IF NOT EXISTS ...` syntax -- confirmed CockroachDB
  supports `CREATE VECTOR INDEX`, but `IF NOT EXISTS` support on that
  specific statement form hasn't been run against a real cluster yet.
- The `<->` distance operator (L2) is what `patrol_agent/mcp_read_client.py`
  already assumes for `ORDER BY embedding <-> ...`; confirm the vector
  index actually accelerates that operator on this CRDB version rather
  than falling back to a full scan.
- Whether the target CRDB version's `VECTOR` type and Titan V2's 1024-dim
  output line up without truncation/padding -- PRD-00's job per the
  architecture doc's risk list, re-confirm here since this is where the
  column type is actually declared.

## Manual verification checklist (PRD-01 acceptance criteria)

1. `cockroach sql --url $CRDB_ADMIN_URL --execute '\d'` shows all 8 tables.
2. `SHOW INDEXES FROM attack_signatures` / `FROM agent_episodes` shows the
   vector indexes.
3. `python -m crdb_schema.seed_attack_signatures` seeds successfully, then:
   ```bash
   python -m scripts.verify_semantic_recall "UnIoN sElEcT 1,2,3-- obfuscated sql injection"
   ```
   top results should be `sqli`-category rows, ranked ahead of unrelated
   categories.
4. Seed data covers all 5 required categories (enforced by
   `tests/test_seed_data.py`; this just confirms the rows landed in CRDB).
5. Re-run `./scripts/run_migrations.sh` and
   `python -m crdb_schema.seed_attack_signatures` a second time -- both
   should exit cleanly with no duplicate rows (`SELECT count(*) FROM
   attack_signatures` unchanged).

## Local development

```bash
pip install -r requirements.txt
python -m pytest -q
```
