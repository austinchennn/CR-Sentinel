from patrol_agent import prompt_builder


def test_verdict_tool_schema_requires_core_fields():
    schema = prompt_builder.VERDICT_TOOL["toolSpec"]["inputSchema"]["json"]

    assert schema["required"] == ["ip", "risk_level", "attack_type", "reasoning"]
    assert schema["properties"]["risk_level"]["enum"] == ["normal", "low", "high"]
    assert prompt_builder.VERDICT_TOOL["toolSpec"]["name"] == prompt_builder.VERDICT_TOOL_NAME


def test_build_messages_includes_log_rows():
    logs = [{"ts": "t1", "method": "POST", "path": "/login", "status_code": 401}]

    messages = prompt_builder.build_messages(ip="203.0.113.5", logs=logs, similar_attacks=[], ip_history=[])

    text = messages[0]["content"][0]["text"]
    assert "203.0.113.5" in text
    assert "/login" in text
    assert "status=401" in text


def test_build_messages_includes_recalled_signatures():
    similar = [{"category": "sqli", "severity": "high", "description": "union select", "distance": 0.1}]

    messages = prompt_builder.build_messages(ip="1.2.3.4", logs=[], similar_attacks=similar, ip_history=[])

    text = messages[0]["content"][0]["text"]
    assert "sqli" in text
    assert "union select" in text


def test_build_messages_notes_no_recalled_signatures():
    messages = prompt_builder.build_messages(ip="1.2.3.4", logs=[], similar_attacks=[], ip_history=[])

    assert "none recalled" in messages[0]["content"][0]["text"]


def test_build_messages_includes_ip_history():
    history = [{"ts": "t0", "risk_level": "low", "attack_type": "scan", "action_taken": "none", "reasoning_summary": "probed /admin"}]

    messages = prompt_builder.build_messages(ip="1.2.3.4", logs=[], similar_attacks=[], ip_history=history)

    text = messages[0]["content"][0]["text"]
    assert "probed /admin" in text


def test_build_messages_notes_first_sighting():
    messages = prompt_builder.build_messages(ip="1.2.3.4", logs=[], similar_attacks=[], ip_history=[])

    assert "first time" in messages[0]["content"][0]["text"]


def test_build_messages_returns_single_user_message():
    messages = prompt_builder.build_messages(ip="1.2.3.4", logs=[], similar_attacks=[], ip_history=[])

    assert len(messages) == 1
    assert messages[0]["role"] == "user"
