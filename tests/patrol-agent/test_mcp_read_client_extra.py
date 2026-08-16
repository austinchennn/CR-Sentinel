"""Covers mcp_read_client.py branches services/patrol-agent/tests/test_mcp_read_client.py
doesn't exercise: the real (non-test) `_default_session_factory` wiring to
the `mcp` SDK, the no-content error-text fallback, and the
_rows_from_tool_result branches for a bare dict payload and for a result
with no usable content at all."""
from contextlib import asynccontextmanager

import pytest

from patrol_agent.config import McpConfig
from patrol_agent.errors import McpUnavailableError
from patrol_agent.mcp_read_client import McpReadOnlyClient


def make_config(**overrides):
    defaults = dict(url="https://cockroachlabs.cloud/mcp", api_key="test-key", timeout_seconds=1.0)
    defaults.update(overrides)
    return McpConfig(**defaults)


class _TextBlock:
    def __init__(self, text):
        self.text = text


class _ToolResult:
    def __init__(self, *, is_error=False, content=None, structured=None):
        self.isError = is_error
        self.content = content
        self.structuredContent = structured


def test_default_session_factory_drives_the_real_mcp_wiring(fake_mcp_transport, mcp_env):
    """No session_factory override -- exercises _default_session_factory,
    the branch every other mcp_read_client test bypasses via a fake."""
    fake_mcp_transport.result = _ToolResult(content=[_TextBlock('{"rows": [{"id": "1"}]}')])
    config = McpConfig.from_env()
    client = McpReadOnlyClient(config)

    rows = client.read_recent_logs(minutes=5)

    assert rows == [{"id": "1"}]
    assert fake_mcp_transport.initialized is True
    (url_call,) = fake_mcp_transport.stream_calls
    assert url_call["url"] == config.url
    assert url_call["headers"] == {"Authorization": f"Bearer {config.api_key}"}
    (tool_name, arguments), = fake_mcp_transport.tool_calls
    assert tool_name == "select_query"
    assert "FROM request_logs" in arguments["sql"]


def test_default_session_factory_wraps_transport_errors(fake_mcp_transport, mcp_env):
    fake_mcp_transport.result = ConnectionRefusedError("mcp endpoint unreachable")
    config = McpConfig.from_env()
    client = McpReadOnlyClient(config)

    with pytest.raises(McpUnavailableError):
        client.read_recent_logs()


def make_client_with_result(result):
    def factory(config):
        @asynccontextmanager
        async def cm():
            class _Session:
                async def call_tool(self, name, arguments):
                    return result

            yield _Session()

        return cm()

    return McpReadOnlyClient(make_config(), session_factory=factory)


def test_error_text_falls_back_when_error_result_has_no_content():
    client = make_client_with_result(_ToolResult(is_error=True, content=[]))

    with pytest.raises(McpUnavailableError, match="no content"):
        client.read_recent_logs()


def test_rows_from_tool_result_wraps_a_bare_dict_payload_without_rows_key():
    client = make_client_with_result(_ToolResult(content=[_TextBlock('{"id": "sig-1", "category": "sqli"}')]))

    rows = client.semantic_search_attack_signatures([0.1, 0.2], top_k=1)

    assert rows == [{"id": "sig-1", "category": "sqli"}]


def test_rows_from_tool_result_returns_empty_list_when_no_usable_content():
    client = make_client_with_result(_ToolResult(content=[]))

    rows = client.read_ip_episodes("203.0.113.5", limit=5)

    assert rows == []
