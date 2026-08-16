# patrol-agent

`PatrolAgentLambda`: the EventBridge-triggered inference loop (PRD-04),
built on the MCP connectivity layer (PRD-03). Two independent channels
between the agent and CockroachDB:

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
data" degradation.

## Dependency inversion

`patrol_agent.interfaces` declares `typing.Protocol` contracts (`ReadClient`,
`WriteClient`, `Judge`, `AlertPublisher`, `SignalsGateway`, `EmbedFn`) for
every collaborator `run_patrol_round` and `PatrolMemoryGateway` take as a
parameter instead of constructing internally. Python's structural typing
means the concrete adapters (`McpReadOnlyClient`, `CrdbWriteClient`,
`BedrockJudge`, `SnsAlertPublisher`) already satisfy these without
inheriting from or importing `interfaces.py` -- so do the `Fake*` test
doubles in `tests/`. This is a documentation/type-checker layer over DI
that already existed (`app.py`'s composition root builds every adapter and
passes it in), not a behavior change: it exists so a new adapter -- a
second `WriteClient` backed by a different store, say -- has one file that
states the full contract instead of reverse-engineering it from
`CrdbWriteClient`.

## Patrol round orchestration (PRD-04)

`patrol_agent.patrol_loop.run_patrol_round` is the main loop, wired
together in `patrol_agent.app.patrol_handler` (the Lambda entry point
EventBridge invokes):

1. `PatrolMemoryGateway.gather_signals` reads the last `window_minutes` of
   `request_logs` once for the round. If the MCP channel is down, the
   round is skipped entirely (`RoundSummary(degraded=True)`).
2. `patrol_agent.heuristics.flag_suspicious_ips` groups those logs by
   `src_ip` and keeps only IPs with a frequency spike or an
   attack-shaped status code/payload -- a cheap pre-filter so every IP in
   the window doesn't cost an embedding call plus a Bedrock call.
3. Per suspicious IP: embed a summary of its rows
   (`patrol_agent.embeddings.embed_text`), recall similar
   `attack_signatures` and this IP's `agent_episodes` history over the
   read channel, and assemble a prompt (`patrol_agent.prompt_builder`)
   combining raw logs + recalled attack signatures + episodic memory +
   static business rules about the demo app's endpoints.
4. `patrol_agent.bedrock_judge.BedrockJudge` calls Bedrock Claude's
   Converse API with `toolChoice` pinned to a single
   `emit_patrol_verdict` tool, so the response is always the structured
   `{ip, risk_level, attack_type, reasoning, action}` schema PRD-04 asks
   for -- never free text to parse.
5. `_dispatch_verdict` branches on `risk_level`: `normal` writes nothing;
   `low` writes one `agent_episodes` row; `high` executes the disposal
   action from Claude's `action.type` (`blacklist_temporary`,
   `blacklist_permanent`, `rate_limit`, `lock_account`, or `task_queue`)
   via `write_client`, writes `alert_log`, publishes the same message to
   SNS and marks the row `sent` (PRD-06, see below), then writes
   `agent_episodes`. A `block_until = NULL` blacklist row is this
   codebase's convention for "permanent" -- PRD-05's gateway lookup should
   honor `block_until IS NULL OR block_until > now()`.

## Alerting (PRD-06)

`patrol_agent.alerting` is the human-facing half of a `high` verdict:

- `format_alert_message(verdict, action_type)` builds one `(subject,
  body)` pair -- the body becomes both `alert_log.message` (queryable
  audit trail) and the SNS email (human-facing), so there's one source of
  truth for "what does a security engineer need to know without
  re-querying the DB": IP, risk level, attack type, action taken, AI
  reasoning, timestamp.
- `SnsAlertPublisher` wraps `boto3.client("sns").publish` against the
  Topic ARN from `SNS_TOPIC_ARN` (the `AlertTopic` resource in
  `template.yaml`, subscribed to `AlertEmail` at deploy time).

In `_dispatch_verdict`, publishing to SNS and marking `alert_log.sent =
true` happens in its own try/except, deliberately separate from the outer
`CrdbWriteError` handling -- a flaky SNS call (or a failed `sent` update)
must not skip the `agent_episodes` write that follows it. The `alert_log`
row itself is already written by that point either way; `sent` only
tracks whether the email side succeeded, so a re-run doesn't double-send
a row that already went out.

