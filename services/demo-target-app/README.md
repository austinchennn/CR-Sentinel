# demo-target-app

Intentionally vulnerable Lambda + API Gateway app used as the attack surface
for the CR-Sentinel demo (see `docs/prd/PRD-02-demo-target-app.md`).

## Endpoints

| Method | Path | Vulnerability |
|---|---|---|
| POST | `/login` | weak/guessable credentials, no rate limiting in-app |
| GET | `/profile?id=` | IDOR -- any `id` returns that user's account data |
| GET/POST | `/comments` | no content filtering (encoded XSS / phishing text) |
| GET | `/admin` | no auth in front of it |

Every request, regardless of outcome, is written to `request_logs`
(schema: `docs/prd/PRD-01-crdb-schema-memory.md`) so it becomes input to the
patrol agent's next pass.

Every handler is also gated (PRD-05): before it runs, the request's source
IP is checked directly against `ip_blacklist`/`ip_rate_limit` (no MCP, no
patrol-agent round-trip). A blacklisted IP gets an immediate 403; an IP over
its assigned `limit_per_min` gets a 429. This is the millisecond-latency
layer that covers the gap between attacks and the patrol agent's next
5-minute batch pass -- see `docs/01-architecture.md` section 2.5.

## Layout

```
demo_target_app/
  interfaces.py  typing.Protocol Repository contract every handler/middleware receives
  db.py          CockroachRepository -- the only place that talks to psycopg2
  http.py        API Gateway event helpers
  middleware.py  @logged (request_logs) and @gated (blacklist/rate-limit) decorators
  seed_accounts.py
  handlers/      one module per endpoint
  app.py         Lambda entry points (one per SAM function)
tests/           handler tests against an in-memory fake repository
```

Every handler and middleware decorator takes `repo` as a parameter rather
than importing `CockroachRepository` directly -- `interfaces.Repository`
(a `typing.Protocol`) documents that contract in one place. `app.py`'s
`_get_repo` composition root is the only place that constructs the
concrete `CockroachRepository`; tests inject `tests/conftest.py`'s
`FakeRepository` instead, which satisfies the same Protocol structurally
without inheriting from it.

## Local development

```bash
pip install -r requirements.txt
python -m pytest -q
```

Tests run against `tests/conftest.py`'s `FakeRepository`, so they don't
need a live CockroachDB connection. `demo_target_app/db.py` is the only
module that imports `psycopg2`, and it's only exercised when actually
deployed.

## Deploy

Requires PRD-00 (AWS account, IaC tooling) and PRD-01 (schema migrated)
to be done first.

```bash
sam build
sam deploy --guided \
  --parameter-overrides CrdbHost=<host> CrdbUser=<user> CrdbPassword=<password>
```

Then seed demo accounts:

```bash
CRDB_HOST=<host> CRDB_USER=<user> CRDB_PASSWORD=<password> \
  python -m demo_target_app.seed_accounts
```
