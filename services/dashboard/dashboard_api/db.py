"""Read-only CockroachDB access for the dashboard API (PRD-07 functional
requirement 4). Direct SQL, not the MCP channel patrol-agent uses -- PRD-07
explicitly scopes this as an independent read path so the dashboard
doesn't compete with the patrol agent's MCP quota, same reasoning as
PRD-05's gateway-interception queries in `demo_target_app/db.py`.

Handlers never talk to psycopg2 directly -- they receive a `Repository`
(interfaces.py) and call its methods, so they're testable against a fake
without a live cluster (see tests/conftest.py).
"""


class DashboardRepository:
    def __init__(self, conn):
        self._conn = conn

    @classmethod
    def connect(cls, config=None):
        import psycopg2

        if config is None:
            from .config import DashboardReadConfig

            config = DashboardReadConfig.from_env()

        conn = psycopg2.connect(
            host=config.host,
            port=config.port,
            dbname=config.database,
            user=config.user,
            password=config.password,
            sslmode=config.sslmode,
        )
        return cls(conn)

    def recent_logs(self, *, limit=100, ip=None, status_code=None):
        clauses = []
        params = []
        if ip:
            clauses.append("src_ip = %s")
            params.append(ip)
        if status_code is not None:
            clauses.append("status_code = %s")
            params.append(status_code)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)

        with self._conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, ts, src_ip, method, path, query_params, body_snippet,
                       user_agent, status_code, user_id, response_time_ms
                FROM request_logs
                {where}
                ORDER BY ts DESC
                LIMIT %s
                """,
                params,
            )
            rows = cur.fetchall()
        return [_row_to_log(row) for row in rows]

    def active_blacklist(self):
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT ip, risk_level, block_until, attack_reason
                FROM ip_blacklist
                WHERE block_until IS NULL OR block_until > now()
                ORDER BY block_until NULLS FIRST
                """,
                None,
            )
            rows = cur.fetchall()
        return [_row_to_blacklist_entry(row) for row in rows]

    def active_rate_limits(self):
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT ip, limit_per_min, expires_at
                FROM ip_rate_limit
                WHERE expires_at > now()
                ORDER BY expires_at
                """,
                None,
            )
            rows = cur.fetchall()
        return [_row_to_rate_limit_entry(row) for row in rows]

    def episodes_for_ip(self, ip, *, limit=50):
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT ts, risk_level, attack_type, reasoning_summary, action_taken
                FROM agent_episodes
                WHERE ip = %s
                ORDER BY ts ASC
                LIMIT %s
                """,
                (ip, limit),
            )
            rows = cur.fetchall()
        return [_row_to_episode(row) for row in rows]


def _row_to_log(row):
    return {
        "id": row[0], "ts": row[1], "src_ip": row[2], "method": row[3], "path": row[4],
        "query_params": row[5], "body_snippet": row[6], "user_agent": row[7],
        "status_code": row[8], "user_id": row[9], "response_time_ms": row[10],
    }


def _row_to_blacklist_entry(row):
    return {"ip": row[0], "risk_level": row[1], "block_until": row[2], "attack_reason": row[3]}


def _row_to_rate_limit_entry(row):
    return {"ip": row[0], "limit_per_min": row[1], "expires_at": row[2]}


def _row_to_episode(row):
    return {"ts": row[0], "risk_level": row[1], "attack_type": row[2], "reasoning_summary": row[3], "action_taken": row[4]}
