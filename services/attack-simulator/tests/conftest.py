import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class FakeHttpClient:
    """Records every get()/post() call instead of hitting a real network,
    and always returns a canned 200 -- these tests are about what the
    simulator sends, not about a real demo-target-app deployment."""

    def __init__(self, status_code=200):
        self.calls = []
        self._status_code = status_code

    def get(self, path, params=None):
        self.calls.append(("GET", path, params))
        return _Response(self._status_code)

    def post(self, path, json_body=None):
        self.calls.append(("POST", path, json_body))
        return _Response(self._status_code)


class _Response:
    def __init__(self, status_code):
        self.status_code = status_code


@pytest.fixture
def fake_client():
    return FakeHttpClient()
