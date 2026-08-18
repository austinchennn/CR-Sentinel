import json

from dashboard_api.handlers import blacklist, episodes, logs


def _event(query_params=None):
    return {"queryStringParameters": query_params}


def test_logs_handle_returns_recent_logs_with_no_filters(fake_repo):
    response = logs.handle(_event(), {}, fake_repo)

    assert response["statusCode"] == 200
    assert fake_repo.calls == [("recent_logs", {"limit": 100, "ip": None, "status_code": None})]


def test_logs_handle_applies_ip_and_status_code_filters(fake_repo):
    logs.handle(_event({"ip": "1.1.1.1", "status_code": "403", "limit": "5"}), {}, fake_repo)

    assert fake_repo.calls == [("recent_logs", {"limit": 5, "ip": "1.1.1.1", "status_code": 403})]


def test_logs_handle_rejects_non_integer_status_code(fake_repo):
    response = logs.handle(_event({"status_code": "not-a-number"}), {}, fake_repo)

    assert response["statusCode"] == 400
    assert fake_repo.calls == []


def test_blacklist_handle_returns_both_blacklist_and_rate_limits(fake_repo):
    fake_repo._blacklist = [{"ip": "2.2.2.2"}]
    fake_repo._rate_limits = [{"ip": "3.3.3.3"}]

    response = blacklist.handle(_event(), {}, fake_repo)

    body = json.loads(response["body"])
    assert body["blacklist"] == [{"ip": "2.2.2.2"}]
    assert body["rate_limits"] == [{"ip": "3.3.3.3"}]


def test_episodes_handle_requires_ip(fake_repo):
    response = episodes.handle(_event(), {}, fake_repo)

    assert response["statusCode"] == 400
    assert fake_repo.calls == []


def test_episodes_handle_returns_episodes_for_ip(fake_repo):
    fake_repo._episodes_by_ip = {"4.4.4.4": [{"risk_level": "high"}]}

    response = episodes.handle(_event({"ip": "4.4.4.4"}), {}, fake_repo)

    body = json.loads(response["body"])
    assert body["ip"] == "4.4.4.4"
    assert body["episodes"] == [{"risk_level": "high"}]


def test_all_responses_include_cors_header(fake_repo):
    response = blacklist.handle(_event(), {}, fake_repo)

    assert response["headers"]["Access-Control-Allow-Origin"] == "*"
