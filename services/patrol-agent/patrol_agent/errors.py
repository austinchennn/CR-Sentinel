"""Exceptions that distinguish which channel failed.

PatrolAgentLambda (PRD-04) needs to tell "MCP read channel is down, skip
this round" apart from "write channel rejected a disposal action" -- the
two failure modes call for different degradation strategies (see PRD-03
functional requirement 6).
"""


class McpUnavailableError(Exception):
    """The read-only MCP channel could not complete a call (connect,
    timeout, or a tool-level error). Callers should treat the current
    patrol round as unusable and retry next cycle rather than proceed on
    partial data."""


class CrdbWriteError(Exception):
    """The independent least-privilege write channel rejected or failed a
    disposal write. Distinct from McpUnavailableError so callers can log
    and alert on it without conflating it with a read-side degradation."""


class BedrockJudgeError(Exception):
    """The Bedrock Claude tool-use call failed, timed out, or returned a
    verdict that doesn't match the forced JSON schema. The patrol loop
    (PRD-04) catches this per-IP and skips disposal for that IP rather than
    aborting the whole round -- one malformed verdict shouldn't stop later
    IPs in the same window from being judged."""
