import pytest

from patrol_agent.bedrock_judge import BedrockJudge
from patrol_agent.errors import BedrockJudgeError


class FakeConverseClient:
    def __init__(self, response=None, raise_exc=None):
        self._response = response
        self._raise_exc = raise_exc
        self.calls = []

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        if self._raise_exc is not None:
            raise self._raise_exc
        return self._response


def _tool_use_response(payload):
    return {
        "output": {
            "message": {
                "content": [
                    {"toolUse": {"name": "emit_patrol_verdict", "input": payload}},
                ]
            }
        }
    }


def test_judge_forces_the_verdict_tool_choice():
    client = FakeConverseClient(response=_tool_use_response(
        {"ip": "1.2.3.4", "risk_level": "high", "attack_type": "sqli", "reasoning": "obvious injection"}
    ))
    judge = BedrockJudge(client=client, model_id="test-model")

    verdict = judge.judge([{"role": "user", "content": [{"text": "hi"}]}])

    assert verdict.ip == "1.2.3.4"
    assert verdict.risk_level == "high"
    call = client.calls[0]
    assert call["modelId"] == "test-model"
    assert call["toolConfig"]["toolChoice"] == {"tool": {"name": "emit_patrol_verdict"}}


def test_judge_parses_action_payload():
    client = FakeConverseClient(response=_tool_use_response({
        "ip": "1.2.3.4",
        "risk_level": "high",
        "attack_type": "bruteforce",
        "reasoning": "many failed logins",
        "action": {"type": "blacklist_temporary", "block_hours": 24},
    }))
    judge = BedrockJudge(client=client)

    verdict = judge.judge([])

    assert verdict.action == {"type": "blacklist_temporary", "block_hours": 24}


def test_judge_defaults_action_to_empty_dict_when_absent():
    client = FakeConverseClient(response=_tool_use_response(
        {"ip": "1.2.3.4", "risk_level": "normal", "attack_type": "none", "reasoning": "fine"}
    ))
    judge = BedrockJudge(client=client)

    verdict = judge.judge([])

    assert verdict.action == {}


def test_judge_raises_on_converse_failure():
    client = FakeConverseClient(raise_exc=RuntimeError("throttled"))
    judge = BedrockJudge(client=client)

    with pytest.raises(BedrockJudgeError):
        judge.judge([])


def test_judge_raises_when_no_tool_use_block_present():
    client = FakeConverseClient(response={"output": {"message": {"content": [{"text": "sorry, I can't"}]}}})
    judge = BedrockJudge(client=client)

    with pytest.raises(BedrockJudgeError):
        judge.judge([])


def test_judge_raises_on_invalid_risk_level():
    client = FakeConverseClient(response=_tool_use_response(
        {"ip": "1.2.3.4", "risk_level": "critical", "attack_type": "sqli", "reasoning": "x"}
    ))
    judge = BedrockJudge(client=client)

    with pytest.raises(BedrockJudgeError):
        judge.judge([])


def test_judge_raises_when_required_field_missing():
    client = FakeConverseClient(response=_tool_use_response({"risk_level": "high"}))
    judge = BedrockJudge(client=client)

    with pytest.raises(BedrockJudgeError):
        judge.judge([])
