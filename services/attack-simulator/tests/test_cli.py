import pytest

from attack_simulator import cli
from attack_simulator.http_client import Response


def _no_sleep(seconds):
    pass


class _FakeClient:
    def __init__(self, base_url):
        self.base_url = base_url
        self.calls = []

    def get(self, path, params=None):
        self.calls.append(("GET", path, params))
        return Response(200, b"{}")

    def post(self, path, json_body=None):
        self.calls.append(("POST", path, json_body))
        return Response(200, b"{}")


def test_main_runs_a_single_named_scenario(capsys):
    clients = []
    exit_code = cli.main(
        ["idor_enumeration", "--base-url", "https://example.com/Prod"],
        client_factory=lambda base_url: clients.append(_FakeClient(base_url)) or clients[-1],
        sleep_fn=_no_sleep,
    )

    assert exit_code == 0
    assert len(clients[0].calls) == 10  # len(idor_enumeration.USER_IDS)
    out = capsys.readouterr().out
    assert "idor_enumeration" in out
    assert "risk_level=high" in out


def test_main_runs_all_scenarios_when_given_all(capsys):
    exit_code = cli.main(
        ["all", "--base-url", "https://example.com/Prod"],
        client_factory=_FakeClient,
        sleep_fn=_no_sleep,
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    for name in ("obfuscated_sqli", "slow_bruteforce", "idor_enumeration", "chained_intrusion"):
        assert name in out


def test_main_rejects_unknown_scenario():
    with pytest.raises(SystemExit):
        cli.main(["not_a_real_scenario", "--base-url", "https://example.com"])
