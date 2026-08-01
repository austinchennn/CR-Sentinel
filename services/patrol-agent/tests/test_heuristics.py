from patrol_agent import heuristics


def _row(ip="203.0.113.5", status_code=200, path="/comments", query_params="", body_snippet="", method="GET"):
    return {
        "src_ip": ip,
        "status_code": status_code,
        "path": path,
        "query_params": query_params,
        "body_snippet": body_snippet,
        "method": method,
    }


def test_flags_ip_with_suspicious_status_code():
    logs = [_row(status_code=403)]

    suspicious = heuristics.flag_suspicious_ips(logs)

    assert "203.0.113.5" in suspicious


def test_flags_ip_with_sqli_shaped_payload():
    logs = [_row(query_params="id=1' UNION SELECT username,password FROM accounts--")]

    suspicious = heuristics.flag_suspicious_ips(logs)

    assert "203.0.113.5" in suspicious


def test_flags_ip_with_xss_shaped_payload():
    logs = [_row(body_snippet="<script>document.location='http://evil'</script>")]

    suspicious = heuristics.flag_suspicious_ips(logs)

    assert "203.0.113.5" in suspicious


def test_flags_ip_exceeding_frequency_threshold():
    logs = [_row() for _ in range(25)]

    suspicious = heuristics.flag_suspicious_ips(logs, high_frequency_threshold=20)

    assert "203.0.113.5" in suspicious
    assert len(suspicious["203.0.113.5"]) == 25


def test_does_not_flag_ordinary_traffic():
    logs = [_row(path="/comments", method="GET"), _row(path="/profile", query_params="id=u-1001")]

    suspicious = heuristics.flag_suspicious_ips(logs, high_frequency_threshold=20)

    assert suspicious == {}


def test_ignores_rows_without_src_ip():
    logs = [{"status_code": 500, "path": "/admin"}]

    suspicious = heuristics.flag_suspicious_ips(logs)

    assert suspicious == {}


def test_summarize_for_embedding_joins_row_fields():
    rows = [_row(method="POST", path="/comments", body_snippet="hello")]

    text = heuristics.summarize_for_embedding(rows)

    assert "POST" in text
    assert "/comments" in text
    assert "hello" in text


def test_summarize_for_embedding_caps_row_count():
    rows = [_row(path=f"/p{i}") for i in range(20)]

    text = heuristics.summarize_for_embedding(rows, max_rows=3)

    assert text.count("|") == 2


def test_summarize_for_embedding_handles_empty_rows():
    assert heuristics.summarize_for_embedding([]) == "no request detail"
