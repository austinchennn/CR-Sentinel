from patrol_agent.alerting import SnsAlertPublisher, format_alert_message
from patrol_agent.bedrock_judge import Verdict


def test_format_alert_message_includes_key_fields():
    verdict = Verdict(
        ip="203.0.113.5",
        risk_level="high",
        attack_type="sqli",
        reasoning="repeated union select probes",
    )

    subject, body = format_alert_message(verdict, "blacklist_temporary")

    assert "203.0.113.5" in subject
    assert "sqli" in subject
    for expected in ("203.0.113.5", "high", "sqli", "blacklist_temporary", "repeated union select probes"):
        assert expected in body


class FakeSnsClient:
    def __init__(self):
        self.calls = []

    def publish(self, **kwargs):
        self.calls.append(kwargs)


def test_sns_alert_publisher_publishes_to_configured_topic():
    client = FakeSnsClient()
    publisher = SnsAlertPublisher(client, "arn:aws:sns:us-east-1:123456789012:cr-sentinel-alerts")

    publisher.publish("subject line", "message body")

    assert client.calls == [
        {
            "TopicArn": "arn:aws:sns:us-east-1:123456789012:cr-sentinel-alerts",
            "Subject": "subject line",
            "Message": "message body",
        }
    ]
