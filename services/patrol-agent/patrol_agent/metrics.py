"""CloudWatch custom metrics for one patrol round (PRD-09 functional
requirement 3: "巡检轮次的自定义指标（本轮处理日志数、判定为 high 的数量)"). `boto3`
is imported lazily inside `connect()`, matching every other AWS-touching
module in this package, so tests can supply a fake client instead.
"""
import logging

logger = logging.getLogger(__name__)

NAMESPACE = "CRSentinel/PatrolAgent"


class CloudWatchMetrics:
    def __init__(self, client):
        self._client = client

    @classmethod
    def connect(cls):
        import boto3

        return cls(boto3.client("cloudwatch"))

    def publish_round_summary(self, summary):
        high_count = sum(1 for v in summary.verdicts if v.risk_level == "high")
        low_count = sum(1 for v in summary.verdicts if v.risk_level == "low")

        self._client.put_metric_data(
            Namespace=NAMESPACE,
            MetricData=[
                {"MetricName": "LogsRead", "Value": summary.logs_read, "Unit": "Count"},
                {"MetricName": "SuspiciousIpCount", "Value": summary.suspicious_ip_count, "Unit": "Count"},
                {"MetricName": "HighRiskVerdicts", "Value": high_count, "Unit": "Count"},
                {"MetricName": "LowRiskVerdicts", "Value": low_count, "Unit": "Count"},
                {"MetricName": "RoundDegraded", "Value": 1 if summary.degraded else 0, "Unit": "Count"},
            ],
        )
