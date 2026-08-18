"""Cheap pre-filter over a window's `request_logs` so PatrolAgentLambda
doesn't spend a Titan embedding call plus a Bedrock Claude call on every IP
that showed up, only on the ones with some surface-level signal (PRD-04
functional requirement 2: "对可疑请求...做向量语义检索").

Deliberately coarse -- status code, a few attack-shaped characters,
request frequency -- and not a replacement for Claude's semantic judgment.
rawmaterial.txt's whole premise is that regex/threshold matching alone
misses obfuscated and novel attacks; this module only decides *which* IPs
are worth spending a Bedrock call on this round, it doesn't render a
verdict.
"""
import re
from collections import defaultdict

SUSPICIOUS_STATUS_CODES = {401, 403, 404, 500, 502, 503}
SUSPICIOUS_PATTERN = re.compile(
    r"['\"<>;()]|--|/\*|\bunion\b|\bselect\b|<script|onerror=|javascript:|\.\./",
    re.IGNORECASE,
)
HIGH_FREQUENCY_THRESHOLD = 20
EMBEDDING_TEXT_FIELDS = ("method", "path", "query_params", "body_snippet")
MAX_ROWS_FOR_EMBEDDING = 10

# PRD-04's chained-intrusion stretch goal ("跨请求链式入侵关联分析"): recon
# (/admin) -> weak-credential login -> IDOR data access -> renewed recon can
# have every individual row look clean (200s, no attack-shaped characters,
# under the frequency threshold) and still be a real intrusion -- the
# attack only exists in *which distinct endpoints* one IP touched, not in
# any single request. See docs/prd/PRD-02-demo-target-app.md for why these
# three specifically are the sensitive ones.
CHAIN_SENSITIVE_PATHS = {"/admin", "/login", "/profile"}
MIN_DISTINCT_SENSITIVE_PATHS_FOR_CHAIN = 3


def flag_suspicious_ips(logs, *, high_frequency_threshold=HIGH_FREQUENCY_THRESHOLD):
    """Group logs by src_ip, keep only IPs with a frequency spike, at
    least one row that looks attack-shaped, or a chained-intrusion-shaped
    spread across sensitive endpoints. Returns {ip: [rows]}."""
    by_ip = defaultdict(list)
    for row in logs:
        ip = row.get("src_ip")
        if ip:
            by_ip[ip].append(row)

    suspicious = {}
    for ip, rows in by_ip.items():
        if (
            len(rows) >= high_frequency_threshold
            or any(_row_looks_suspicious(row) for row in rows)
            or _touches_multiple_sensitive_paths(rows)
        ):
            suspicious[ip] = rows
    return suspicious


def summarize_endpoint_diversity(rows):
    """The ordered sequence of paths one IP touched this round, e.g.
    "/admin -> /login -> /profile -> /profile -> /admin" -- surfaced
    directly in the prompt (prompt_builder.py) so Claude's reasoning can
    reference the *sequence* of a chained intrusion explicitly, not just
    infer it from the raw row list."""
    return " -> ".join(row.get("path") or "?" for row in rows)


def _touches_multiple_sensitive_paths(rows):
    touched = {row.get("path") for row in rows}
    return len(touched & CHAIN_SENSITIVE_PATHS) >= MIN_DISTINCT_SENSITIVE_PATHS_FOR_CHAIN


def summarize_for_embedding(rows, *, max_rows=MAX_ROWS_FOR_EMBEDDING):
    """Flatten an IP's suspicious rows into one string to embed for
    semantic recall against attack_signatures -- the vector search wants a
    short attack-shaped description, not the raw log rows."""
    parts = [_row_text(row) for row in rows[:max_rows]]
    parts = [p for p in parts if p]
    return " | ".join(parts) or "no request detail"


def _row_looks_suspicious(row):
    if row.get("status_code") in SUSPICIOUS_STATUS_CODES:
        return True
    return bool(SUSPICIOUS_PATTERN.search(_row_text(row)))


def _row_text(row):
    return " ".join(str(row.get(field) or "") for field in EMBEDDING_TEXT_FIELDS)
