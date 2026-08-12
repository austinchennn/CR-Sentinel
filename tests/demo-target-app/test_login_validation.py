"""Covers the missing-credentials 400 branch of login.handle(), which
services/demo-target-app/tests/test_login.py doesn't exercise."""
from demo_target_app.handlers import login


class _FakeRepo:
    def __init__(self):
        self.request_logs = []

    def log_request(self, **fields):
        self.request_logs.append(fields)

    def is_ip_blacklisted(self, ip):
        return False

    def get_active_rate_limit(self, ip):
        return None

    def count_recent_requests(self, ip, window_seconds=60):
        return 0

    def get_account_by_username(self, username):
        raise AssertionError("should not look up an account without credentials")


def test_missing_username_is_a_400(make_event):
    repo = _FakeRepo()
    event = make_event("POST", "/login", body={"password": "x"})

    resp = login.handle(event, {}, repo)

    assert resp["statusCode"] == 400


def test_missing_password_is_a_400(make_event):
    repo = _FakeRepo()
    event = make_event("POST", "/login", body={"username": "alice"})

    resp = login.handle(event, {}, repo)

    assert resp["statusCode"] == 400


def test_missing_body_is_a_400(make_event):
    repo = _FakeRepo()
    event = make_event("POST", "/login")

    resp = login.handle(event, {}, repo)

    assert resp["statusCode"] == 400
