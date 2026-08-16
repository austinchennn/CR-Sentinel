"""Request-entry decorators shared by every handler.

`logged` wraps a handler so every request -- success or failure -- lands a
row in request_logs; that's the only place request logging happens.

`gated` is PRD-05's execution-interception layer: the "毫秒级基础防护" that
compensates for the patrol agent's 5-minute batch latency (docs/01-architecture.md
section 2.5). It reads `ip_blacklist`/`ip_rate_limit` directly (not via MCP --
see PRD-05's "独立的只读路径，不占用 MCP 配额") and short-circuits before the
handler runs. Compose it inside `@logged` (`@logged` outermost, `@gated`
innermost) so blocked attempts still get a request_logs row for the patrol
agent to see, the same as any other request.
"""
import time

from . import http

RATE_LIMIT_WINDOW_SECONDS = 60


def logged(handler):
    def wrapped(event, context, repo):
        start = time.monotonic()
        try:
            response = handler(event, context, repo)
        except Exception:
            response = http.json_response(500, {"error": "internal_error"})
            raise
        finally:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            body = http.parse_json_body(event)
            repo.log_request(
                src_ip=http.source_ip(event),
                method=event.get("httpMethod", "UNKNOWN"),
                path=event.get("path", ""),
                query_params=str(http.query_params(event)),
                body_snippet=str(body)[:500],
                user_agent=http.user_agent(event),
                status_code=response.get("statusCode", 0) if isinstance(response, dict) else 0,
                user_id=event.get("_resolved_user_id"),
                response_time_ms=elapsed_ms,
            )
        return response

    return wrapped


def gated(handler):
    def wrapped(event, context, repo):
        ip = http.source_ip(event)

        if repo.is_ip_blacklisted(ip):
            return http.json_response(403, {"error": "ip_blacklisted"})

        limit_per_min = repo.get_active_rate_limit(ip)
        if limit_per_min is not None:
            recent = repo.count_recent_requests(ip, window_seconds=RATE_LIMIT_WINDOW_SECONDS)
            if recent >= limit_per_min:
                return http.json_response(429, {"error": "rate_limited"})

        return handler(event, context, repo)

    return wrapped
