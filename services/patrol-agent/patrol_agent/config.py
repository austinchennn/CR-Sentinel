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
