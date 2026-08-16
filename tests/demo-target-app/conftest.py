"""Dedicated coverage-gap test suite for services/demo-target-app.

Kept in a separate top-level `tests/` tree (rather than inside
`services/demo-target-app/tests/`) so it's obvious at a glance which tests
were added to close out coverage gaps vs. the original PRD-02/PRD-05 test
suite. Run with `cd tests/demo-target-app && python3 -m pytest
--cov=demo_target_app --cov-report=term-missing` (needs the sys.path insert
below since demo_target_app isn't pip-installed).
"""
import json
import sys
from pathlib import Path

import pytest

SERVICE_ROOT = Path(__file__).resolve().parents[2] / "services" / "demo-target-app"
sys.path.insert(0, str(SERVICE_ROOT))


def _make_event(method="GET", path="/", query=None, body=None, source_ip="203.0.113.5", headers=None):
    event_headers = {"User-Agent": "pytest"}
    if headers is not None:
        event_headers = headers
    return {
        "httpMethod": method,
        "path": path,
        "queryStringParameters": query,
        "body": json.dumps(body) if body is not None else None,
        "headers": event_headers,
        "requestContext": {"identity": {"sourceIp": source_ip}},
    }


@pytest.fixture
def make_event():
    """Exposed as a fixture (not a plain module-level import) so test files
    never need `from conftest import make_event` -- with a second, same-
    named conftest.py in services/demo-target-app/tests/ also defining
    module-level helpers, a bare `import conftest` from a test file in one
    directory can resolve to whichever conftest.py Python's sys.modules
    cache happened to load first when both suites run in the same pytest
    session (e.g. `pytest services tests` from the repo root). Fixtures are
    resolved by pytest itself per-test-file, so they don't have this
    problem."""
    return _make_event


class FakeCursor:
    """Stand-in for a psycopg2 cursor: records every execute() call and
    replays queued fetchone() results in call order, matching how
    CockroachRepository actually uses its cursor (one query per `with`
    block, at most one fetchone per query)."""

    def __init__(self, log, fetchone_results):
        self._log = log
        self._fetchone_results = list(fetchone_results)

    def execute(self, statement, params=None):
        self._log.append((" ".join(statement.split()), params))

    def fetchone(self):
        if not self._fetchone_results:
            return None
        return self._fetchone_results.pop(0)

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


class FakeConnection:
    def __init__(self, fetchone_results=None):
        self.executed = []
        self.committed = 0
        self._fetchone_results = fetchone_results or []

    def cursor(self):
        return FakeCursor(self.executed, self._fetchone_results)

    def commit(self):
        self.committed += 1

    def queue_fetchone(self, row):
        self._fetchone_results.append(row)


@pytest.fixture
def fake_conn():
    return FakeConnection()


@pytest.fixture
def crdb_env(monkeypatch):
    monkeypatch.setenv("CRDB_HOST", "db.example.com")
    monkeypatch.setenv("CRDB_USER", "app")
    monkeypatch.setenv("CRDB_PASSWORD", "s3cret")
    monkeypatch.delenv("CRDB_PORT", raising=False)
    monkeypatch.delenv("CRDB_DATABASE", raising=False)
    monkeypatch.delenv("CRDB_SSLMODE", raising=False)
