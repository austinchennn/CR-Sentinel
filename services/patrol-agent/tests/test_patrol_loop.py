from datetime import datetime, timezone

from patrol_agent.bedrock_judge import Verdict
from patrol_agent.errors import BedrockJudgeError, CrdbWriteError, McpUnavailableError
from patrol_agent.memory_gateway import PatrolMemoryGateway
from patrol_agent.patrol_loop import run_patrol_round


class FakeReadClient:
    def __init__(self, logs, similar=None, history=None, fail_read_recent_logs=False, fail_history_for=None):
        self._logs = logs
        self._similar = similar if similar is not None else []
        self._history = history if history is not None else []
        self._fail_read_recent_logs = fail_read_recent_logs
        self._fail_history_for = fail_history_for or set()
        self.calls = []

    def read_recent_logs(self, minutes):
        self.calls.append(("read_recent_logs", minutes))
        if self._fail_read_recent_logs:
            raise McpUnavailableError("mcp down")
        return self._logs

    def semantic_search_attack_signatures(self, embedding, top_k):
        self.calls.append(("semantic_search_attack_signatures", top_k))
        return self._similar

    def read_ip_episodes(self, ip, limit):
        self.calls.append(("read_ip_episodes", ip, limit))
        if ip in self._fail_history_for:
            raise McpUnavailableError("history unavailable")
        return self._history


class FakeJudge:
    def __init__(self, verdicts_by_ip=None, raise_for=None):
        self._verdicts_by_ip = verdicts_by_ip or {}
        self._raise_for = raise_for or set()
        self.calls = []

    def judge(self, messages):
        text = messages[0]["content"][0]["text"]
        ip = text.splitlines()[0][len("# Patrol round for IP "):]
        self.calls.append(ip)
        if ip in self._raise_for:
            raise BedrockJudgeError("simulated bedrock failure")
        return self._verdicts_by_ip[ip]


class FakeWriteClient:
    def __init__(self, fail_on=None):
        self.calls = []
        self._fail_on = fail_on or set()
        self._next_alert_id = 0

    def _record(self, name, kwargs):
        if name in self._fail_on:
            raise CrdbWriteError("simulated write failure")
        self.calls.append((name, kwargs))

    def write_blacklist(self, ip, risk_level, block_until, attack_reason):
        self._record("write_blacklist", dict(ip=ip, risk_level=risk_level, block_until=block_until, attack_reason=attack_reason))

    def write_rate_limit(self, ip, limit_per_min, expires_at):
        self._record("write_rate_limit", dict(ip=ip, limit_per_min=limit_per_min, expires_at=expires_at))

    def lock_account(self, user_id, reason):
        self._record("lock_account", dict(user_id=user_id, reason=reason))

    def write_episode(self, *, ip, risk_level, attack_type, reasoning_summary, action_taken, embedding):
        self._record("write_episode", dict(ip=ip, risk_level=risk_level, attack_type=attack_type, reasoning_summary=reasoning_summary, action_taken=action_taken, embedding=embedding))

    def write_task(self, task_type, payload):
        self._record("write_task", dict(task_type=task_type, payload=payload))

    def write_alert(self, severity, message):
        self._next_alert_id += 1
        alert_id = f"alert-{self._next_alert_id}"
        self._record("write_alert", dict(severity=severity, message=message, alert_id=alert_id))
        return alert_id

    def mark_alert_sent(self, alert_id):
        self._record("mark_alert_sent", dict(alert_id=alert_id))

    def calls_named(self, name):
        return [kwargs for call_name, kwargs in self.calls if call_name == name]


class FakeAlertPublisher:
    def __init__(self, fail=False):
        self.published = []
        self._fail = fail

    def publish(self, subject, message):
        if self._fail:
            raise RuntimeError("simulated SNS failure")
        self.published.append((subject, message))


def _suspicious_row(ip, status_code=403):
    return {"src_ip": ip, "status_code": status_code, "path": "/admin", "query_params": "", "body_snippet": "", "method": "GET"}


