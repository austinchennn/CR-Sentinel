"""Thin HTTP client for hitting a deployed demo-target-app instance
(PRD-08). Built on `urllib.request` only -- this is a demo/CLI tool, not a
new microservice, so it doesn't pull in `requests`/`httpx` as a new
dependency (none of the other services in this repo use one either).

The real network call is behind an injectable `transport` function, same
pattern as `patrol_agent/mcp_read_client.py`'s `session_factory` -- tests
supply a fake transport instead of hitting a real HTTP endpoint.
"""
import json
import urllib.error
import urllib.parse
import urllib.request


class Response:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self.body = body


class HttpClient:
    def __init__(self, base_url, transport=None):
        self._base_url = base_url.rstrip("/")
        self._transport = transport or _urllib_transport

    def get(self, path, params=None):
        return self._transport("GET", self._build_url(path, params), None)

    def post(self, path, json_body=None):
        body = json.dumps(json_body or {}).encode()
        return self._transport("POST", self._build_url(path, None), body)

    def _build_url(self, path, params):
        url = f"{self._base_url}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        return url


def _urllib_transport(method, url, body):
    headers = {"Content-Type": "application/json"} if body is not None else {}
    request = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=10) as resp:
            return Response(resp.status, resp.read())
    except urllib.error.HTTPError as exc:
        return Response(exc.code, exc.read())
