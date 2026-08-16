"""Covers demo_target_app/http.py branches services/demo-target-app/tests/
never hits directly (it only exercises http.py indirectly through
handlers with well-formed events)."""
from demo_target_app import http


def test_json_response_shape():
    resp = http.json_response(404, {"error": "not found"})

    assert resp == {
        "statusCode": 404,
        "headers": {"Content-Type": "application/json"},
        "body": '{"error": "not found"}',
    }


def test_parse_json_body_returns_empty_dict_when_body_missing():
    assert http.parse_json_body({}) == {}


def test_parse_json_body_returns_empty_dict_when_body_is_none():
    assert http.parse_json_body({"body": None}) == {}


def test_parse_json_body_parses_valid_json():
    assert http.parse_json_body({"body": '{"a": 1}'}) == {"a": 1}


def test_parse_json_body_returns_empty_dict_on_malformed_json():
    assert http.parse_json_body({"body": "{not json"}) == {}


def test_query_params_returns_empty_dict_when_absent():
    assert http.query_params({}) == {}


def test_query_params_returns_empty_dict_when_none():
    assert http.query_params({"queryStringParameters": None}) == {}


def test_query_params_returns_the_dict_when_present():
    assert http.query_params({"queryStringParameters": {"id": "u-1001"}}) == {"id": "u-1001"}


def test_source_ip_prefers_request_context_identity():
    event = {"requestContext": {"identity": {"sourceIp": "203.0.113.5"}}}

    assert http.source_ip(event) == "203.0.113.5"


def test_source_ip_falls_back_to_x_forwarded_for_header_when_request_context_missing():
    event = {"headers": {"X-Forwarded-For": "198.51.100.9"}}

    assert http.source_ip(event) == "198.51.100.9"


def test_source_ip_falls_back_when_identity_key_missing():
    event = {"requestContext": {}, "headers": {"X-Forwarded-For": "198.51.100.9"}}

    assert http.source_ip(event) == "198.51.100.9"


def test_source_ip_returns_unknown_when_nothing_available():
    assert http.source_ip({}) == "unknown"


def test_source_ip_does_not_crash_when_headers_key_is_explicitly_none():
    """Regression test: `event.get("headers", {})` used to be called on an
    event where `headers` is present but `None` (a real shape API Gateway
    can send when a request has no custom headers), raising AttributeError
    instead of falling back to "unknown". See docs/03-open-issues.md."""
    event = {"headers": None}

    assert http.source_ip(event) == "unknown"


def test_user_agent_reads_title_case_header():
    assert http.user_agent({"headers": {"User-Agent": "curl/8.0"}}) == "curl/8.0"


def test_user_agent_reads_lower_case_header():
    assert http.user_agent({"headers": {"user-agent": "curl/8.0"}}) == "curl/8.0"


def test_user_agent_defaults_to_unknown_when_headers_missing():
    assert http.user_agent({}) == "unknown"


def test_user_agent_defaults_to_unknown_when_headers_none():
    assert http.user_agent({"headers": None}) == "unknown"