Every per-IP step (embedding, MCP reads, Bedrock call, disposal write) is
wrapped so one IP's failure is logged and skipped rather than aborting the
rest of the round or the next EventBridge cycle.

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
  interfaces.py     typing.Protocol contracts for the DI seams below (ReadClient/WriteClient/Judge/AlertPublisher/SignalsGateway/EmbedFn)
  config.py          McpConfig / CrdbWriteConfig / BedrockConfig / PatrolConfig / SnsConfig
  errors.py           McpUnavailableError, CrdbWriteError, BedrockJudgeError
  sql_literals.py      Safe literal quoting for the MCP read-only tool
  mcp_read_client.py   Read channel (mcp SDK imported lazily, see below)
  write_client.py      Write channel (psycopg2 imported lazily)
  memory_gateway.py     Combines the three reads with degrade-on-failure
  embeddings.py         Query-time Titan embedding wrapper (PRD-04)
  heuristics.py          Suspicious-IP pre-filter over a log window (PRD-04)
  prompt_builder.py       Static business rules + verdict tool schema + prompt assembly (PRD-04)
  bedrock_judge.py         Bedrock Converse tool-use call + verdict parsing (PRD-04)
  alerting.py               SNS email alerting for high-risk verdicts (PRD-06)
  patrol_loop.py            run_patrol_round: ties everything above together (PRD-04)
  app.py                     Lambda entry point EventBridge invokes (PRD-04)
sql/
  patrol_write_role.sql  Least-privilege role/grants for the write channel
template.yaml         SAM template: PatrolAgentLambda + EventBridge Scheduler rule + SNS AlertTopic
tests/                Unit tests against fakes -- no live MCP, CRDB, or Bedrock needed
```

`mcp`, `psycopg2`, and `boto3` are imported inside the functions that need
them (`_default_session_factory`, `CrdbWriteClient.connect`,
`embed_text`, `BedrockJudge.__init__`), not at module load time, so the
rest of the package -- and all the tests -- stay usable without any driver
installed. Same convention as
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

Bedrock and patrol-round tuning:

| Env var | Default |
|---|---|
| `BEDROCK_MODEL_ID` | `anthropic.claude-3-5-sonnet-20241022-v2:0` (override once the model actually approved under PRD-00 is known) |
| `PATROL_WINDOW_MINUTES` | `5` |
| `PATROL_TOP_K` | `5` |
| `PATROL_IP_HISTORY_LIMIT` | `20` |
| `PATROL_HIGH_FREQUENCY_THRESHOLD` | `20` |

Alerting (PRD-06):

| Env var | Default |
|---|---|
| `SNS_TOPIC_ARN` | required (the `AlertTopic` Output from `template.yaml`) |

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

## Manual verification against a live cluster + Bedrock (PRD-04 acceptance criteria)

Also needs live Bedrock model access (see PRD-00) in addition to the CRDB
cluster and MCP endpoint above:

1. Deploy `template.yaml` (or invoke `patrol_agent.app.patrol_handler`
   locally with env vars set) and confirm one full round -- read logs,
   recall, prompt assembly, Bedrock verdict -- completes without error
   against seeded traffic.
2. Run it against 10 different suspicious-request fixtures and confirm
   `BedrockJudge.judge` never raises `BedrockJudgeError` for a
   well-formed request (the forced `toolChoice` is what should guarantee
   this; a failure here means the tool schema needs adjusting).
3. Send the same IP through two patrol rounds with an escalating pattern
   (e.g. more failed logins the second time) and check CloudWatch logs
   for the `patrol_prompt_assembled` / `patrol_verdict` lines: the second
   round's prompt should include the first round's `agent_episodes` row,
   and `reasoning` should reference it (PRD-04's core acceptance
   criterion for Agentic Memory Design).
4. Confirm all three branches fire on the right input: a clean IP stays
   `normal` (no writes), a scan/probe pattern lands `low` (one
   `agent_episodes` row, no disposal write), and an obvious attack
   pattern lands `high` (disposal write + `alert_log` + `agent_episodes`).

## Manual verification against a live cluster + SNS (PRD-06 acceptance criteria)

Also needs `AlertTopic` deployed and its email subscription confirmed
(click the link SNS sends `AlertEmail` right after `sam deploy`):

1. Trigger a `high` verdict (e.g. via the attack simulator once PRD-08
   exists, or a manual `patrol_handler` invoke against seeded attack
   traffic) and confirm the subscribed mailbox receives an email with the
   subject and body `alerting.format_alert_message` produces.
2. Query `alert_log` for that row and confirm `sent = true` after the
   round completes.
3. Re-run the same patrol round (or a round that revisits the same
   `agent_episodes` history) and confirm no duplicate email arrives for
   the already-sent row -- each `high` verdict produces exactly one new
   `alert_log` row and one publish attempt, so there is nothing to
   re-send.
4. Point `SNS_TOPIC_ARN` at a topic the function's role can't publish to
   and confirm the round still completes (disposal write + `agent_episodes`
   still happen; only the email and `sent` flag are skipped), per the
   `_publish_alert` isolation in `patrol_loop.py`.