def _run(logs, write_client, judge, *, similar=None, history=None, fail_read_recent_logs=False, fail_history_for=None, alert_publisher=None):
    read_client = FakeReadClient(logs, similar=similar, history=history, fail_read_recent_logs=fail_read_recent_logs, fail_history_for=fail_history_for)
    gateway = PatrolMemoryGateway(read_client)
    embed_fn = lambda text: [0.1, 0.2, 0.3]
    summary = run_patrol_round(
        memory_gateway=gateway, read_client=read_client, write_client=write_client, judge=judge, embed_fn=embed_fn,
        alert_publisher=alert_publisher,
    )
    return summary, read_client


def test_degraded_when_mcp_read_recent_logs_fails():
    write_client = FakeWriteClient()
    judge = FakeJudge()

    summary, _ = _run([], write_client, judge, fail_read_recent_logs=True)

    assert summary.degraded is True
    assert summary.degraded_reason == "mcp down"
    assert write_client.calls == []
    assert judge.calls == []


def test_no_logs_returns_empty_summary():
    write_client = FakeWriteClient()
    judge = FakeJudge()

    summary, _ = _run([], write_client, judge)

    assert summary.logs_read == 0
    assert summary.suspicious_ip_count == 0
    assert summary.verdicts == []


def test_normal_verdict_writes_nothing():
    logs = [_suspicious_row("1.1.1.1")]
    judge = FakeJudge(verdicts_by_ip={
        "1.1.1.1": Verdict(ip="1.1.1.1", risk_level="normal", attack_type="none", reasoning="fine"),
    })
    write_client = FakeWriteClient()

    summary, _ = _run(logs, write_client, judge)

    assert len(summary.verdicts) == 1
    assert write_client.calls == []


def test_low_verdict_writes_episode_only():
    logs = [_suspicious_row("1.1.1.1")]
    judge = FakeJudge(verdicts_by_ip={
        "1.1.1.1": Verdict(ip="1.1.1.1", risk_level="low", attack_type="scan", reasoning="probed /admin"),
    })
    write_client = FakeWriteClient()

    _run(logs, write_client, judge)

    assert [name for name, _ in write_client.calls] == ["write_episode"]
    episode = write_client.calls_named("write_episode")[0]
    assert episode["risk_level"] == "low"
    assert episode["action_taken"] == "none"


def test_high_verdict_blacklist_temporary_writes_blacklist_alert_and_episode():
    logs = [_suspicious_row("1.1.1.1")]
    judge = FakeJudge(verdicts_by_ip={
        "1.1.1.1": Verdict(
            ip="1.1.1.1", risk_level="high", attack_type="sqli", reasoning="union select attack",
            action={"type": "blacklist_temporary", "block_hours": 12},
        ),
    })
    write_client = FakeWriteClient()

    before = datetime.now(timezone.utc)
    _run(logs, write_client, judge)

    assert [name for name, _ in write_client.calls] == ["write_blacklist", "write_alert", "write_episode"]
    blacklist = write_client.calls_named("write_blacklist")[0]
    assert blacklist["ip"] == "1.1.1.1"
    assert blacklist["block_until"] > before
    episode = write_client.calls_named("write_episode")[0]
    assert episode["action_taken"] == "blacklist_temporary"


def test_high_verdict_blacklist_permanent_sets_block_until_none():
    logs = [_suspicious_row("1.1.1.1")]
    judge = FakeJudge(verdicts_by_ip={
        "1.1.1.1": Verdict(
            ip="1.1.1.1", risk_level="high", attack_type="sqli", reasoning="repeat offender",
            action={"type": "blacklist_permanent"},
        ),
    })
    write_client = FakeWriteClient()

    _run(logs, write_client, judge)

    blacklist = write_client.calls_named("write_blacklist")[0]
    assert blacklist["block_until"] is None


def test_high_verdict_rate_limit_uses_action_params():
    logs = [_suspicious_row("1.1.1.1")]
    judge = FakeJudge(verdicts_by_ip={
        "1.1.1.1": Verdict(
            ip="1.1.1.1", risk_level="high", attack_type="scan", reasoning="crawling",
            action={"type": "rate_limit", "limit_per_min": 3},
        ),
    })
    write_client = FakeWriteClient()

    _run(logs, write_client, judge)

    rate_limit = write_client.calls_named("write_rate_limit")[0]
    assert rate_limit["limit_per_min"] == 3


