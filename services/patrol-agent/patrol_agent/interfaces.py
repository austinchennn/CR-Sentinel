"""Structural (`typing.Protocol`) interfaces for PatrolAgentLambda's
dependency-injection seams: the collaborators `run_patrol_round`
(patrol_loop.py) and `PatrolMemoryGateway` (memory_gateway.py) receive as
constructor/function parameters rather than importing and instantiating
themselves -- the same seams `app.py`'s composition root wires concrete
adapters into, and the same seams tests replace with hand-written fakes
(see tests/test_patrol_loop.py's Fake*).

These are documentation and type-checker aids only, not runtime contracts:
Python's structural typing means `McpReadOnlyClient`, `CrdbWriteClient`,
`BedrockJudge`, and `SnsAlertPublisher` already satisfy the matching
Protocol below without inheriting from it or importing this module -- so
does every `Fake*` test double. Nothing here changes behavior; this module
exists so a reader (or a new adapter -- a second `WriteClient` backed by a
different store, say) can see the full contract in one place instead of
inferring it from `CrdbWriteClient`'s implementation.
"""
from typing import Callable, Optional, Protocol

from .bedrock_judge import Verdict
from .memory_gateway import PatrolSignals


class ReadClient(Protocol):
    def read_recent_logs(self, minutes: int = ...) -> list: ...
    def semantic_search_attack_signatures(self, embedding: list, top_k: int = ...) -> list: ...
    def read_ip_episodes(self, ip: str, limit: int = ...) -> list: ...


class WriteClient(Protocol):
    def write_blacklist(self, ip, risk_level, block_until, attack_reason) -> None: ...
    def write_rate_limit(self, ip, limit_per_min, expires_at) -> None: ...
    def lock_account(self, user_id, reason) -> None: ...
    def write_episode(self, *, ip, risk_level, attack_type, reasoning_summary, action_taken, embedding) -> None: ...
    def write_task(self, task_type, payload) -> None: ...
    def write_alert(self, severity: str, message: str) -> str: ...
    def mark_alert_sent(self, alert_id: str) -> None: ...


class Judge(Protocol):
    def judge(self, messages: list) -> Verdict: ...


class AlertPublisher(Protocol):
    def publish(self, subject: str, message: str) -> None: ...


class SignalsGateway(Protocol):
    def gather_signals(
        self, *, minutes: int = ..., suspicious_embedding: Optional[list] = ..., ip: Optional[str] = ..., top_k: int = ...
    ) -> PatrolSignals: ...


EmbedFn = Callable[[str], list]
