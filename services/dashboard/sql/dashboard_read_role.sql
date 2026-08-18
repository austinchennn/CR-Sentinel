-- Least-privilege role for the Dashboard read-only API (PRD-07), same
-- convention as services/patrol-agent/sql/patrol_write_role.sql.
--
-- Credentials live in Secrets Manager (PRD-00) and are injected as
-- CRDB_DASHBOARD_* env vars. Separate from both the patrol agent's write
-- channel (INSERT/UPDATE, no SELECT beyond upserts) and its MCP read
-- channel (a CockroachDB Cloud service account, not a SQL user) -- this
-- role can only SELECT, and only from the four tables the dashboard's
-- three views actually read.
--
-- Run with `cockroach sql` or `ccloud`; idempotent, matches PRD-01's
-- migration style.

CREATE ROLE IF NOT EXISTS dashboard_reader WITH LOGIN;

-- Password is set out of band and stored only in Secrets Manager:
--   ALTER USER dashboard_reader WITH PASSWORD '<generated>';
-- Do not commit a password to this file.

GRANT SELECT ON TABLE request_logs TO dashboard_reader;
GRANT SELECT ON TABLE ip_blacklist TO dashboard_reader;
GRANT SELECT ON TABLE ip_rate_limit TO dashboard_reader;
GRANT SELECT ON TABLE agent_episodes TO dashboard_reader;

-- Explicit revokes for auditability, same reasoning as
-- patrol_write_role.sql -- CRDB denies by default, so these are no-ops on
-- a fresh role, but keep this file self-documenting and correct if
-- broader grants are ever added by accident.
REVOKE ALL ON TABLE accounts FROM dashboard_reader;
REVOKE ALL ON TABLE attack_signatures FROM dashboard_reader;
REVOKE ALL ON TABLE task_queue FROM dashboard_reader;
REVOKE ALL ON TABLE alert_log FROM dashboard_reader;