def test_high_verdict_lock_account_calls_lock_account():
    logs = [_suspicious_row("1.1.1.1")]
    judge = FakeJudge(verdicts_by_ip={
        "1.1.1.1": Verdict(
            ip="1.1.1.1", risk_level="high", attack_type="account_takeover", reasoning="anomalous login",
            action={"type": "lock_account", "user_id": "u-1001"},
        ),
    })
    write_client = FakeWriteClient()

    _run(logs, write_client, judge)

    lock = write_client.calls_named("lock_account")[0]
    assert lock["user_id"] == "u-1001"


def test_high_verdict_lock_account_without_user_id_skips_disposal_but_still_records():
    logs = [_suspicious_row("1.1.1.1")]
    judge = FakeJudge(verdicts_by_ip={
        "1.1.1.1": Verdict(
            ip="1.1.1.1", risk_level="high", attack_type="account_takeover", reasoning="anomalous login",
            action={"type": "lock_account"},
        ),
    })
    write_client = FakeWriteClient()

    _run(logs, write_client, judge)

    assert write_client.calls_named("lock_account") == []
    assert [name for name, _ in write_client.calls] == ["write_alert", "write_episode"]


def test_high_verdict_task_queue_writes_json_payload():
    logs = [_suspicious_row("1.1.1.1")]
    judge = FakeJudge(verdicts_by_ip={
        "1.1.1.1": Verdict(
            ip="1.1.1.1", risk_level="high", attack_type="sqli", reasoning="needs parameterization",
            action={"type": "task_queue", "task_note": "add param whitelist"},
        ),
    })
    write_client = FakeWriteClient()

    _run(logs, write_client, judge)

    task = write_client.calls_named("write_task")[0]
    assert task["task_type"] == "hardening_suggestion"
    assert "add param whitelist" in task["payload"]


def test_high_verdict_unknown_action_type_still_writes_alert_and_episode():
    logs = [_suspicious_row("1.1.1.1")]
    judge = FakeJudge(verdicts_by_ip={
        "1.1.1.1": Verdict(ip="1.1.1.1", risk_level="high", attack_type="sqli", reasoning="x", action={}),
    })
    write_client = FakeWriteClient()

    _run(logs, write_client, judge)

    assert [name for name, _ in write_client.calls] == ["write_alert", "write_episode"]


def test_ip_with_failing_embedding_is_skipped_others_still_processed():
    logs = [_suspicious_row("1.1.1.1"), _suspicious_row("2.2.2.2")]
    judge = FakeJudge(verdicts_by_ip={
        "2.2.2.2": Verdict(ip="2.2.2.2", risk_level="normal", attack_type="none", reasoning="fine"),
    })
    write_client = FakeWriteClient()
    read_client = FakeReadClient(logs)
    gateway = PatrolMemoryGateway(read_client)

    calls = []

    def embed_fn(text):
        calls.append(text)
        if len(calls) == 1:
            raise RuntimeError("embedding backend down")
        return [0.1]

    summary = run_patrol_round(memory_gateway=gateway, read_client=read_client, write_client=write_client, judge=judge, embed_fn=embed_fn)

    assert judge.calls == ["2.2.2.2"]
    assert len(summary.verdicts) == 1


def test_ip_with_failing_history_lookup_is_skipped():
    logs = [_suspicious_row("1.1.1.1")]
    judge = FakeJudge()
    write_client = FakeWriteClient()

    summary, _ = _run(logs, write_client, judge, fail_history_for={"1.1.1.1"})

    assert summary.verdicts == []
    assert judge.calls == []


def test_ip_with_bedrock_failure_is_skipped():
    logs = [_suspicious_row("1.1.1.1")]
    judge = FakeJudge(raise_for={"1.1.1.1"})
    write_client = FakeWriteClient()

    summary, _ = _run(logs, write_client, judge)

    assert summary.verdicts == []
    assert write_client.calls == []


