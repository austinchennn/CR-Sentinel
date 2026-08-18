from attack_simulator.http_client import HttpClient, Response


class _FakeTransport:
    def __init__(self, status_code=200, body=b"{}"):
        self.calls = []
        self._status_code = status_code
        self._body = body

    def __call__(self, method, url, body):
        self.calls.append((method, url, body))
        return Response(self._status_code, self._body)


def test_get_builds_url_with_query_params():
    transport = _FakeTransport()
    client = HttpClient("https://example.com/Prod", transport=transport)

    client.get("/profile", params={"id": "u-1001"})

    method, url, body = transport.calls[0]
    assert method == "GET"
    assert url == "https://example.com/Prod/profile?id=u-1001"
    assert body is None


def test_get_without_params_has_no_query_string():
    transport = _FakeTransport()
    client = HttpClient("https://example.com/Prod", transport=transport)

    client.get("/admin")

    _, url, _ = transport.calls[0]
    assert url == "https://example.com/Prod/admin"


def test_post_sends_json_encoded_body():
    transport = _FakeTransport()
    client = HttpClient("https://example.com/Prod", transport=transport)

    client.post("/login", json_body={"username": "alice", "password": "hunter2"})

    method, url, body = transport.calls[0]
    assert method == "POST"
    assert url == "https://example.com/Prod/login"
    assert body == b'{"username": "alice", "password": "hunter2"}'


def test_base_url_trailing_slash_is_stripped():
    transport = _FakeTransport()
    client = HttpClient("https://example.com/Prod/", transport=transport)

    client.get("/admin")

    _, url, _ = transport.calls[0]
    assert url == "https://example.com/Prod/admin"


def test_response_carries_status_code_and_body():
    transport = _FakeTransport(status_code=403, body=b'{"error": "ip_blacklisted"}')
    client = HttpClient("https://example.com", transport=transport)

    resp = client.get("/admin")

    assert resp.status_code == 403
    assert resp.body == b'{"error": "ip_blacklisted"}'
