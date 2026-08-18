"""Lambda entry point for `PatrolAgentLambda`, triggered by the EventBridge
Scheduler rule in `template.yaml` (PRD-04 functional requirement 1).

Clients that hold a live connection (the write channel) or get built fresh
per cold start (everything else) are cached at module scope, same pattern
as `demo_target_app/app.py`'s `_get_repo`, so a warm Lambda container
reuses them across invocations instead of reconnecting every 2-5 minutes.
"""
import logging
from typing import Optional

from .alerting import SnsAlertPublisher
from .bedrock_judge import BedrockJudge
from .config import BedrockConfig, CrdbWriteConfig, McpConfig, PatrolConfig, SnsConfig
from .embeddings import embed_text
from .interfaces import AlertPublisher, WriteClient
from .mcp_read_client import McpReadOnlyClient
from .memory_gateway import PatrolMemoryGateway
from .metrics import CloudWatchMetrics
from .patrol_loop import run_patrol_round
from .write_client import CrdbWriteClient

logging.getLogger().setLevel(logging.INFO)
logger = logging.getLogger(__name__)

_write_client: Optional[WriteClient] = None
_alert_publisher: Optional[AlertPublisher] = None
_metrics = None


def _get_write_client() -> WriteClient:
    global _write_client
    if _write_client is None:
        _write_client = CrdbWriteClient.connect(CrdbWriteConfig.from_env())
    return _write_client


def _get_alert_publisher() -> AlertPublisher:
    global _alert_publisher
    if _alert_publisher is None:
        _alert_publisher = SnsAlertPublisher.connect(SnsConfig.from_env())
    return _alert_publisher


def _get_metrics() -> CloudWatchMetrics:
    global _metrics
    if _metrics is None:
        _metrics = CloudWatchMetrics.connect()
    return _metrics


def patrol_handler(event, context):
    patrol_config = PatrolConfig.from_env()
    read_client = McpReadOnlyClient(McpConfig.from_env())
    memory_gateway = PatrolMemoryGateway(read_client)
    judge = BedrockJudge(model_id=BedrockConfig.from_env().model_id)

    summary = run_patrol_round(
        memory_gateway=memory_gateway,
        read_client=read_client,
        write_client=_get_write_client(),
        judge=judge,
        embed_fn=embed_text,
        alert_publisher=_get_alert_publisher(),
        window_minutes=patrol_config.window_minutes,
        top_k=patrol_config.top_k,
        ip_history_limit=patrol_config.ip_history_limit,
        high_frequency_threshold=patrol_config.high_frequency_threshold,
    )

    logger.info(
        "patrol_round_complete degraded=%s logs_read=%d suspicious_ip_count=%d verdict_count=%d",
        summary.degraded, summary.logs_read, summary.suspicious_ip_count, len(summary.verdicts),
    )

    try:
        _get_metrics().publish_round_summary(summary)
    except Exception as exc:
        # A CloudWatch hiccup must never mask the round's actual result --
        # disposal/alert writes already happened by this point (PRD-09
        # functional requirement 3's metrics are observability, not part
        # of the safety-critical path).
        logger.warning("patrol_metrics_publish_failed", exc_info=exc)

    return {
        "degraded": summary.degraded,
        "logs_read": summary.logs_read,
        "suspicious_ip_count": summary.suspicious_ip_count,
        "verdict_count": len(summary.verdicts),
    }
