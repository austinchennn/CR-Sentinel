"""Covers BedrockJudge branches services/patrol-agent/tests/test_bedrock_judge.py
doesn't exercise: the lazy `client is None` boto3 branch, Verdict.__repr__,
and the "already a BedrockJudgeError, re-raise as-is" passthrough."""
from patrol_agent.bedrock_judge import BedrockJudge, Verdict
from patrol_agent.errors import BedrockJudgeError


def _tool_use_response(payload):
    return {
        "output": {
            "message": {"content": [{"toolUse": {"name": "emit_patrol_verdict", "input": payload}}]}
        }
    }


def test_verdict_repr_includes_key_fields():
    verdict = Verdict(ip="1.2.3.4", risk_level="high", attack_type="sqli", reasoning="x", action={"type": "blacklist_temporary"})

    text = repr(verdict)

    assert "1.2.3.4" in text
    assert "high" in text
    assert "sqli" in text
    assert "blacklist_temporary" in text


def test_judge_builds_its_own_bedrock_client_when_none_given(fake_boto3):
    fake_boto3.client.converse_response = _tool_use_response(
        {"ip": "1.2.3.4", "risk_level": "normal", "attack_type": "none", "reasoning": "fine"}
    )

    judge = BedrockJudge(model_id="test-model")
    verdict = judge.judge([{"role": "user", "content": [{"text": "hi"}]}])

    assert fake_boto3.calls == ["bedrock-runtime"]
    assert verdict.risk_level == "normal"


def test_judge_reraises_bedrock_judge_error_without_rewrapping():
    class RaisingClient:
        def converse(self, **kwargs):
            raise BedrockJudgeError("already the right type")

    judge = BedrockJudge(client=RaisingClient())

    try:
        judge.judge([])
        raise AssertionError("expected BedrockJudgeError")
    except BedrockJudgeError as exc:
        assert str(exc) == "already the right type"
