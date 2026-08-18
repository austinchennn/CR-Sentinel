"""Env-var config for the dashboard's read-only CRDB connection, same
lazy-driver-import convention as `demo_target_app/db.py` and
`patrol_agent/write_client.py`. Separate role/credentials from both the
patrol agent's write channel and its MCP read channel -- this API should
never be able to write anything (see sql/dashboard_read_role.sql).
"""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class DashboardReadConfig:
    host: str
    port: str
    database: str
    user: str
    password: str
    sslmode: str

    @classmethod
    def from_env(cls):
        return cls(
            host=os.environ["CRDB_DASHBOARD_HOST"],
            port=os.environ.get("CRDB_DASHBOARD_PORT", "26257"),
            database=os.environ.get("CRDB_DASHBOARD_DATABASE", "cr_sentinel"),
            user=os.environ["CRDB_DASHBOARD_USER"],
            password=os.environ["CRDB_DASHBOARD_PASSWORD"],
            sslmode=os.environ.get("CRDB_DASHBOARD_SSLMODE", "verify-full"),
        )
