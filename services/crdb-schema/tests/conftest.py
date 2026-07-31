import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class FakeCursor:
    def __init__(self, log):
        self._log = log

    def execute(self, statement, params):
        self._log.append((statement.strip(), params))

    def fetchall(self):
        return []

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
