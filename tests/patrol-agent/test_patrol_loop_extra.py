"""Covers patrol_loop._dispatch_verdict/_write_episode's episode-embedding-
failure branch (patrol_agent/patrol_loop.py), which
services/patrol-agent/tests/test_patrol_loop.py's own embedding-failure
test doesn't exercise the same way: that one only fails the *first*
embed_fn call (the per-IP query embedding in _judge_one_ip), never the
second one (the episode embedding, only reached for a non-normal verdict).

Per docs/03-open-issues.md #2 (fixed): a transient episode-embedding
failure only drops the `agent_episodes` memory row now, not the disposal
action or alert for a `high` verdict -- those two are independent failure
domains."""
from patrol_agent.bedrock_judge import Verdict
from patrol_agent.errors import McpUnavailableError
from patrol_agent.memory_gateway import PatrolMemoryGateway
from patrol_agent.patrol_loop import run_patrol_round


class _FakeReadClient:
    def __init__(self, logs):
        self._logs = logs

    def read_recent_logs(self, minutes):
        return self._logs

    def semantic_search_attack_signatures(self, embedding, top_k):
        return []

    def read_ip_episodes(self, ip, limit):
        return []


class _FakeJudge:
    def __init__(self, verdict):
        self._verdict = verdict

    def judge(self, messages):
        return self._verdict


class _FakeWriteClient:
    def __init__(self):
        self.calls = []

    def write_blacklist(self, **kwargs):
        self.calls.append(("write_blacklist", kwargs))

    def write_rate_limit(self, **kwargs):
        self.calls.append(("write_rate_limit", kwargs))

    def lock_account(self, *args, **kwargs):
        self.calls.append(("lock_account", kwargs))

    def write_episode(self, **kwargs):
        self.calls.append(("write_episode", kwargs))

    def write_task(self, *args, **kwargs):
        self.calls.append(("write_task", kwargs))

    def write_alert(self, **kwargs):
        self.calls.append(("write_alert", kwargs))


def _row(ip):
    return {"src_ip": ip, "status_code": 403, "path": "/admin", "query_params": "", "body_snippet": "", "method": "GET"}


def test_episode_embedding_failure_on_a_high_verdict_does_not_skip_disposal_or_alert():
    verdict = Verdict(
        ip="1.1.1.1", risk_level="high", attack_type="sqli", reasoning="union select attack",
        action={"type": "blacklist_temporary", "block_hours": 12},
    )
    write_client = _FakeWriteClient()
    read_client = _FakeReadClient([_row("1.1.1.1")])
    gateway = PatrolMemoryGateway(read_client)

    calls = []

    def embed_fn(text):
        calls.append(text)
        if len(calls) == 1:
            return [0.1, 0.2]
        raise RuntimeError("titan throttled")

    summary = run_patrol_round(
        memory_gateway=gateway, read_client=read_client, write_client=write_client,
        judge=_FakeJudge(verdict), embed_fn=embed_fn,
    )

    assert len(summary.verdicts) == 1
    call_names = [name for name, _ in write_client.calls]
    assert "write_blacklist" in call_names
    assert "write_alert" in call_names
    assert "write_episode" not in call_names


def test_episode_embedding_failure_on_a_low_verdict_skips_the_episode_write():
    verdict = Verdict(ip="1.1.1.1", risk_level="low", attack_type="scan", reasoning="probed /admin")
    write_client = _FakeWriteClient()
    read_client = _FakeReadClient([_row("1.1.1.1")])
    gateway = PatrolMemoryGateway(read_client)

    calls = []

    def embed_fn(text):
        calls.append(text)
        if len(calls) == 1:
            return [0.1, 0.2]
        raise RuntimeError("titan throttled")

    run_patrol_round(
        memory_gateway=gateway, read_client=read_client, write_client=write_client,
        judge=_FakeJudge(verdict), embed_fn=embed_fn,
    )

    assert write_client.calls == []
