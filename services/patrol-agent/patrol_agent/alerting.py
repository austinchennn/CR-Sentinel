"""SNS email alerting for high-risk verdicts (PRD-06).

`format_alert_message` builds the human-readable body once so the same
text goes into both the `alert_log.message` column (queryable audit trail)
and the SNS email (human-facing) -- one source of truth for "what does a
security engineer need to know without re-querying the DB".

`SnsAlertPublisher` follows the same lazy-import-driver convention as
`write_client.CrdbWriteClient` and `embeddings.embed_text`: `boto3` is
imported inside `connect()`, not at module load time, so this module stays
importable in tests without the dependency installed.
"""
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def format_alert_message(verdict, action_type):
    """Returns (subject, body) for a high-risk verdict. Kept separate from
    `patrol_loop` so the format can be unit-tested without a live SNS
    client or write channel."""
    subject = f"[CR-Sentinel] High risk verdict: {verdict.ip} ({verdict.attack_type})"
    body = "\n".join(
        [
            f"IP: {verdict.ip}",
            f"Risk level: {verdict.risk_level}",
            f"Attack type: {verdict.attack_type}",
            f"Action taken: {action_type}",
            f"AI reasoning: {verdict.reasoning}",
            f"Timestamp: {datetime.now(timezone.utc).isoformat()}",
        ]
    )
    return subject, body


class SnsAlertPublisher:
    def __init__(self, client, topic_arn):
        self._client = client
        self._topic_arn = topic_arn

    @classmethod
    def connect(cls, config=None):
        import boto3

        if config is None:
            from .config import SnsConfig

            config = SnsConfig.from_env()
        return cls(boto3.client("sns"), config.topic_arn)

    def publish(self, subject, message):
        self._client.publish(TopicArn=self._topic_arn, Subject=subject, Message=message)
