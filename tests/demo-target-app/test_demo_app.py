"""Covers demo_target_app/app.py's Lambda entry points and repo caching,
which services/demo-target-app/tests/ never imports (handlers there are
always called directly against a FakeRepository)."""
import demo_target_app.app as app_mod


class _FakeRepo:
    def __init__(self):
        self.request_logs = []
        self.accounts = {
            "u-1001": {"user_id": "u-1001", "username": "alice", "locked": False, "locked_reason": None},
        }
        self.blacklisted_ips = set()
        self.rate_limits = {}
        self.recent_request_counts = {}

    def log_request(self, **fields):
        self.request_logs.append(fields)

    def is_ip_blacklisted(self, ip):
        return False

    def get_active_rate_limit(self, ip):
        return None

    def count_recent_requests(self, ip, window_seconds=60):
        return 0

    def get_account_by_user_id(self, user_id):
        return self.accounts.get(user_id)

    def get_account_by_username(self, username):
        for account in self.accounts.values():
            if account["username"] == username:
                return account
        return None


def _reset_repo_cache(monkeypatch, fake_repo):
    monkeypatch.setattr(app_mod, "_repo", None)
    monkeypatch.setattr(app_mod, "_get_repo", lambda: fake_repo)


def test_get_repo_connects_once_and_caches(monkeypatch):
    fake_repo = _FakeRepo()
    connect_calls = []
    monkeypatch.setattr(app_mod, "_repo", None)
    monkeypatch.setattr(app_mod.CockroachRepository, "connect", classmethod(lambda cls: connect_calls.append(1) or fake_repo))

    first = app_mod._get_repo()
    second = app_mod._get_repo()

    assert first is fake_repo
    assert second is fake_repo
    assert len(connect_calls) == 1


def test_login_handler_dispatches_to_login_handle(monkeypatch, make_event):
    fake_repo = _FakeRepo()
    _reset_repo_cache(monkeypatch, fake_repo)

    resp = app_mod.login_handler(make_event("POST", "/login", body={"username": "", "password": ""}), {})

    assert resp["statusCode"] == 400


def test_profile_handler_dispatches_to_profile_handle(monkeypatch, make_event):
    fake_repo = _FakeRepo()
    _reset_repo_cache(monkeypatch, fake_repo)

    resp = app_mod.profile_handler(make_event("GET", "/profile", query={"id": "u-1001"}), {})

    assert resp["statusCode"] == 200


def test_comments_handler_dispatches_to_comments_handle(monkeypatch, make_event):
    fake_repo = _FakeRepo()
    _reset_repo_cache(monkeypatch, fake_repo)

    resp = app_mod.comments_handler(make_event("GET", "/comments"), {})

    assert resp["statusCode"] == 200


def test_admin_handler_dispatches_to_admin_handle(monkeypatch, make_event):
    fake_repo = _FakeRepo()
    _reset_repo_cache(monkeypatch, fake_repo)

    resp = app_mod.admin_handler(make_event("GET", "/admin"), {})

    assert resp["statusCode"] == 200