def test_high_verdict_publishes_alert_and_marks_sent():
    logs = [_suspicious_row("1.1.1.1")]
    judge = FakeJudge(verdicts_by_ip={
        "1.1.1.1": Verdict(
            ip="1.1.1.1", risk_level="high", attack_type="sqli", reasoning="union select attack",
            action={"type": "blacklist_temporary", "block_hours": 12},
        ),
    })
    write_client = FakeWriteClient()
    alert_publisher = FakeAlertPublisher()

    _run(logs, write_client, judge, alert_publisher=alert_publisher)

    assert len(alert_publisher.published) == 1
    subject, body = alert_publisher.published[0]
    assert "1.1.1.1" in subject
    assert "1.1.1.1" in body
    alert = write_client.calls_named("write_alert")[0]
    marked = write_client.calls_named("mark_alert_sent")[0]
    assert marked["alert_id"] == alert["alert_id"]


def test_high_verdict_without_alert_publisher_skips_publish_but_still_writes():
    logs = [_suspicious_row("1.1.1.1")]
    judge = FakeJudge(verdicts_by_ip={
        "1.1.1.1": Verdict(
            ip="1.1.1.1", risk_level="high", attack_type="sqli", reasoning="x",
            action={"type": "blacklist_temporary"},
        ),
    })
    write_client = FakeWriteClient()

    _run(logs, write_client, judge, alert_publisher=None)

    assert write_client.calls_named("write_alert")
    assert write_client.calls_named("mark_alert_sent") == []


def test_alert_publish_failure_does_not_block_episode_write():
    logs = [_suspicious_row("1.1.1.1")]
    judge = FakeJudge(verdicts_by_ip={
        "1.1.1.1": Verdict(
            ip="1.1.1.1", risk_level="high", attack_type="sqli", reasoning="x",
            action={"type": "blacklist_temporary"},
        ),
    })
    write_client = FakeWriteClient()
    alert_publisher = FakeAlertPublisher(fail=True)

    _run(logs, write_client, judge, alert_publisher=alert_publisher)

    assert write_client.calls_named("mark_alert_sent") == []
    assert write_client.calls_named("write_episode")


def test_high_verdict_episode_embedding_failure_does_not_block_disposal_or_alert():
    logs = [_suspicious_row("1.1.1.1")]
    judge = FakeJudge(verdicts_by_ip={
        "1.1.1.1": Verdict(
            ip="1.1.1.1", risk_level="high", attack_type="sqli", reasoning="union select attack",
            action={"type": "blacklist_temporary", "block_hours": 12},
        ),
    })
    write_client = FakeWriteClient()
    alert_publisher = FakeAlertPublisher()
    read_client = FakeReadClient(logs)
    gateway = PatrolMemoryGateway(read_client)

    calls = []

    def embed_fn(text):
        calls.append(text)
        if len(calls) == 1:
            return [0.1, 0.2, 0.3]
        raise RuntimeError("embedding backend down")

    summary = run_patrol_round(
        memory_gateway=gateway, read_client=read_client, write_client=write_client, judge=judge,
        embed_fn=embed_fn, alert_publisher=alert_publisher,
    )

    assert len(summary.verdicts) == 1
    assert write_client.calls_named("write_blacklist")
    assert write_client.calls_named("write_alert")
    assert alert_publisher.published
    assert write_client.calls_named("write_episode") == []


def test_disposal_write_failure_does_not_block_episode_write():
    logs = [_suspicious_row("1.1.1.1")]
    judge = FakeJudge(verdicts_by_ip={
        "1.1.1.1": Verdict(
            ip="1.1.1.1", risk_level="high", attack_type="sqli", reasoning="x",
            action={"type": "blacklist_temporary"},
        ),
    })
    write_client = FakeWriteClient(fail_on={"write_blacklist"})

    _run(logs, write_client, judge)

    assert write_client.calls_named("write_episode")


def test_write_failure_is_swallowed_not_raised():
    logs = [_suspicious_row("1.1.1.1")]
    judge = FakeJudge(verdicts_by_ip={
        "1.1.1.1": Verdict(ip="1.1.1.1", risk_level="low", attack_type="scan", reasoning="probed"),
    })
    write_client = FakeWriteClient(fail_on={"write_episode"})

    summary, _ = _run(logs, write_client, judge)

    assert len(summary.verdicts) == 1
