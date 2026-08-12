"""Dedicated coverage-gap test suite for services/crdb-schema.

Kept in a separate top-level `tests/` tree (rather than inside
`services/crdb-schema/tests/`) so it's obvious at a glance which tests were
added to close out coverage gaps vs. the original PRD-01 test suite. Run
with `cd tests/crdb-schema && python3 -m pytest --cov=crdb_schema
--cov-report=term-missing` (needs the sys.path insert below since
crdb_schema isn't pip-installed).
"""
import sys
import types
from pathlib import Path

import pytest

SERVICE_ROOT = Path(__file__).resolve().parents[2] / "services" / "crdb-schema"
sys.path.insert(0, str(SERVICE_ROOT))


class FakeCursor:
    def __init__(self, log):
        self._log = log

    def execute(self, statement, params):
        self._log.append((statement.strip(), params))

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


class FakeConnection:
    def __init__(self):
        self.executed = []
        self.committed = 0

    def cursor(self):
        return FakeCursor(self.executed)

    def commit(self):
        self.committed += 1


@pytest.fixture
def fake_conn():
    return FakeConnection()


@pytest.fixture
def fake_boto3(monkeypatch):
    """Injects a fake `boto3` module into sys.modules so the lazy `import
    boto3` inside embed_text()/BedrockJudge.__init__ resolves without the
    real dependency installed, and records what `boto3.client(...)` was
    called with."""
    calls = []

    class _FakeBedrockClient:
        def __init__(self):
            self.invoke_model_calls = []

        def invoke_model(self, **kwargs):
            self.invoke_model_calls.append(kwargs)
            import json

            body = json.dumps({"embedding": [0.0] * 1024}).encode()

            class _Body:
                def read(self_inner):
                    return body

            return {"body": _Body()}

    fake_client = _FakeBedrockClient()

    fake_module = types.ModuleType("boto3")

    def client(service_name, *args, **kwargs):
        calls.append(service_name)
        return fake_client

    fake_module.client = client
    monkeypatch.setitem(sys.modules, "boto3", fake_module)
    return types.SimpleNamespace(calls=calls, client=fake_client)


@pytest.fixture
def crdb_admin_env(monkeypatch):
    monkeypatch.setenv("CRDB_ADMIN_HOST", "admin.example.com")
    monkeypatch.setenv("CRDB_ADMIN_USER", "admin")
    monkeypatch.setenv("CRDB_ADMIN_PASSWORD", "s3cret")
    monkeypatch.delenv("CRDB_ADMIN_PORT", raising=False)
    monkeypatch.delenv("CRDB_ADMIN_DATABASE", raising=False)
    monkeypatch.delenv("CRDB_ADMIN_SSLMODE", raising=False)
