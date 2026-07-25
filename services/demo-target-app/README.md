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

## Layout

```
demo_target_app/
  db.py          CockroachRepository -- the only place that talks to psycopg2
  http.py        API Gateway event helpers
  middleware.py  @logged decorator, writes request_logs around every handler
  seed_accounts.py
  handlers/      one module per endpoint
  app.py         Lambda entry points (one per SAM function)
tests/           handler tests against an in-memory fake repository
```

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
