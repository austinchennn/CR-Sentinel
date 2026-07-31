import asyncio

import pytest

from patrol_agent.config import McpConfig
from patrol_agent.errors import McpUnavailableError
from patrol_agent.mcp_read_client import McpReadOnlyClient

from conftest import FakeMcpSession, FakeToolResult, fake_session_factory


def make_config(**overrides):
    defaults = dict(url="https://cockroachlabs.cloud/mcp", api_key="test-key", timeout_seconds=1.0)
    defaults.update(overrides)
    return McpConfig(**defaults)


def make_client(results):
    session = FakeMcpSession(results)
    client = McpReadOnlyClient(make_config(), session_factory=fake_session_factory(session))
    return client, session


def test_read_recent_logs_calls_select_query_tool():
    rows = [{"id": "1", "src_ip": "203.0.113.5", "path": "/login"}]
    client, session = make_client([FakeToolResult(rows=rows)])

    result = client.read_recent_logs(minutes=5)

    assert result == rows
    (tool_name, arguments), = session.calls
    assert tool_name == "select_query"
    query = arguments["sql"]
    assert "FROM request_logs" in query
    assert "INTERVAL '5 minutes'" in query


def test_semantic_search_embeds_vector_literal_and_orders_by_distance():
    rows = [{"id": "sig-1", "category": "sqli", "distance": 0.02}]
    client, session = make_client([FakeToolResult(rows=rows)])

    result = client.semantic_search_attack_signatures([0.1, 0.2, 0.3], top_k=3)

    assert result == rows
    (_, arguments), = session.calls
    query = arguments["sql"]
    assert "FROM attack_signatures" in query
    assert "ORDER BY embedding <->" in query
    assert "LIMIT 3" in query
    assert "0.1" in query and "0.2" in query and "0.3" in query


def test_read_ip_episodes_escapes_quotes_in_ip():
    client, session = make_client([FakeToolResult(rows=[])])

    client.read_ip_episodes("1' OR '1'='1", limit=10)

    (_, arguments), = session.calls
    query = arguments["sql"]
    assert "1'' OR ''1''=''1'" in query
    assert "FROM agent_episodes" in query


def test_custom_sql_arg_name_is_respected():
    rows = []
    session = FakeMcpSession([FakeToolResult(rows=rows)])
    config = make_config(sql_arg_name="query")
    client = McpReadOnlyClient(config, session_factory=fake_session_factory(session))

    client.read_recent_logs()

    (_, arguments), = session.calls
    assert "query" in arguments and "sql" not in arguments


def test_tool_error_raises_mcp_unavailable():
    client, _ = make_client([FakeToolResult(is_error=True, error_message="permission denied")])

    with pytest.raises(McpUnavailableError, match="permission denied"):
        client.read_recent_logs()


def test_session_factory_failure_is_wrapped():
    def broken_factory(config):
        raise ConnectionRefusedError("mcp endpoint unreachable")

    client = McpReadOnlyClient(make_config(), session_factory=broken_factory)

    with pytest.raises(McpUnavailableError):
        client.read_recent_logs()


def test_timeout_is_wrapped_as_mcp_unavailable():
    class SlowSession:
        async def call_tool(self, name, arguments):
            await asyncio.sleep(10)

    from contextlib import asynccontextmanager

    def slow_factory(config):
        @asynccontextmanager
        async def cm():
            yield SlowSession()

        return cm()

    config = make_config(timeout_seconds=0.05)
    client = McpReadOnlyClient(config, session_factory=slow_factory)

    with pytest.raises(McpUnavailableError):
        client.read_recent_logs()


def test_structured_content_is_preferred_over_text_block():
    session = FakeMcpSession(
        [FakeToolResult(structured={"rows": [{"id": "1"}]})]
    )
    client = McpReadOnlyClient(make_config(), session_factory=fake_session_factory(session))

    assert client.read_recent_logs() == [{"id": "1"}]
