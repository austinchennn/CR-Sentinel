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

    def write_episode(self, *, ip, risk_level, attack_type, reasoning_summary, action_taken, embedding, idempotency_key):
        # ON CONFLICT (idempotency_key) DO NOTHING (PRD-09 functional
        # requirement 5): idempotency_key is derived from the actual
        # request_logs.id's judged this round (patrol_loop.py's
        # _compute_round_idempotency_key), so a Lambda retry that re-judges
        # the identical rows for this IP recognizes it as the same episode
        # rather than inserting a duplicate memory row.
        self._execute(
            """
            INSERT INTO agent_episodes
                (id, ip, risk_level, attack_type, reasoning_summary, action_taken, embedding, idempotency_key)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (idempotency_key) DO NOTHING
            """,
            (str(uuid.uuid4()), ip, risk_level, attack_type, reasoning_summary, action_taken, embedding, idempotency_key),
        )

    def write_task(self, task_type, payload, idempotency_key):
        self._execute(
            """
            INSERT INTO task_queue (id, type, payload, status, idempotency_key)
            VALUES (%s, %s, %s, 'pending', %s)
            ON CONFLICT (idempotency_key) DO NOTHING
            """,
            (str(uuid.uuid4()), task_type, payload, idempotency_key),
        )

    def write_alert(self, severity, message, idempotency_key):
        # Same ON CONFLICT DO NOTHING idempotency guard as write_episode.
        # One known residual gap, deliberately accepted rather than solved
        # with a more complex RETURNING-based upsert: on a duplicate key,
        # the returned `alert_id` refers to a row that was *not* inserted
        # (a different id already exists for that key), so a subsequent
        # mark_alert_sent(alert_id) silently no-ops instead of updating the
        # pre-existing row. That only matters if a retry follows a partial
        # failure that already ran write_alert but not mark_alert_sent --
        # a narrow window, and the row itself is never duplicated either
        # way, which is what PRD-09's acceptance criterion actually asks
        # for. See docs/06-production-readiness.md §4.
        alert_id = str(uuid.uuid4())
        self._execute(
            """
            INSERT INTO alert_log (id, severity, message, idempotency_key)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (idempotency_key) DO NOTHING
            """,
            (alert_id, severity, message, idempotency_key),
        )
        return alert_id

    def mark_alert_sent(self, alert_id):
        self._execute(
            "UPDATE alert_log SET sent = true WHERE id = %s",
            (alert_id,),
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
