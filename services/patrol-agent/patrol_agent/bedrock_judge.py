"""Bedrock Claude tool-use call and structured-output parsing (PRD-04
functional requirement 3).

Uses the Converse API with `toolChoice` pinned to `emit_patrol_verdict`
rather than free-text prompting plus a JSON parser -- forcing the tool
choice is what PRD-04's acceptance criterion "跑 10 次不同输入，输出格式无解析
失败" is actually asking for: the model cannot reply with prose instead of
the schema.

`boto3` is imported lazily inside `__init__`, matching every other
lazy-import module in this package, so tests can supply a fake client
without the dependency installed.
"""
import logging

from .config import BedrockConfig
from .errors import BedrockJudgeError
from .prompt_builder import SYSTEM_PROMPT, VERDICT_TOOL, VERDICT_TOOL_NAME

logger = logging.getLogger(__name__)

VALID_RISK_LEVELS = {"normal", "low", "high"}


class Verdict:
    def __init__(self, *, ip, risk_level, attack_type, reasoning, action=None):
        self.ip = ip
        self.risk_level = risk_level
        self.attack_type = attack_type
        self.reasoning = reasoning
        self.action = action or {}

    def __repr__(self):
        return (
            f"Verdict(ip={self.ip!r}, risk_level={self.risk_level!r}, "
            f"attack_type={self.attack_type!r}, action={self.action!r})"
        )


class BedrockJudge:
    def __init__(self, client=None, model_id=None):
        if client is None:
            import boto3

            client = boto3.client("bedrock-runtime")
        self._client = client
        self._model_id = model_id or BedrockConfig.model_id

    def judge(self, messages):
        try:
            response = self._client.converse(
                modelId=self._model_id,
                system=[{"text": SYSTEM_PROMPT}],
                messages=messages,
                toolConfig={
                    "tools": [VERDICT_TOOL],
                    "toolChoice": {"tool": {"name": VERDICT_TOOL_NAME}},
                },
            )
        except BedrockJudgeError:
            raise
        except Exception as exc:
            logger.warning("bedrock_converse_failed", exc_info=exc)
            raise BedrockJudgeError(str(exc)) from exc

        return _parse_verdict(response)


def _parse_verdict(response):
    try:
        content = response["output"]["message"]["content"]
        tool_use = next(block["toolUse"] for block in content if "toolUse" in block)
        payload = tool_use["input"]

        risk_level = payload["risk_level"]
        if risk_level not in VALID_RISK_LEVELS:
            raise ValueError(f"unexpected risk_level {risk_level!r}")

        return Verdict(
            ip=payload["ip"],
            risk_level=risk_level,
            attack_type=payload.get("attack_type", "unknown"),
            reasoning=payload.get("reasoning", ""),
            action=payload.get("action"),
        )
    except (KeyError, StopIteration, ValueError, TypeError) as exc:
        raise BedrockJudgeError(f"malformed Bedrock verdict: {exc}") from exc
