"""Single patrol round orchestration (PRD-04 functional requirement 2-4):
read logs -> pre-filter suspicious IPs -> per IP, recall memory and ask
Bedrock for a verdict -> branch on risk_level.

`gather_signals`'s log read happens once per round (not once per IP) --
per-IP reads only cover the two things that are actually IP-scoped:
semantic recall of that IP's suspicious text, and that IP's own
`agent_episodes` history. Re-running `read_recent_logs` per IP would just
repeat the same window query N times for no benefit.

Every per-IP step (embedding, MCP reads, Bedrock) is wrapped so one IP's
failure is logged and skipped rather than aborting the rest of the round --
see PRD-09's "MCP/Bedrock/CRDB 写入任一环节失败时...宁可整轮跳过该项，不要写入
不完整的处置记录", applied here at IP granularity so an EventBridge cycle
with 30 suspicious IPs doesn't lose all 30 verdicts because IP #1's Bedrock
call timed out.
"""
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from . import alerting, heuristics, prompt_builder
from .errors import BedrockJudgeError, CrdbWriteError, McpUnavailableError

logger = logging.getLogger(__name__)

DEFAULT_BLOCK_HOURS = 24
DEFAULT_RATE_LIMIT_PER_MIN = 10
DEFAULT_RATE_LIMIT_HOURS = 1


@dataclass
class RoundSummary:
    logs_read: int = 0
    suspicious_ip_count: int = 0
    verdicts: list = field(default_factory=list)
    degraded: bool = False
    degraded_reason: str = None


def run_patrol_round(
    *,
    memory_gateway,
    read_client,
    write_client,
    judge,
    embed_fn,
    alert_publisher=None,
    window_minutes=5,
    top_k=5,
    ip_history_limit=20,
    high_frequency_threshold=heuristics.HIGH_FREQUENCY_THRESHOLD,
):
    signals = memory_gateway.gather_signals(minutes=window_minutes)
    if signals.degraded:
        logger.warning("patrol_round_skipped reason=%r", signals.degraded_reason)
        return RoundSummary(degraded=True, degraded_reason=signals.degraded_reason)

    logger.info("patrol_round_logs_read count=%d window_minutes=%d", len(signals.logs), window_minutes)
    if not signals.logs:
        return RoundSummary(logs_read=0)

    suspicious = heuristics.flag_suspicious_ips(signals.logs, high_frequency_threshold=high_frequency_threshold)
    logger.info("patrol_round_suspicious_ips count=%d ips=%s", len(suspicious), sorted(suspicious))

    verdicts = []
    for ip, ip_logs in suspicious.items():
        verdict = _judge_one_ip(
            ip=ip,
            ip_logs=ip_logs,
            read_client=read_client,
            judge=judge,
            embed_fn=embed_fn,
            top_k=top_k,
            ip_history_limit=ip_history_limit,
        )
        if verdict is None:
            continue

        logger.info(
            "patrol_verdict ip=%s risk_level=%s attack_type=%s action=%r",
            verdict.ip, verdict.risk_level, verdict.attack_type, verdict.action,
        )
        _dispatch_verdict(verdict, write_client=write_client, embed_fn=embed_fn, alert_publisher=alert_publisher)
        verdicts.append(verdict)

    return RoundSummary(logs_read=len(signals.logs), suspicious_ip_count=len(suspicious), verdicts=verdicts)


def _judge_one_ip(*, ip, ip_logs, read_client, judge, embed_fn, top_k, ip_history_limit):
    try:
        query_text = heuristics.summarize_for_embedding(ip_logs)
        embedding = embed_fn(query_text)
        similar_attacks = read_client.semantic_search_attack_signatures(embedding, top_k=top_k)
        ip_history = read_client.read_ip_episodes(ip, limit=ip_history_limit)
    except McpUnavailableError as exc:
        logger.warning("patrol_ip_skipped ip=%s reason=%r", ip, str(exc))
        return None
    except Exception as exc:
        logger.warning("patrol_ip_signal_gathering_failed ip=%s", ip, exc_info=exc)
        return None

    messages = prompt_builder.build_messages(ip=ip, logs=ip_logs, similar_attacks=similar_attacks, ip_history=ip_history)
    logger.info(
        "patrol_prompt_assembled ip=%s log_count=%d similar_count=%d history_count=%d",
        ip, len(ip_logs), len(similar_attacks), len(ip_history),
    )

    try:
        return judge.judge(messages)
    except BedrockJudgeError as exc:
        logger.warning("patrol_bedrock_failed ip=%s", ip, exc_info=exc)
        return None


