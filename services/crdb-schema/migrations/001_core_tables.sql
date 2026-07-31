-- PRD-01: core schema for CR-Sentinel's agentic memory model.
--
-- Idempotent by design (PRD-01 functional requirement 5): every statement
-- uses IF NOT EXISTS so this can be re-run against an existing cluster
-- (teammate onboarding, demo environment rebuild) without erroring. Run
-- with `cockroach sql -f` or `ccloud sql --file` (see scripts/run_migrations.sh).
--
-- Table/column definitions match docs/01-architecture.md section 3.
-- Embedding dimension (1024) matches Titan Embeddings V2's default output
-- size -- see services/crdb-schema/crdb_schema/titan_embeddings.py.

CREATE TABLE IF NOT EXISTS request_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ts TIMESTAMPTZ DEFAULT now(),
  src_ip STRING,
  method STRING,
  path STRING,
  query_params STRING,
  body_snippet STRING,
  user_agent STRING,
  status_code INT,
  user_id STRING,
  response_time_ms INT
);
CREATE INDEX IF NOT EXISTS request_logs_ts_src_ip_idx ON request_logs (ts, src_ip);

CREATE TABLE IF NOT EXISTS attack_signatures (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  category STRING,          -- sqli/xss/idor/bruteforce/phishing/...
  description STRING,
  severity STRING,
  embedding VECTOR(1024),   -- Titan Embeddings V2 dimension
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE VECTOR INDEX IF NOT EXISTS attack_signatures_embedding_idx ON attack_signatures (embedding);
-- Not part of the base DDL in docs/01-architecture.md -- added so
-- crdb_schema/seed_attack_signatures.py can upsert idempotently instead
-- of accumulating duplicate rows on every re-run (PRD-01 functional
-- requirement 5). Editing a seeded description's text creates a new row
-- rather than updating the old one in place -- keep wording stable.
CREATE UNIQUE INDEX IF NOT EXISTS attack_signatures_category_description_key
  ON attack_signatures (category, description);

CREATE TABLE IF NOT EXISTS agent_episodes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ts TIMESTAMPTZ DEFAULT now(),
  ip STRING,
  risk_level STRING,        -- normal/low/high
  attack_type STRING,
  reasoning_summary STRING, -- Claude's reasoning output
  action_taken STRING,
  embedding VECTOR(1024),
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE VECTOR INDEX IF NOT EXISTS agent_episodes_embedding_idx ON agent_episodes (embedding);
CREATE INDEX IF NOT EXISTS agent_episodes_ip_ts_idx ON agent_episodes (ip, ts);

CREATE TABLE IF NOT EXISTS ip_blacklist (
  ip STRING PRIMARY KEY,
  risk_level STRING,
  block_until TIMESTAMPTZ,
  attack_reason STRING,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ip_rate_limit (
  ip STRING PRIMARY KEY,
  limit_per_min INT,
  expires_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS accounts (
  user_id STRING PRIMARY KEY,
  username STRING,
  locked BOOL DEFAULT false,
  locked_reason STRING,
  force_logout_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS task_queue (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  type STRING,
  payload JSONB,
  status STRING DEFAULT 'pending',
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS alert_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ts TIMESTAMPTZ DEFAULT now(),
  severity STRING,
  message STRING,
  sent BOOL DEFAULT false
);
