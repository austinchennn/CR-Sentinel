"""Covers the from_env() classmethods on every dataclass in
patrol_agent/config.py, none of which are exercised by
services/patrol-agent/tests/ (those tests always construct configs
directly with keyword args)."""
import pytest

from patrol_agent.config import BedrockConfig, CrdbWriteConfig, McpConfig, PatrolConfig


def test_mcp_config_from_env_uses_defaults(mcp_env):
    config = McpConfig.from_env()

    assert config.api_key == "test-mcp-key"
    assert config.url == "https://cockroachlabs.cloud/mcp"
    assert config.timeout_seconds == 10.0
    assert config.sql_arg_name == "sql"


def test_mcp_config_from_env_respects_overrides(mcp_env, monkeypatch):
    monkeypatch.setenv("MCP_URL", "https://example.com/mcp")
    monkeypatch.setenv("MCP_TIMEOUT_SECONDS", "5")
    monkeypatch.setenv("MCP_SQL_ARG_NAME", "query")

    config = McpConfig.from_env()

    assert config.url == "https://example.com/mcp"
    assert config.timeout_seconds == 5.0
    assert config.sql_arg_name == "query"


def test_mcp_config_from_env_requires_api_key(monkeypatch):
    monkeypatch.delenv("MCP_API_KEY", raising=False)

    with pytest.raises(KeyError):
        McpConfig.from_env()


def test_bedrock_config_from_env_defaults(bedrock_env):
    config = BedrockConfig.from_env()

    assert config.model_id == BedrockConfig.model_id


def test_bedrock_config_from_env_override(bedrock_env, monkeypatch):
    monkeypatch.setenv("BEDROCK_MODEL_ID", "anthropic.claude-3-opus")

    config = BedrockConfig.from_env()

    assert config.model_id == "anthropic.claude-3-opus"


def test_patrol_config_from_env_defaults(patrol_env):
    config = PatrolConfig.from_env()

    assert config.window_minutes == 5
    assert config.top_k == 5
    assert config.ip_history_limit == 20
    assert config.high_frequency_threshold == 20


def test_patrol_config_from_env_override(patrol_env, monkeypatch):
    monkeypatch.setenv("PATROL_WINDOW_MINUTES", "10")
    monkeypatch.setenv("PATROL_TOP_K", "3")
    monkeypatch.setenv("PATROL_IP_HISTORY_LIMIT", "50")
    monkeypatch.setenv("PATROL_HIGH_FREQUENCY_THRESHOLD", "30")

    config = PatrolConfig.from_env()

    assert config.window_minutes == 10
    assert config.top_k == 3
    assert config.ip_history_limit == 50
    assert config.high_frequency_threshold == 30


def test_crdb_write_config_from_env_uses_defaults(crdb_write_env):
    config = CrdbWriteConfig.from_env()

    assert config.host == "write.example.com"
    assert config.user == "patrol_write"
    assert config.password == "s3cret"
    assert config.port == "26257"
    assert config.database == "cr_sentinel"
    assert config.sslmode == "verify-full"


def test_crdb_write_config_from_env_requires_host(monkeypatch):
    monkeypatch.delenv("CRDB_WRITE_HOST", raising=False)
    monkeypatch.setenv("CRDB_WRITE_USER", "x")
    monkeypatch.setenv("CRDB_WRITE_PASSWORD", "x")

    with pytest.raises(KeyError):
        CrdbWriteConfig.from_env()
