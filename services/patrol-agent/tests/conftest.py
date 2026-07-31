import sys
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class FakeToolResult:
    """Stand-in for mcp.types.CallToolResult."""

    def __init__(self, rows=None, is_error=False, error_message=None, structured=None):
        self.isError = is_error
        self.structuredContent = structured
        if structured is not None:
            self.content = []
        elif is_error:
            self.content = [_TextBlock(error_message or "boom")]
        else:
            import json

            self.content = [_TextBlock(json.dumps(rows if rows is not None else []))]


class _TextBlock:
    def __init__(self, text):
        self.text = text


class FakeMcpSession:
    """Records every call_tool invocation and replays a queued result."""

    def __init__(self, results):
        self._results = list(results)
        self.calls = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if not self._results:
            raise AssertionError("FakeMcpSession ran out of queued results")
        result = self._results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def fake_session_factory(session):
    def factory(config):
        @asynccontextmanager
        async def cm():
            yield session

        return cm()

    return factory


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
