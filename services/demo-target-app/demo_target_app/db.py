"""CockroachDB access layer for the demo target app.

Tables (`request_logs`, `accounts`) are defined in PRD-01. This module only
depends on their column names, not on how the migration got them there.

Handlers never talk to psycopg2 directly -- they receive a `Repository` and
call its methods. That keeps handler logic testable without a live cluster
(see tests/conftest.py for the in-memory fake used in unit tests) and keeps
the production connection details (Secrets Manager-injected env vars) in one
place.
"""
import os
import time
import uuid


class CockroachRepository:
    """Repository backed by a real CockroachDB connection (psycopg2)."""

    def __init__(self, conn):
        self._conn = conn

    @classmethod
    def connect(cls):
        import psycopg2

        conn = psycopg2.connect(
            host=os.environ["CRDB_HOST"],
            port=os.environ.get("CRDB_PORT", "26257"),
            dbname=os.environ.get("CRDB_DATABASE", "cr_sentinel"),
            user=os.environ["CRDB_USER"],
            password=os.environ["CRDB_PASSWORD"],
            sslmode=os.environ.get("CRDB_SSLMODE", "verify-full"),
        )
        return cls(conn)

    def log_request(self, *, src_ip, method, path, query_params="", body_snippet="",
                     user_agent="", status_code=200, user_id=None, response_time_ms=0):
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO request_logs
                    (id, ts, src_ip, method, path, query_params, body_snippet,
                     user_agent, status_code, user_id, response_time_ms)
                VALUES (%s, now(), %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    str(uuid.uuid4()), src_ip, method, path, query_params,
                    body_snippet, user_agent, status_code, user_id, response_time_ms,
                ),
            )
        self._conn.commit()

    def get_account_by_user_id(self, user_id):
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT user_id, username, locked, locked_reason FROM accounts WHERE user_id = %s",
                (user_id,),
            )
            row = cur.fetchone()
        return _row_to_account(row)

    def get_account_by_username(self, username):
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT user_id, username, locked, locked_reason FROM accounts WHERE username = %s",
                (username,),
            )
            row = cur.fetchone()
        return _row_to_account(row)

    def lock_account(self, user_id, reason):
        with self._conn.cursor() as cur:
            cur.execute(
                "UPDATE accounts SET locked = true, locked_reason = %s, force_logout_at = now() WHERE user_id = %s",
                (reason, user_id),
            )
        self._conn.commit()

    def upsert_account(self, user_id, username, locked=False, locked_reason=None):
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO accounts (user_id, username, locked, locked_reason)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE
                    SET username = excluded.username,
                        locked = excluded.locked,
                        locked_reason = excluded.locked_reason
                """,
                (user_id, username, locked, locked_reason),
            )
        self._conn.commit()

    def is_ip_blacklisted(self, ip):
        """PRD-05 functional requirement 6: block_until IS NULL is the
        permanent-block convention the patrol agent writes (see
        patrol_agent/patrol_loop.py's `_execute_disposal_action`)."""
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM ip_blacklist WHERE ip = %s AND (block_until IS NULL OR block_until > now())",
                (ip,),
            )
            return cur.fetchone() is not None

    def get_active_rate_limit(self, ip):
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT limit_per_min FROM ip_rate_limit WHERE ip = %s AND expires_at > now()",
                (ip,),
            )
            row = cur.fetchone()
        return row[0] if row else None

    def count_recent_requests(self, ip, window_seconds=60):
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT count(*) FROM request_logs
                WHERE src_ip = %s AND ts > now() - (%s * INTERVAL '1 second')
                """,
                (ip, window_seconds),
            )
            row = cur.fetchone()
        return row[0] if row else 0


def _row_to_account(row):
    if row is None:
        return None
    return {
        "user_id": row[0],
        "username": row[1],
        "locked": bool(row[2]),
        "locked_reason": row[3],
    }


def now_ms():
    return int(time.time() * 1000)
