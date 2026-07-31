"""Independent least-privilege write channel (PRD-03 functional
requirement 5). Deliberately does not share a connection, credential, or
code path with `mcp_read_client.py` -- the whole point of splitting these
is that the write role (see `sql/patrol_write_role.sql`) can only
INSERT/UPDATE the six disposal tables, and a bug in the read path can
never escalate into a write.

Same `import psycopg2` inside `connect()` convention as
`demo_target_app/db.py`, so this module stays importable without the
driver installed -- tests use a fake connection/cursor instead.
"""
import logging
import uuid

from .errors import CrdbWriteError

logger = logging.getLogger(__name__)


class CrdbWriteClient:
    def __init__(self, conn):
        self._conn = conn

    @classmethod
    def connect(cls, config=None):
        import psycopg2

        if config is None:
            from .config import CrdbWriteConfig

            config = CrdbWriteConfig.from_env()

        conn = psycopg2.connect(
            host=config.host,
            port=config.port,
            dbname=config.database,
            user=config.user,
            password=config.password,
            sslmode=config.sslmode,
        )
        return cls(conn)

    def write_blacklist(self, ip, risk_level, block_until, attack_reason):
        self._execute(
            """
            INSERT INTO ip_blacklist (ip, risk_level, block_until, attack_reason)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (ip) DO UPDATE
                SET risk_level = excluded.risk_level,
                    block_until = excluded.block_until,
                    attack_reason = excluded.attack_reason
            """,
            (ip, risk_level, block_until, attack_reason),
        )

    def write_rate_limit(self, ip, limit_per_min, expires_at):
        self._execute(
            """
            INSERT INTO ip_rate_limit (ip, limit_per_min, expires_at)
            VALUES (%s, %s, %s)
            ON CONFLICT (ip) DO UPDATE
                SET limit_per_min = excluded.limit_per_min,
                    expires_at = excluded.expires_at
            """,
            (ip, limit_per_min, expires_at),
        )

    def lock_account(self, user_id, reason):
        self._execute(
            """
            UPDATE accounts
                SET locked = true, locked_reason = %s, force_logout_at = now()
                WHERE user_id = %s
            """,
            (reason, user_id),
        )

    def write_episode(self, *, ip, risk_level, attack_type, reasoning_summary, action_taken, embedding):
        self._execute(
            """
            INSERT INTO agent_episodes
                (id, ip, risk_level, attack_type, reasoning_summary, action_taken, embedding)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (str(uuid.uuid4()), ip, risk_level, attack_type, reasoning_summary, action_taken, embedding),
        )

    def write_task(self, task_type, payload):
        self._execute(
            "INSERT INTO task_queue (id, type, payload, status) VALUES (%s, %s, %s, 'pending')",
            (str(uuid.uuid4()), task_type, payload),
        )

    def write_alert(self, severity, message):
        self._execute(
            "INSERT INTO alert_log (id, severity, message) VALUES (%s, %s, %s)",
            (str(uuid.uuid4()), severity, message),
        )

    def _execute(self, statement, params):
        try:
            with self._conn.cursor() as cur:
                cur.execute(statement, params)
            self._conn.commit()
        except Exception as exc:
            self._conn.rollback()
            logger.warning("crdb_write_failed statement=%r", statement, exc_info=exc)
            raise CrdbWriteError(str(exc)) from exc
