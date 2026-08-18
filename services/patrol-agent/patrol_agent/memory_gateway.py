"""Ties the read-only MCP channel's three methods together with the
degrade-on-failure behavior PRD-03 functional requirement 6 asks for: if
the MCP channel is unavailable, skip the round cleanly (empty signals,
`degraded=True`, one log line) instead of raising out of the patrol loop
or proceeding to disposal writes on partial data.

PatrolAgentLambda (PRD-04) is expected to check `degraded` before calling
Bedrock at all -- there's nothing useful to reason about without logs.
"""
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from .errors import McpUnavailableError

if TYPE_CHECKING:
    # Deferred to avoid a cycle: interfaces.py imports PatrolSignals from
    # this module for SignalsGateway's return type, so this module can only
    # reach back for ReadClient under TYPE_CHECKING, never at import time.
    from .interfaces import ReadClient

logger = logging.getLogger(__name__)


@dataclass
class PatrolSignals:
    logs: list = field(default_factory=list)
    similar_attacks: list = field(default_factory=list)
    ip_history: list = field(default_factory=list)
    degraded: bool = False
    degraded_reason: Optional[str] = None


class PatrolMemoryGateway:
    def __init__(self, read_client: "ReadClient"):
        self._read = read_client

    def gather_signals(self, *, minutes=5, suspicious_embedding: Optional[list] = None, ip: Optional[str] = None, top_k=5) -> PatrolSignals:
        try:
            logs = self._read.read_recent_logs(minutes=minutes)
            similar_attacks = (
                self._read.semantic_search_attack_signatures(suspicious_embedding, top_k=top_k)
                if suspicious_embedding is not None
                else []
            )
            ip_history = self._read.read_ip_episodes(ip, limit=20) if ip else []
        except McpUnavailableError as exc:
            logger.warning("patrol_round_degraded reason=%r", str(exc))
            return PatrolSignals(degraded=True, degraded_reason=str(exc))

        return PatrolSignals(logs=logs, similar_attacks=similar_attacks, ip_history=ip_history)
