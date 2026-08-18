-- Adds a round-scoped idempotency key to the three disposal-write tables
-- that were only protected by a random UUID PRIMARY KEY, not a natural
-- key -- unlike ip_blacklist/ip_rate_limit (already ON CONFLICT (ip)
-- upserts), a Lambda retry that re-ran the same patrol round could insert
-- a duplicate agent_episodes/task_queue/alert_log row (PRD-09 acceptance
-- criterion 5, see docs/06-production-readiness.md §4 for the analysis
-- of why this wasn't safe to fix with a content-based key instead --
-- agent_episodes deliberately holds multiple rows per IP over time, and
-- deduping on content would collapse legitimate consecutive verdicts).
--
-- `idempotency_key` is computed by patrol_loop.py's
-- _compute_round_idempotency_key: a hash of (ip, sorted request_logs.id's
-- judged this round). A Lambda retry that re-reads the identical
-- underlying rows for an IP produces the same key; write_client.py's
-- INSERT ... ON CONFLICT (idempotency_key) DO NOTHING then recognizes it
-- as the same event instead of a new one.
--
-- Nullable and additive: existing rows (written before this migration)
-- get idempotency_key = NULL, which a UNIQUE index never treats as a
-- conflict (standard SQL NULL != NULL semantics) -- only new rows written
-- by the updated write_client.py populate and get protected by it.
-- Idempotent and additive, same convention as 001/002.

ALTER TABLE agent_episodes ADD COLUMN IF NOT EXISTS idempotency_key STRING;
CREATE UNIQUE INDEX IF NOT EXISTS agent_episodes_idempotency_key_key ON agent_episodes (idempotency_key);

ALTER TABLE task_queue ADD COLUMN IF NOT EXISTS idempotency_key STRING;
CREATE UNIQUE INDEX IF NOT EXISTS task_queue_idempotency_key_key ON task_queue (idempotency_key);

ALTER TABLE alert_log ADD COLUMN IF NOT EXISTS idempotency_key STRING;
CREATE UNIQUE INDEX IF NOT EXISTS alert_log_idempotency_key_key ON alert_log (idempotency_key);
