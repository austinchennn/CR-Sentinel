"""PRD-05 functional requirement 6: gateway interception in front of every
handler, reading ip_blacklist/ip_rate_limit before the real handler runs."""
from conftest import make_event

from demo_target_app.handlers import admin, login


def test_blacklisted_ip_rejected_with_403_without_reaching_handler(repo):
    repo.blacklisted_ips.add("198.51.100.9")
    event = make_event("GET", "/admin", source_ip="198.51.100.9")

    resp = admin.handle(event, {}, repo)

    assert resp["statusCode"] == 403


def test_non_blacklisted_ip_passes_through(repo):
    event = make_event("GET", "/admin", source_ip="203.0.113.5")

    resp = admin.handle(event, {}, repo)

    assert resp["statusCode"] == 200


def test_blocked_attempt_is_still_logged_for_the_patrol_agent(repo):
    repo.blacklisted_ips.add("198.51.100.9")
    event = make_event("GET", "/admin", source_ip="198.51.100.9")

    admin.handle(event, {}, repo)

    assert len(repo.request_logs) == 1
    assert repo.request_logs[0]["status_code"] == 403


def test_rate_limit_under_threshold_passes_through(repo):
    repo.rate_limits["203.0.113.5"] = 10
    repo.recent_request_counts["203.0.113.5"] = 5
    event = make_event("GET", "/admin", source_ip="203.0.113.5")

    resp = admin.handle(event, {}, repo)

    assert resp["statusCode"] == 200


def test_rate_limit_at_threshold_rejected_with_429(repo):
    repo.rate_limits["203.0.113.5"] = 10
    repo.recent_request_counts["203.0.113.5"] = 10
    event = make_event("GET", "/admin", source_ip="203.0.113.5")

    resp = admin.handle(event, {}, repo)

    assert resp["statusCode"] == 429


def test_no_rate_limit_row_means_unrestricted(repo):
    repo.recent_request_counts["203.0.113.5"] = 999
    event = make_event("GET", "/admin", source_ip="203.0.113.5")

    resp = admin.handle(event, {}, repo)

    assert resp["statusCode"] == 200


def test_blacklist_check_happens_before_account_lock_check(repo):
    repo.blacklisted_ips.add("198.51.100.9")
    event = make_event("POST", "/login", body={"username": "alice", "password": "alice123"}, source_ip="198.51.100.9")

    resp = login.handle(event, {}, repo)

    assert resp["statusCode"] == 403
    assert resp["body"].find("ip_blacklisted") != -1
