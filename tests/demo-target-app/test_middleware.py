"""Covers the exception path of middleware.logged(), which
services/demo-target-app/tests/test_gateway.py doesn't exercise (every
handler used there returns normally)."""
import pytest

from demo_target_app.middleware import gated, logged


class _FakeRepo:
    def __init__(self):
        self.request_logs = []
        self.blacklisted_ips = set()
        self.rate_limits = {}
        self.recent_request_counts = {}

    def log_request(self, **fields):
        self.request_logs.append(fields)

    def is_ip_blacklisted(self, ip):
        return ip in self.blacklisted_ips

    def get_active_rate_limit(self, ip):
        return self.rate_limits.get(ip)

    def count_recent_requests(self, ip, window_seconds=60):
        return self.recent_request_counts.get(ip, 0)


def test_logged_records_a_500_row_and_reraises_when_handler_raises(make_event):
    repo = _FakeRepo()

    @logged
    def handler(event, context, repo):
        raise ValueError("boom")

    event = make_event("GET", "/admin")

    with pytest.raises(ValueError, match="boom"):
        handler(event, {}, repo)

    assert len(repo.request_logs) == 1
    assert repo.request_logs[0]["status_code"] == 500


def test_logged_records_success_status_code_and_returns_response(make_event):
    repo = _FakeRepo()

    @logged
    def handler(event, context, repo):
        return {"statusCode": 201, "body": "{}"}

    resp = handler(make_event("POST", "/comments"), {}, repo)

    assert resp["statusCode"] == 201
    assert repo.request_logs[0]["status_code"] == 201


def test_gated_calls_through_to_handler_when_not_blocked(make_event):
    repo = _FakeRepo()
    calls = []

    @gated
    def handler(event, context, repo):
        calls.append(1)
        return {"statusCode": 200}

    handler(make_event("GET", "/admin"), {}, repo)

    assert calls == [1]
