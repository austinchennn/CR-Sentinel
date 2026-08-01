"""Static business context, the forced tool-use schema, and per-IP message
assembly for Bedrock Claude (PRD-04 functional requirements 2-3).

The demo target app's endpoint descriptions below (PRD-02) are the
"静态业务规则说明" the architecture doc calls for -- without them Claude has
no baseline for what "normal" traffic to this specific app looks like, only
generic web-attack knowledge.
"""

VERDICT_TOOL_NAME = "emit_patrol_verdict"

RISK_LEVELS = ("normal", "low", "high")
ACTION_TYPES = ("none", "rate_limit", "blacklist_temporary", "blacklist_permanent", "lock_account", "task_queue")

SYSTEM_PROMPT = """You are CR-Sentinel's patrol agent: a security analyst reviewing recent \
HTTP access logs for a small demo web app, backed by a CockroachDB memory layer instead of \
static regex/threshold rules.

Demo app surface (docs/prd/PRD-02-demo-target-app.md) -- your baseline for "normal" traffic:
- POST /login -- weak-credential auth with no built-in rate limiting or lockout. Many failed \
attempts from one IP in a short window is a brute-force signal.
- GET /profile?id=<user_id> -- returns whatever account the id param names, with no ownership \
check. Sequential or enumerated id values from one IP is an IDOR/enumeration signal.
- GET/POST /comments -- accepts and echoes arbitrary text with no filtering. Encoded or \
obfuscated <script> payloads or social-engineering links are the XSS/phishing signal.
- GET /admin -- unauthenticated, always answers 200. Repeated probing of this or other unknown \
paths is a scan/recon signal.

You are given, for one IP: its raw log rows from this patrol round, attack_signatures \
semantically recalled from CockroachDB's vector index (your long-term memory of known attack \
patterns), and this IP's agent_episodes history (your own episodic memory of past verdicts on \
this same IP). Weigh the episodes history explicitly: a second suspicious round from an IP you \
already flagged should usually escalate rather than reset to normal, and your reasoning should \
say so when it applies.

Classify risk_level as exactly one of: normal (no real signal), low (scanning/probing worth \
recording but not blocking), or high (confirmed attack pattern -- injection, brute force, \
IDOR abuse, XSS/phishing payloads, or an IP already known from agent_episodes escalating \
further). Always call emit_patrol_verdict exactly once with your structured verdict; never \
respond in plain text."""

VERDICT_TOOL = {
    "toolSpec": {
        "name": VERDICT_TOOL_NAME,
        "description": "Record this patrol round's structured risk verdict for one IP.",
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "ip": {"type": "string"},
                    "risk_level": {"type": "string", "enum": list(RISK_LEVELS)},
                    "attack_type": {
                        "type": "string",
                        "description": "e.g. sqli, xss, idor, bruteforce, phishing, scan, none",
                    },
                    "reasoning": {
                        "type": "string",
                        "description": (
                            "1-3 sentence explanation. Reference agent_episodes history "
                            "explicitly if it influenced the verdict."
                        ),
                    },
                    "action": {
                        "type": "object",
                        "description": "Required and meaningful only when risk_level is 'high'.",
                        "properties": {
                            "type": {"type": "string", "enum": list(ACTION_TYPES)},
                            "block_hours": {
                                "type": "number",
                                "description": "For blacklist_temporary; hours to block.",
                            },
                            "limit_per_min": {
                                "type": "integer",
                                "description": "For rate_limit; requests per minute to allow.",
                            },
                            "user_id": {
                                "type": "string",
                                "description": "For lock_account; the account to lock.",
                            },
                            "task_note": {
                                "type": "string",
                                "description": "For task_queue; a hardening suggestion.",
                            },
                        },
                        "required": ["type"],
                    },
                },
                "required": ["ip", "risk_level", "attack_type", "reasoning"],
            }
        },
    }
}


def build_messages(*, ip, logs, similar_attacks, ip_history):
    lines = [f"# Patrol round for IP {ip}", "", "## Recent request_logs for this IP"]
    for row in logs:
        lines.append(_format_log_row(row))

    lines.append("")
    lines.append("## Semantically recalled attack_signatures (CockroachDB vector search)")
    if similar_attacks:
        for row in similar_attacks:
            lines.append(
                f"- [{row.get('category')}/{row.get('severity')}] {row.get('description')} "
                f"(distance={row.get('distance')})"
            )
    else:
        lines.append("- none recalled")

    lines.append("")
    lines.append("## agent_episodes history for this IP (your own past verdicts)")
    if ip_history:
        for row in ip_history:
            lines.append(
                f"- {row.get('ts')}: risk_level={row.get('risk_level')} "
                f"attack_type={row.get('attack_type')} action_taken={row.get('action_taken')} "
                f"-- {row.get('reasoning_summary')}"
            )
    else:
        lines.append("- none -- first time this agent has seen this IP")

    return [{"role": "user", "content": [{"text": "\n".join(lines)}]}]


def _format_log_row(row):
    return (
        f"- {row.get('ts')} {row.get('method')} {row.get('path')} "
        f"query={row.get('query_params')!r} body={row.get('body_snippet')!r} "
        f"status={row.get('status_code')} user_id={row.get('user_id')} ua={row.get('user_agent')!r}"
    )
