"""Safe SQL literal formatting for the MCP read-only tool.

The CockroachDB Cloud MCP server's read-only tool takes a single SQL
string (see README's note on `select_query`), not bind parameters like a
DB-API cursor. Values that can be attacker-influenced -- most notably
`src_ip`, which is read back out of request_logs and could contain a
spoofed X-Forwarded-For value -- still have to go through this client, so
they're quoted here rather than f-string'd directly into the query.
"""


def quote_string(value):
    escaped = value.replace("'", "''")
    return f"'{escaped}'"


def quote_vector(embedding):
    if not embedding:
        raise ValueError("embedding must be a non-empty sequence of floats")
    values = ", ".join(repr(float(x)) for x in embedding)
    return f"'[{values}]'"


def quote_int(value):
    return str(int(value))
