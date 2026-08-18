"""Single patrol round orchestration (PRD-04 functional requirement 2-4):
read logs -> pre-filter suspicious IPs -> per IP, recall memory and ask
Bedrock for a verdict -> branch on risk_level.

`gather_signals`'s log read happens once per round (not once per IP) --
per-IP reads only cover the two things that are actually IP-scoped:
semantic recall of that IP's suspicious text, and that IP's own
`agent_episodes` history. Re-running `read_recent_logs` per IP would just
repeat the same window query N times for no benefit.

Every per-IP signal-gathering step (embedding, MCP reads, Bedrock) is
wrapped so one IP's failure is logged and skipped rather than aborting the
rest of the round -- see PRD-09's "MCP/Bedrock/CRDB 写入任一环节失败时...宁可
整轮跳过该项，不要写入不完整的处置记录", applied here at IP granularity so an
EventBridge cycle with 30 suspicious IPs doesn't lose all 30 verdicts
because IP #1's Bedrock call timed out.

Once a verdict exists, `_dispatch_verdict` deliberately does NOT apply that
same all-or-nothing rule across disposal/alert vs. episode-memory writes --
see its docstring: those are two independent failure domains, because a
confirmed `high` verdict's actual block/alert must not be cancelled by an
unrelated embedding hiccup.

`_compute_round_idempotency_key` (PRD-09 functional requirement 5) gives
each IP's verdict this round a key stable across a Lambda retry of the
*same* invocation -- derived from the actual `request_logs.id`s judged,
not wall-clock time, since those rows are immutable once written. A retry
that re-reads the identical underlying rows for an IP produces the same
key, so `write_episode`/`write_task`/`write_alert`'s `ON CONFLICT
(idempotency_key) DO NOTHING` recognizes it as the same event instead of
inserting a duplicate row. `ip_blacklist`/`ip_rate_limit` don't need this:
they're already idempotent via `ON CONFLICT (ip)` (see write_client.py).
"""
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from . import alerting, heuristics, prompt_builder
from .bedrock_judge import Verdict
from .errors import BedrockJudgeError, CrdbWriteError, McpUnavailableError
from .interfaces import AlertPublisher, EmbedFn, Judge, ReadClient, SignalsGateway, WriteClient

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
    degraded_reason: Optional[str] = None


def run_patrol_round(
    *,
    memory_gateway: SignalsGateway,
    read_client: ReadClient,
    write_client: WriteClient,
    judge: Judge,
    embed_fn: EmbedFn,
    alert_publisher: Optional[AlertPublisher] = None,
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
        idempotency_key = _compute_round_idempotency_key(ip, ip_logs)
        _dispatch_verdict(
            verdict, idempotency_key=idempotency_key, write_client=write_client, embed_fn=embed_fn,
            alert_publisher=alert_publisher,
        )
        verdicts.append(verdict)

    return RoundSummary(logs_read=len(signals.logs), suspicious_ip_count=len(suspicious), verdicts=verdicts)


def _compute_round_idempotency_key(ip, ip_logs):
    ids = sorted(str(row.get("id")) for row in ip_logs if row.get("id"))
    raw = f"{ip}:{','.join(ids)}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _judge_one_ip(*, ip, ip_logs, read_client: ReadClient, judge: Judge, embed_fn: EmbedFn, top_k, ip_history_limit) -> Optional[Verdict]:
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


def _dispatch_verdict(
    verdict: Verdict, *, idempotency_key: str, write_client: WriteClient, embed_fn: EmbedFn,
    alert_publisher: Optional[AlertPublisher] = None,
):
    """Disposal/alert and episode-memory writes are deliberately independent
    failure domains. A confirmed `high` verdict's blacklist/rate-limit/
    lock-account/alert must go out even if the *unrelated* Titan embedding
    call for `agent_episodes` fails (rate limit, transient network blip) --
    letting an embedding hiccup silently cancel an already-decided block is
    a real security gap for a product whose job is automated defense. Only
    the `agent_episodes` memory row is allowed to be skipped on embedding
    failure; see docs/03-open-issues.md #1 for the incident this fixes."""
    if verdict.risk_level == "normal":
        return

    action = verdict.action or {}
    action_type = action.get("type", "none")

    if verdict.risk_level == "high":
        try:
            _execute_disposal_action(verdict, action, action_type, idempotency_key=idempotency_key, write_client=write_client)
            subject, body = alerting.format_alert_message(verdict, action_type)
            alert_id = write_client.write_alert(severity="high", message=body, idempotency_key=idempotency_key)
            _publish_alert(alert_publisher, write_client, alert_id=alert_id, ip=verdict.ip, subject=subject, body=body)
        except CrdbWriteError as exc:
            logger.warning("patrol_write_failed ip=%s risk_level=%s", verdict.ip, verdict.risk_level, exc_info=exc)

    _write_episode(verdict, action_type, idempotency_key=idempotency_key, write_client=write_client, embed_fn=embed_fn)


def _write_episode(verdict: Verdict, action_type, *, idempotency_key: str, write_client: WriteClient, embed_fn: EmbedFn):
    try:
        episode_embedding = embed_fn(verdict.reasoning or verdict.attack_type or verdict.ip)
    except Exception as exc:
        logger.warning("patrol_episode_embedding_failed ip=%s", verdict.ip, exc_info=exc)
        return

    try:
        write_client.write_episode(
            ip=verdict.ip,
            risk_level=verdict.risk_level,
            attack_type=verdict.attack_type,
            reasoning_summary=verdict.reasoning,
            action_taken=action_type if verdict.risk_level == "high" else "none",
            embedding=episode_embedding,
            idempotency_key=idempotency_key,
        )
    except CrdbWriteError as exc:
        logger.warning("patrol_write_failed ip=%s risk_level=%s", verdict.ip, verdict.risk_level, exc_info=exc)


def _publish_alert(alert_publisher: Optional[AlertPublisher], write_client: WriteClient, *, alert_id, ip, subject, body):
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


def _execute_disposal_action(verdict: Verdict, action, action_type, *, idempotency_key: str, write_client: WriteClient):
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
            idempotency_key=idempotency_key,
        )
    else:
        logger.warning("patrol_high_risk_no_action ip=%s action=%r", verdict.ip, action)
