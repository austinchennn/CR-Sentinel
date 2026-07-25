"""Wraps a handler so every request -- success or failure -- lands a row in
request_logs. This is the only place request logging happens; individual
handlers just return a response."""
import time

from . import http


def logged(handler):
    def wrapped(event, context, repo):
        start = time.monotonic()
        body = http.parse_json_body(event)
        try:
            response = handler(event, context, repo)
        except Exception:
            response = http.json_response(500, {"error": "internal_error"})
            raise
        finally:
            elapsed_ms = int((time.monotonic() - start) * 1000)
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
