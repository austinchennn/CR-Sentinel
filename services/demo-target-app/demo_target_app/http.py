"""Small helpers for working with API Gateway (REST API, proxy integration)
Lambda events, without pulling in a web framework."""
import json


def json_response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def parse_json_body(event):
    raw = event.get("body") or ""
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return {}


def query_params(event):
    return event.get("queryStringParameters") or {}


def source_ip(event):
    try:
        return event["requestContext"]["identity"]["sourceIp"]
    except (KeyError, TypeError):
        headers = event.get("headers") or {}
        return headers.get("X-Forwarded-For", "unknown")


def user_agent(event):
    headers = event.get("headers") or {}
    return headers.get("User-Agent") or headers.get("user-agent") or "unknown"
