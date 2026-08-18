# dashboard

Security Ops Dashboard (PRD-07): the most direct visual evidence of
"memory-driven decisions" in the whole project -- text describing the
Agentic Memory Design is less convincing than a judge watching the agent
actually reference its own history and escalate a verdict.

Two independently-deployable pieces:

- **`dashboard_api`** -- a read-only Lambda API, direct SQL against
  CockroachDB (not the MCP channel the patrol agent uses -- PRD-07
  explicitly scopes this as an independent read path so the dashboard
  never competes with the patrol agent's MCP quota). Three GET endpoints.
- **`frontend/index.html`** -- one self-contained static HTML file
  (inline CSS/JS, no build step, no framework) meant for S3 + CloudFront.
  Deliberately not a React/Vue app -- PRD-07's own non-goal is "不做复杂的
  图表库集成，清晰可读优先于美观".

## API

| Endpoint | Query params | Returns |
|---|---|---|
| `GET /logs` | `ip`, `status_code`, `limit` (default 100) | Recent `request_logs`, newest first |
| `GET /blacklist` | none | `{blacklist: [...], rate_limits: [...]}` -- currently-active `ip_blacklist`/`ip_rate_limit` rows |
| `GET /episodes` | `ip` (required), `limit` (default 50) | One IP's `agent_episodes` history, **oldest first** so the frontend can render it as a timeline without re-sorting |

Every response carries `Access-Control-Allow-Origin: *` -- the frontend is
static-hosted on a different origin (CloudFront) than the API (API
Gateway), so CORS has to be handled on every response, not just via an
OPTIONS preflight route.

## Frontend

Three tabs, matching PRD-07 functional requirements 1-3:

1. **Log Stream** -- recent `request_logs`, filterable by IP/status code,
   auto-refreshes every 5s (checkbox to disable) so a running attack
   simulator scenario shows up within seconds, per PRD-07's acceptance
   criterion.
2. **Blacklist & Rate Limits** -- side-by-side tables of what the
   demo-target-app gateway (PRD-05's `gated` middleware) is actually
   enforcing right now.
3. **Agent Memory Timeline** (the core view) -- enter an IP, see its
   `agent_episodes` laid out chronologically with a color-coded
   normal/low/high marker per round and the reasoning text for each. This
   is the one place the "recalls its own past verdict and escalates"
   story is directly visible, and is the recommended camera shot for
   PRD-10's demo video.

The frontend doesn't know its own API URL at build time (it's a static
file with no build step) -- paste the API Gateway URL from
`template.yaml`'s `DashboardApiUrl` output into the "API base URL" field
in the header and click Save; it's persisted to `localStorage` so it only
needs to be set once per browser.

## Layout

```
dashboard_api/
  interfaces.py     typing.Protocol Repository contract (matches patrol-agent/demo-target-app convention)
  config.py          DashboardReadConfig -- read-only CRDB credentials
  db.py               DashboardRepository -- the only place that talks to psycopg2
  http.py              API Gateway event/response helpers (CORS header, datetime-safe JSON)
  handlers/             one module per endpoint
  app.py                 Lambda entry points (one per SAM function)
frontend/
  index.html         self-contained static page -- inline CSS/JS, fetch() only
sql/
  dashboard_read_role.sql   Least-privilege SELECT-only role/grants
template.yaml         SAM: 3 read-only Lambdas + API Gateway + S3/CloudFront (OAC) for the frontend
tests/                Unit tests against fakes -- no live CRDB needed
```

## Local development

```bash
pip install -r requirements.txt
python -m pytest -q
```

Tests run against `tests/conftest.py`'s `FakeConnection`/`FakeRepository`,
so they don't need a live CockroachDB connection. `dashboard_api/db.py` is
the only module that imports `psycopg2`.

To preview the frontend locally against a deployed API, just open
`frontend/index.html` directly in a browser (or `python -m http.server`
from this directory) and paste the API base URL in.

## Setting up the read role

Requires PRD-00 (cluster reachable) and PRD-01 (target tables exist):

```bash
cockroach sql --url "$CRDB_ADMIN_URL" -f sql/dashboard_read_role.sql
cockroach sql --url "$CRDB_ADMIN_URL" \
  --execute "ALTER USER dashboard_reader WITH PASSWORD '<generated>';"
```

Store the generated password in Secrets Manager and wire it into
`CRDB_DASHBOARD_PASSWORD` at deploy time, same pattern as
`patrol-agent`'s write role and `demo-target-app`'s app credentials.

## Manual verification against a live cluster (PRD-07 acceptance criteria)

Needs a real CockroachDB Cloud cluster with data flowing in from PRD-04/05
and, ideally, `attack-simulator` (PRD-08) traffic to generate something to
look at:

1. Deploy `template.yaml`, upload `frontend/index.html` to the
   `FrontendBucket` output, open the `FrontendUrl` output, paste the
   `DashboardApiUrl` output into the header field.
2. Confirm all three views load real data.
3. Run `python -m attack_simulator.cli obfuscated_sqli --base-url <demo-app-url>`
   and confirm new rows appear in the Log Stream tab within a few seconds
   (auto-refresh).
4. Wait for a patrol round to complete and confirm the Blacklist tab picks
   up the new `ip_blacklist` row.
5. Enter that IP in the Agent Memory Timeline tab and confirm the episode
   history renders with the correct risk-level color coding.
