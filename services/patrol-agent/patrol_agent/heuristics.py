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


def flag_suspicious_ips(logs, *, high_frequency_threshold=HIGH_FREQUENCY_THRESHOLD):
    """Group logs by src_ip, keep only IPs with a frequency spike or at
    least one row that looks attack-shaped. Returns {ip: [rows]}."""
    by_ip = defaultdict(list)
    for row in logs:
        ip = row.get("src_ip")
        if ip:
            by_ip[ip].append(row)

    suspicious = {}
    for ip, rows in by_ip.items():
        if len(rows) >= high_frequency_threshold or any(_row_looks_suspicious(row) for row in rows):
            suspicious[ip] = rows
    return suspicious


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
