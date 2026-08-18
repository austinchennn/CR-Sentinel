"""Covers patrol_agent/app.py's Lambda entry point and write-client
caching, which services/patrol-agent/tests/ never imports (patrol_loop is
always tested directly with fully faked collaborators, bypassing app.py's
env-var wiring entirely)."""
import types

import patrol_agent.app as app_mod


class _TextBlock:
    def __init__(self, text):
        self.text = text


class _ToolResult:
    def __init__(self, *, is_error=False, content=None):
        self.isError = is_error
        self.content = content or []
        self.structuredContent = None


def _patch_write_client_connect(monkeypatch, fake_client):
    calls = []
    monkeypatch.setattr(app_mod, "_write_client", None)
    monkeypatch.setattr(app_mod, "_alert_publisher", None)
    monkeypatch.setattr(app_mod, "_metrics", None)
    monkeypatch.setattr(
        app_mod.CrdbWriteClient, "connect", classmethod(lambda cls, config=None: calls.append(config) or fake_client)
    )
    return calls


def test_get_write_client_connects_once_and_caches(monkeypatch, crdb_write_env):
    calls = _patch_write_client_connect(monkeypatch, fake_client=object())

    first = app_mod._get_write_client()
    second = app_mod._get_write_client()

    assert first is second
    assert len(calls) == 1


def test_patrol_handler_wires_env_config_into_a_full_round(
    monkeypatch, mcp_env, bedrock_env, patrol_env, crdb_write_env, sns_env, fake_boto3, fake_mcp_transport,
):
    fake_mcp_transport.result = _ToolResult(content=[_TextBlock('{"rows": []}')])
    _patch_write_client_connect(monkeypatch, fake_client=types.SimpleNamespace())

    result = app_mod.patrol_handler({}, {})

    assert result == {"degraded": False, "logs_read": 0, "suspicious_ip_count": 0, "verdict_count": 0}
    (tool_name, arguments), = fake_mcp_transport.tool_calls
    assert tool_name == "select_query"
    assert "FROM request_logs" in arguments["sql"]


def test_patrol_handler_reports_degraded_when_mcp_is_down(
    monkeypatch, mcp_env, bedrock_env, patrol_env, crdb_write_env, sns_env, fake_boto3, fake_mcp_transport,
):
    fake_mcp_transport.result = ConnectionRefusedError("mcp endpoint unreachable")
    _patch_write_client_connect(monkeypatch, fake_client=types.SimpleNamespace())

    result = app_mod.patrol_handler({}, {})

    assert result["degraded"] is True
    assert result["logs_read"] == 0
    assert result["verdict_count"] == 0
