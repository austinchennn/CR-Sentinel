"""Credentials for running migrations and seeding -- a human/CI principal
with DDL rights. Deliberately a separate env var prefix from both the MCP
read channel and PatrolAgentLambda's least-privilege write channel
(services/patrol-agent/patrol_agent/config.py, PRD-03): this admin
connection is never used at Lambda runtime.
"""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class CrdbAdminConfig:
    host: str
    port: str
    database: str
    user: str
    password: str
    sslmode: str

    @classmethod
    def from_env(cls):
        return cls(
            host=os.environ["CRDB_ADMIN_HOST"],
            port=os.environ.get("CRDB_ADMIN_PORT", "26257"),
            database=os.environ.get("CRDB_ADMIN_DATABASE", "cr_sentinel"),
            user=os.environ["CRDB_ADMIN_USER"],
            password=os.environ["CRDB_ADMIN_PASSWORD"],
            sslmode=os.environ.get("CRDB_ADMIN_SSLMODE", "verify-full"),
        )
