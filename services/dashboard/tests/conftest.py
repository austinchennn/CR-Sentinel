import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class FakeCursor:
    def __init__(self, log, results):
        self._log = log
        self._results = results

    def execute(self, statement, params):
        self._log.append((statement.strip(), tuple(params) if params else params))

    def fetchall(self):
        return self._results

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


class FakeConnection:
    def __init__(self, results=None):
        self.executed = []
        self._results = results or []

    def cursor(self):
        return FakeCursor(self.executed, self._results)


@pytest.fixture
def fake_conn():
    return FakeConnection()


class FakeRepository:
    """In-memory stand-in for DashboardRepository, same method surface."""

    def __init__(self, logs=None, blacklist=None, rate_limits=None, episodes_by_ip=None):
        self._logs = logs if logs is not None else []
        self._blacklist = blacklist if blacklist is not None else []
        self._rate_limits = rate_limits if rate_limits is not None else []
        self._episodes_by_ip = episodes_by_ip or {}
        self.calls = []

    def recent_logs(self, *, limit=100, ip=None, status_code=None):
        self.calls.append(("recent_logs", dict(limit=limit, ip=ip, status_code=status_code)))
        return self._logs

    def active_blacklist(self):
        self.calls.append(("active_blacklist", {}))
        return self._blacklist

    def active_rate_limits(self):
        self.calls.append(("active_rate_limits", {}))
        return self._rate_limits

    def episodes_for_ip(self, ip, *, limit=50):
        self.calls.append(("episodes_for_ip", dict(ip=ip, limit=limit)))
        return self._episodes_by_ip.get(ip, [])


@pytest.fixture
def fake_repo():
    return FakeRepository()
