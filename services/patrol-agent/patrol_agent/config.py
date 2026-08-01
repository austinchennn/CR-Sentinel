"""Env-var config for both channels, mirroring demo_target_app/db.py's
approach: values arrive as Lambda environment variables populated from
Secrets Manager at deploy time (see PRD-00), not fetched at runtime. The
two channels intentionally read disjoint env var prefixes so a config
mistake can't accidentally hand write credentials to the read path or
vice versa.
"""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class McpConfig:
    url: str
    api_key: str
    timeout_seconds: float
    # The CockroachDB Cloud Console config snippet is the source of truth
    # for the actual read-only tool's argument name -- see PRD-03
    # acceptance criterion 1 and services/patrol-agent/README.md. Default
    # matches the snippet as of the PRD-03 spike; override if Console
    # regenerates it differently.
    sql_arg_name: str = "sql"

    @classmethod
    def from_env(cls):
        return cls(
            url=os.environ.get("MCP_URL", "https://cockroachlabs.cloud/mcp"),
            api_key=os.environ["MCP_API_KEY"],
            timeout_seconds=float(os.environ.get("MCP_TIMEOUT_SECONDS", "10")),
            sql_arg_name=os.environ.get("MCP_SQL_ARG_NAME", "sql"),
        )


@dataclass(frozen=True)
class BedrockConfig:
    # Default matches whatever Claude model access was approved under
    # PRD-00's Day 1 Bedrock access request; override once the actual
    # approved model ID is known rather than assuming this one is granted.
    model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"

    @classmethod
    def from_env(cls):
        return cls(model_id=os.environ.get("BEDROCK_MODEL_ID", cls.model_id))


@dataclass(frozen=True)
class PatrolConfig:
    """Tunables for one patrol round (PRD-04). Kept separate from
    McpConfig/CrdbWriteConfig/BedrockConfig since these govern orchestration
    behavior, not a specific external channel's credentials."""

    window_minutes: int = 5
    top_k: int = 5
    ip_history_limit: int = 20
    high_frequency_threshold: int = 20

    @classmethod
    def from_env(cls):
        return cls(
            window_minutes=int(os.environ.get("PATROL_WINDOW_MINUTES", cls.window_minutes)),
            top_k=int(os.environ.get("PATROL_TOP_K", cls.top_k)),
            ip_history_limit=int(os.environ.get("PATROL_IP_HISTORY_LIMIT", cls.ip_history_limit)),
            high_frequency_threshold=int(
                os.environ.get("PATROL_HIGH_FREQUENCY_THRESHOLD", cls.high_frequency_threshold)
            ),
        )


@dataclass(frozen=True)
class CrdbWriteConfig:
    host: str
    port: str
    database: str
    user: str
    password: str
    sslmode: str

    @classmethod
    def from_env(cls):
        return cls(
            host=os.environ["CRDB_WRITE_HOST"],
            port=os.environ.get("CRDB_WRITE_PORT", "26257"),
            database=os.environ.get("CRDB_WRITE_DATABASE", "cr_sentinel"),
            user=os.environ["CRDB_WRITE_USER"],
            password=os.environ["CRDB_WRITE_PASSWORD"],
            sslmode=os.environ.get("CRDB_WRITE_SSLMODE", "verify-full"),
        )
