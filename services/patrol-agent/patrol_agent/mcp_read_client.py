"""Read-only MCP channel: log tail, semantic recall, and per-IP episodic
memory (PRD-03 functional requirements 2-4).

The `mcp` SDK is only imported inside `_default_session_factory`, not at
module load time, so this module -- and anything that imports it -- stays
importable without the `mcp` package installed. Same reasoning as
`demo_target_app/db.py` deferring its `psycopg2` import into `connect()`:
tests exercise the query-building and response-parsing logic against a
fake session and never need the real driver.

`select_query` is the tool name confirmed against the CockroachDB Cloud
Console-generated MCP config snippet (see README) -- the architecture
doc's earlier `run_read_query`/`vector_search` names were placeholders per
docs/01-architecture.md section 6, and have been corrected here. There is
no separate vector-search tool: semantic recall runs a normal `SELECT ...
ORDER BY embedding <-> $vec` query through the same read-only tool CRDB's
vector index accelerates it.
"""
import asyncio
import json
import logging

from . import sql_literals
from .errors import McpUnavailableError

logger = logging.getLogger(__name__)


class McpReadOnlyClient:
    def __init__(self, config, session_factory=None):
        self._config = config
        self._session_factory = session_factory or _default_session_factory

    def read_recent_logs(self, minutes=5):
        query = (
            "SELECT id, ts, src_ip, method, path, query_params, body_snippet, "
            "user_agent, status_code, user_id, response_time_ms FROM request_logs "
            f"WHERE ts > now() - INTERVAL '{sql_literals.quote_int(minutes)} minutes' "
            "ORDER BY ts"
        )
        return self._run_select(query)

    def semantic_search_attack_signatures(self, embedding, top_k=5):
        vector_literal = sql_literals.quote_vector(embedding)
        query = (
            "SELECT id, category, description, severity, "
            f"embedding <-> {vector_literal} AS distance FROM attack_signatures "
            f"ORDER BY embedding <-> {vector_literal} LIMIT {sql_literals.quote_int(top_k)}"
        )
        return self._run_select(query)

    def read_ip_episodes(self, ip, limit=20):
        query = (
            "SELECT id, ts, ip, risk_level, attack_type, reasoning_summary, action_taken "
            f"FROM agent_episodes WHERE ip = {sql_literals.quote_string(ip)} "
            f"ORDER BY ts DESC LIMIT {sql_literals.quote_int(limit)}"
        )
        return self._run_select(query)

    def _run_select(self, query):
        try:
            return asyncio.run(self._call_select_query(query))
        except McpUnavailableError:
            raise
        except Exception as exc:
            logger.warning("mcp_call_failed query=%r", query, exc_info=exc)
            raise McpUnavailableError(str(exc)) from exc

    async def _call_select_query(self, query):
        async with asyncio.timeout(self._config.timeout_seconds):
            async with self._session_factory(self._config) as session:
                result = await session.call_tool(
                    "select_query",
                    arguments={self._config.sql_arg_name: query},
                )
        if getattr(result, "isError", False):
            raise McpUnavailableError(_error_text(result))
        return _rows_from_tool_result(result)


def _default_session_factory(config):
    from contextlib import asynccontextmanager

    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    @asynccontextmanager
    async def factory():
        headers = {"Authorization": f"Bearer {config.api_key}"}
        async with streamablehttp_client(config.url, headers=headers) as (read, write, _get_session_id):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session

    return factory()


def _error_text(result):
    for block in getattr(result, "content", None) or []:
        text = getattr(block, "text", None)
        if text:
            return text
    return "MCP tool call returned an error with no content"


def _rows_from_tool_result(result):
    structured = getattr(result, "structuredContent", None)
    if structured:
        rows = structured.get("rows", structured)
        return rows if isinstance(rows, list) else [rows]
    for block in getattr(result, "content", None) or []:
        text = getattr(block, "text", None)
        if text:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed.get("rows", [parsed])
            return parsed
    return []
