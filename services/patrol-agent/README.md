# patrol-agent

MCP connectivity layer for `PatrolAgentLambda` (see
`docs/prd/PRD-03-mcp-connectivity.md`). Two independent channels between
the agent and CockroachDB:

- **Read** -- `patrol_agent.mcp_read_client.McpReadOnlyClient`, over the
  CockroachDB Cloud Managed MCP Server (`https://cockroachlabs.cloud/mcp`,
  read-only). Three methods: `read_recent_logs`,
  `semantic_search_attack_signatures`, `read_ip_episodes`.
- **Write** -- `patrol_agent.write_client.CrdbWriteClient`, a direct
  psycopg2 connection authenticated with a separate least-privilege SQL
  role (`sql/patrol_write_role.sql`). Six methods, one per disposal action:
  `write_blacklist`, `write_rate_limit`, `lock_account`, `write_episode`,
  `write_task`, `write_alert`.

`patrol_agent.memory_gateway.PatrolMemoryGateway` wraps the read channel
so a caller gets one exception type to handle: on any MCP failure
(connect, timeout, tool-level error) it logs once and returns
`PatrolSignals(degraded=True)` with empty lists instead of raising --
PRD-03 functional requirement 6's "skip the round, don't write partial
data" degradation. This repo does not yet call `write_client` from a
degraded round (there's nothing to call it *with* -- Bedrock parsing is
PRD-04), but the split is what makes that guarantee possible: nothing in
this package writes as a side effect of a read.

## MCP tool names -- resolved spike (PRD-03 functional requirement 1)

`docs/01-architecture.md` flagged `run_read_query`/`vector_search` as
placeholder names pending verification against the real Cloud
Console-generated MCP config snippet. Per CockroachDB's own docs for the
managed MCP server, the actual read-only tool is **`select_query`** (plus
introspection tools `list_databases`/`get_table_schema` this project
doesn't need). There is no separate vector-search tool -- semantic recall
runs a normal `SELECT ... ORDER BY embedding <-> $vec LIMIT k` through
`select_query`, and CRDB's vector index accelerates it transparently.
`mcp_read_client.py` is written against that tool name.

What's still unverified against a live cluster (needs the actual
Console-generated config snippet, not just the public docs used here):

- The exact argument name `select_query` expects for the SQL string.
  Defaults to `"sql"`; override via `McpConfig.sql_arg_name` /
  `MCP_SQL_ARG_NAME` if the real snippet says otherwise.
- Whether responses come back as `structuredContent` or a JSON text
  block -- `_rows_from_tool_result` in `mcp_read_client.py` handles both.
- Whether `select_query` accepts bind parameters at all. Because that's
  unconfirmed, `sql_literals.py` inlines values as escaped SQL literals
  rather than assuming parameter support -- this matters for
  `read_ip_episodes(ip=...)`, since `ip` is read back out of
  `request_logs` and can be attacker-influenced (spoofed
  `X-Forwarded-For`).

## Layout

```
patrol_agent/
  config.py          McpConfig / CrdbWriteConfig, read from env vars
  errors.py           McpUnavailableError, CrdbWriteError
  sql_literals.py      Safe literal quoting for the MCP read-only tool
  mcp_read_client.py   Read channel (mcp SDK imported lazily, see below)
  write_client.py      Write channel (psycopg2 imported lazily)
  memory_gateway.py     Combines the three reads with degrade-on-failure
sql/
  patrol_write_role.sql  Least-privilege role/grants for the write channel
tests/                Unit tests against fakes -- no live MCP or CRDB needed
```

`mcp` and `psycopg2` are imported inside the functions that need them
(`_default_session_factory`, `CrdbWriteClient.connect`), not at module
load time, so the rest of the package -- and all the tests -- stay usable
without either driver installed. Same convention as
`services/demo-target-app/demo_target_app/db.py`.

## Configuration

Read channel:

| Env var | Default |
|---|---|
| `MCP_URL` | `https://cockroachlabs.cloud/mcp` |
| `MCP_API_KEY` | required |
| `MCP_TIMEOUT_SECONDS` | `10` |
| `MCP_SQL_ARG_NAME` | `sql` |

Write channel (populated from Secrets Manager at deploy time, same
pattern as `demo-target-app`'s `CRDB_*` vars):

| Env var | Default |
|---|---|
| `CRDB_WRITE_HOST` | required |
| `CRDB_WRITE_PORT` | `26257` |
| `CRDB_WRITE_DATABASE` | `cr_sentinel` |
| `CRDB_WRITE_USER` | required |
| `CRDB_WRITE_PASSWORD` | required |
| `CRDB_WRITE_SSLMODE` | `verify-full` |

## Local development

```bash
pip install -r requirements.txt
python -m pytest -q
```

## Setting up the write role

Requires PRD-00 (cluster reachable) and PRD-01 (target tables exist):

```bash
cockroach sql --url "$CRDB_ADMIN_URL" -f sql/patrol_write_role.sql
cockroach sql --url "$CRDB_ADMIN_URL" \
  --execute "ALTER USER patrol_agent_writer WITH PASSWORD '<generated>';"
```

Then store the generated password in Secrets Manager and wire it into
`CRDB_WRITE_PASSWORD` at deploy time.

## Manual verification against a live cluster (PRD-03 acceptance criteria)

These need a real CockroachDB Cloud cluster and MCP endpoint and aren't
automated here, matching how `demo-target-app/README.md` treats deploy
steps as manual:

1. Confirm the MCP config snippet from Cloud Console matches the
   assumptions above (tool name, arg name, response shape); adjust
   `McpConfig` overrides if not.
2. Query `request_logs` over the read-only MCP connection; attempt an
   `INSERT` over the same connection and confirm it's rejected.
3. Run `semantic_search_attack_signatures` with an embedding for a
   "变形 SQL 注入" (obfuscated SQL injection) description and confirm the
   top results are `category = 'sqli'` rows from PRD-01's seed data.
4. Connect as `patrol_agent_writer` and confirm `write_blacklist` succeeds
   while a direct `INSERT INTO request_logs ...` under the same
   credentials is rejected.
5. Point `MCP_URL` at an unreachable host and confirm
   `PatrolMemoryGateway.gather_signals` returns `degraded=True` with a
   logged reason instead of raising.
