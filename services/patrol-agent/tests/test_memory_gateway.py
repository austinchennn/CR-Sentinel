from patrol_agent.errors import McpUnavailableError
from patrol_agent.memory_gateway import PatrolMemoryGateway


class FakeReadClient:
    def __init__(self, logs=None, similar=None, history=None, fail=False):
        self._logs = logs or []
        self._similar = similar or []
        self._history = history or []
        self._fail = fail
        self.calls = []

    def read_recent_logs(self, minutes):
        self.calls.append(("read_recent_logs", minutes))
        if self._fail:
            raise McpUnavailableError("mcp timeout")
        return self._logs

    def semantic_search_attack_signatures(self, embedding, top_k):
        self.calls.append(("semantic_search_attack_signatures", top_k))
        return self._similar

    def read_ip_episodes(self, ip, limit):
        self.calls.append(("read_ip_episodes", ip, limit))
        return self._history


def test_gather_signals_combines_all_three_reads():
    read_client = FakeReadClient(
        logs=[{"id": "1"}], similar=[{"id": "sig-1"}], history=[{"id": "ep-1"}]
    )
    gateway = PatrolMemoryGateway(read_client)

    signals = gateway.gather_signals(minutes=5, suspicious_embedding=[0.1, 0.2], ip="203.0.113.5")

    assert signals.degraded is False
    assert signals.logs == [{"id": "1"}]
    assert signals.similar_attacks == [{"id": "sig-1"}]
    assert signals.ip_history == [{"id": "ep-1"}]


def test_gather_signals_skips_optional_reads_when_not_requested():
    read_client = FakeReadClient(logs=[{"id": "1"}])
    gateway = PatrolMemoryGateway(read_client)

    signals = gateway.gather_signals(minutes=5)

    assert signals.similar_attacks == []
    assert signals.ip_history == []
    assert [c[0] for c in read_client.calls] == ["read_recent_logs"]


def test_gather_signals_degrades_on_mcp_failure_without_raising():
    read_client = FakeReadClient(fail=True)
    gateway = PatrolMemoryGateway(read_client)

    signals = gateway.gather_signals(minutes=5, ip="203.0.113.5")

    assert signals.degraded is True
    assert signals.degraded_reason == "mcp timeout"
    assert signals.logs == []
    assert signals.similar_attacks == []
    assert signals.ip_history == []
