import sys
from pathlib import Path

import pytest

# Tests import the service as a top-level `src` package without installing it.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class FakeRepository:
    """In-memory stand-in for CockroachRepository, same method surface."""

    def __init__(self, accounts=None):
        self.accounts = {a["user_id"]: dict(a) for a in (accounts or [])}
        self.request_logs = []
        self.blacklisted_ips = set()
        self.rate_limits = {}  # ip -> limit_per_min
        self.recent_request_counts = {}  # ip -> count, set directly by tests

    def log_request(self, **fields):
        self.request_logs.append(fields)

    def get_account_by_user_id(self, user_id):
        account = self.accounts.get(user_id)
        return dict(account) if account else None

    def get_account_by_username(self, username):
        for account in self.accounts.values():
            if account["username"] == username:
                return dict(account)
        return None

    def lock_account(self, user_id, reason):
        self.accounts[user_id]["locked"] = True
        self.accounts[user_id]["locked_reason"] = reason

    def upsert_account(self, user_id, username, locked=False, locked_reason=None):
        self.accounts[user_id] = {
            "user_id": user_id,
            "username": username,
            "locked": locked,
            "locked_reason": locked_reason,
        }

    def is_ip_blacklisted(self, ip):
        return ip in self.blacklisted_ips

    def get_active_rate_limit(self, ip):
        return self.rate_limits.get(ip)

    def count_recent_requests(self, ip, window_seconds=60):
        return self.recent_request_counts.get(ip, 0)


@pytest.fixture
def repo():
    from demo_target_app.seed_accounts import SEED_ACCOUNTS

    return FakeRepository(accounts=SEED_ACCOUNTS)


def make_event(method="GET", path="/", query=None, body=None, source_ip="203.0.113.5"):
    import json

    return {
        "httpMethod": method,
        "path": path,
        "queryStringParameters": query,
        "body": json.dumps(body) if body is not None else None,
        "headers": {"User-Agent": "pytest"},
        "requestContext": {"identity": {"sourceIp": source_ip}},
    }
