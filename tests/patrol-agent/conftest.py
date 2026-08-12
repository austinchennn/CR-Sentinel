"""Dedicated coverage-gap test suite for services/patrol-agent.

Kept in a separate top-level `tests/` tree (rather than inside
`services/patrol-agent/tests/`) so it's obvious at a glance which tests
were added to close out coverage gaps vs. the original PRD-03/04 test
suite. Run with `cd tests/patrol-agent && python3 -m pytest
--cov=patrol_agent --cov-report=term-missing` (needs the sys.path insert
below since patrol_agent isn't pip-installed).
"""
import json
import sys
import types
from pathlib import Path

import pytest

SERVICE_ROOT = Path(__file__).resolve().parents[2] / "services" / "patrol-agent"
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
        self.rolled_back = 0
        self.fail_next = False

    def cursor(self):
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("simulated write failure")
        return FakeCursor(self.executed)

    def commit(self):
        self.committed += 1

    def rollback(self):
        self.rolled_back += 1


@pytest.fixture
def fake_conn():
    return FakeConnection()


@pytest.fixture
def mcp_env(monkeypatch):
    monkeypatch.setenv("MCP_API_KEY", "test-mcp-key")
    monkeypatch.delenv("MCP_URL", raising=False)
    monkeypatch.delenv("MCP_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("MCP_SQL_ARG_NAME", raising=False)


@pytest.fixture
def bedrock_env(monkeypatch):
    monkeypatch.delenv("BEDROCK_MODEL_ID", raising=False)


@pytest.fixture
def patrol_env(monkeypatch):
    for var in (
        "PATROL_WINDOW_MINUTES", "PATROL_TOP_K", "PATROL_IP_HISTORY_LIMIT",
        "PATROL_HIGH_FREQUENCY_THRESHOLD",
    ):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def crdb_write_env(monkeypatch):
    monkeypatch.setenv("CRDB_WRITE_HOST", "write.example.com")
    monkeypatch.setenv("CRDB_WRITE_USER", "patrol_write")
    monkeypatch.setenv("CRDB_WRITE_PASSWORD", "s3cret")
    monkeypatch.delenv("CRDB_WRITE_PORT", raising=False)
    monkeypatch.delenv("CRDB_WRITE_DATABASE", raising=False)
    monkeypatch.delenv("CRDB_WRITE_SSLMODE", raising=False)


@pytest.fixture
def fake_boto3(monkeypatch):
    """Injects a fake `boto3` module into sys.modules so the lazy `import
    boto3` inside BedrockJudge.__init__/embed_text resolves without the
    real dependency installed."""
    client_calls = []

    class _FakeBedrockClient:
        def __init__(self):
            self.converse_calls = []
            self.invoke_model_calls = []
            self.converse_response = None
            self.embedding = [0.0] * 1024

        def converse(self, **kwargs):
            self.converse_calls.append(kwargs)
            return self.converse_response

        def invoke_model(self, **kwargs):
            self.invoke_model_calls.append(kwargs)
            body = json.dumps({"embedding": self.embedding}).encode()

            class _Body:
                def read(self_inner):
                    return body

            return {"body": _Body()}

    fake_client = _FakeBedrockClient()
    fake_module = types.ModuleType("boto3")

    def client(service_name, *args, **kwargs):
        client_calls.append(service_name)
        return fake_client

    fake_module.client = client
    monkeypatch.setitem(sys.modules, "boto3", fake_module)
    return types.SimpleNamespace(calls=client_calls, client=fake_client)


@pytest.fixture
def fake_mcp_transport(monkeypatch):
    """Injects fake `mcp`/`mcp.client.streamable_http` modules into
    sys.modules so McpReadOnlyClient's default (production) session
    factory -- normally only reachable with the real `mcp` SDK installed --
    can be exercised end to end against a scripted tool-call result."""
    from contextlib import asynccontextmanager

    record = types.SimpleNamespace(
        stream_calls=[], session_calls=[], tool_calls=[], initialized=False,
        result=None,
    )

    class _FakeStreamCM:
        async def __aenter__(self):
            return ("read-stream", "write-stream", lambda: "session-id")

        async def __aexit__(self, *exc_info):
            return False

    def fake_streamablehttp_client(url, headers=None):
        record.stream_calls.append({"url": url, "headers": headers})
        return _FakeStreamCM()

    class FakeClientSession:
        def __init__(self, read, write):
            record.session_calls.append((read, write))
            self._read = read
            self._write = write

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            return False

        async def initialize(self):
            record.initialized = True

        async def call_tool(self, name, arguments):
            record.tool_calls.append((name, arguments))
            if isinstance(record.result, Exception):
                raise record.result
            return record.result

    mcp_module = types.ModuleType("mcp")
    mcp_module.ClientSession = FakeClientSession

    mcp_client_module = types.ModuleType("mcp.client")
    mcp_streamable_module = types.ModuleType("mcp.client.streamable_http")
    mcp_streamable_module.streamablehttp_client = fake_streamablehttp_client

    monkeypatch.setitem(sys.modules, "mcp", mcp_module)
    monkeypatch.setitem(sys.modules, "mcp.client", mcp_client_module)
    monkeypatch.setitem(sys.modules, "mcp.client.streamable_http", mcp_streamable_module)

    return record
