-- Least-privilege role for the PatrolAgentLambda write channel (PRD-03).
--
-- Credentials for this role live in Secrets Manager (PRD-00) and are
-- injected into PatrolAgentLambda as CRDB_WRITE_* env vars. They are never
-- reused for the MCP read channel (which authenticates as a separate
-- CockroachDB Cloud service account via API key, not SQL user/password).
--
-- Run with `cockroach sql` or `ccloud`; idempotent, matches the migration
-- style set by PRD-01.

CREATE ROLE IF NOT EXISTS patrol_agent_writer WITH LOGIN;

-- Password is set out of band and stored only in Secrets Manager:
--   ALTER USER patrol_agent_writer WITH PASSWORD '<generated>';
-- Do not commit a password to this file.

-- Six disposal methods (write_client.py) map to grants on six tables.
-- INSERT/UPDATE only -- no DELETE, DROP, or ALTER, and no SELECT beyond
-- what's needed to do an upsert.
GRANT INSERT, UPDATE ON TABLE ip_blacklist TO patrol_agent_writer;
GRANT INSERT, UPDATE ON TABLE ip_rate_limit TO patrol_agent_writer;
GRANT UPDATE ON TABLE accounts TO patrol_agent_writer;
GRANT INSERT ON TABLE agent_episodes TO patrol_agent_writer;
GRANT INSERT ON TABLE task_queue TO patrol_agent_writer;
GRANT INSERT ON TABLE alert_log TO patrol_agent_writer;

-- Explicit revokes for auditability. CRDB denies by default, so these are
-- no-ops on a fresh role -- they exist so this script stays correct (and
-- self-documenting) if broader grants are ever added by accident and need
-- undoing, and so PRD-03's acceptance check has a single file to point at.
REVOKE ALL ON TABLE request_logs FROM patrol_agent_writer;
REVOKE ALL ON TABLE attack_signatures FROM patrol_agent_writer;
