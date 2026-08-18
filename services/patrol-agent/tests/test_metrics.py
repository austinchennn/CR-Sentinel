from patrol_agent.bedrock_judge import Verdict
from patrol_agent.metrics import NAMESPACE, CloudWatchMetrics
from patrol_agent.patrol_loop import RoundSummary


class FakeCloudWatchClient:
    def __init__(self):
        self.calls = []

    def put_metric_data(self, **kwargs):
        self.calls.append(kwargs)


def _values(call):
    return {d["MetricName"]: d["Value"] for d in call["MetricData"]}


def test_publish_round_summary_counts_verdicts_by_risk_level():
    client = FakeCloudWatchClient()
    metrics = CloudWatchMetrics(client)
    summary = RoundSummary(
        logs_read=10,
        suspicious_ip_count=3,
        verdicts=[
            Verdict(ip="1.1.1.1", risk_level="high", attack_type="sqli", reasoning="x"),
            Verdict(ip="2.2.2.2", risk_level="low", attack_type="scan", reasoning="y"),
            Verdict(ip="3.3.3.3", risk_level="normal", attack_type="none", reasoning="z"),
        ],
    )

    metrics.publish_round_summary(summary)

    call = client.calls[0]
    assert call["Namespace"] == NAMESPACE
    values = _values(call)
    assert values["LogsRead"] == 10
    assert values["SuspiciousIpCount"] == 3
    assert values["HighRiskVerdicts"] == 1
    assert values["LowRiskVerdicts"] == 1
    assert values["RoundDegraded"] == 0


def test_publish_round_summary_marks_degraded_rounds():
    client = FakeCloudWatchClient()
    metrics = CloudWatchMetrics(client)
    summary = RoundSummary(degraded=True, degraded_reason="mcp down")

    metrics.publish_round_summary(summary)

    values = _values(client.calls[0])
    assert values["RoundDegraded"] == 1
    assert values["LogsRead"] == 0
    assert values["HighRiskVerdicts"] == 0