def _dispatch_verdict(verdict, *, write_client, embed_fn, alert_publisher=None):
    if verdict.risk_level == "normal":
        return

    try:
        episode_embedding = embed_fn(verdict.reasoning or verdict.attack_type or verdict.ip)
    except Exception as exc:
        logger.warning("patrol_episode_embedding_failed ip=%s", verdict.ip, exc_info=exc)
        return

    action = verdict.action or {}
    action_type = action.get("type", "none")

    try:
        if verdict.risk_level == "high":
            _execute_disposal_action(verdict, action, action_type, write_client=write_client)
            subject, body = alerting.format_alert_message(verdict, action_type)
            alert_id = write_client.write_alert(severity="high", message=body)
            _publish_alert(alert_publisher, write_client, alert_id=alert_id, ip=verdict.ip, subject=subject, body=body)
        write_client.write_episode(
            ip=verdict.ip,
            risk_level=verdict.risk_level,
            attack_type=verdict.attack_type,
            reasoning_summary=verdict.reasoning,
            action_taken=action_type if verdict.risk_level == "high" else "none",
            embedding=episode_embedding,
        )
    except CrdbWriteError as exc:
        logger.warning("patrol_write_failed ip=%s risk_level=%s", verdict.ip, verdict.risk_level, exc_info=exc)


def _publish_alert(alert_publisher, write_client, *, alert_id, ip, subject, body):
    """SNS publish + marking `alert_log.sent` is deliberately its own
    try/except, separate from the outer CrdbWriteError handling in
    `_dispatch_verdict` -- a flaky SNS call or a failed `sent` update should
    never skip the `agent_episodes` write that comes right after this call.
    The `alert_log` row from `write_alert` already exists either way; this
    only controls whether it also gets emailed and marked sent."""
    if alert_publisher is None:
        return
    try:
        alert_publisher.publish(subject, body)
        write_client.mark_alert_sent(alert_id)
    except Exception as exc:
        logger.warning("patrol_alert_publish_failed ip=%s alert_id=%s", ip, alert_id, exc_info=exc)


def _execute_disposal_action(verdict, action, action_type, *, write_client):
    now = datetime.now(timezone.utc)

    if action_type == "blacklist_temporary":
        block_hours = action.get("block_hours") or DEFAULT_BLOCK_HOURS
        write_client.write_blacklist(
            ip=verdict.ip,
            risk_level=verdict.risk_level,
            block_until=now + timedelta(hours=block_hours),
            attack_reason=verdict.reasoning,
        )
    elif action_type == "blacklist_permanent":
        # block_until = NULL is the "no expiry" convention PRD-05's gateway
        # lookup is expected to honor (block_until IS NULL OR > now()).
        write_client.write_blacklist(
            ip=verdict.ip, risk_level=verdict.risk_level, block_until=None, attack_reason=verdict.reasoning
        )
    elif action_type == "rate_limit":
        limit_per_min = action.get("limit_per_min") or DEFAULT_RATE_LIMIT_PER_MIN
        write_client.write_rate_limit(
            ip=verdict.ip, limit_per_min=limit_per_min, expires_at=now + timedelta(hours=DEFAULT_RATE_LIMIT_HOURS)
        )
    elif action_type == "lock_account":
        user_id = action.get("user_id")
        if user_id:
            write_client.lock_account(user_id, verdict.reasoning)
        else:
            logger.warning("patrol_lock_account_missing_user_id ip=%s", verdict.ip)
    elif action_type == "task_queue":
        write_client.write_task(
            "hardening_suggestion",
            json.dumps({"ip": verdict.ip, "attack_type": verdict.attack_type, "note": action.get("task_note", verdict.reasoning)}),
        )
    else:
        logger.warning("patrol_high_risk_no_action ip=%s action=%r", verdict.ip, action)
