"""POST/GET /comments -- no content filtering, on purpose.

Backs the encoded-XSS and social-engineering-text attack scenarios: any text
is accepted and echoed back verbatim. Storage is in-process (module-level
list) since PRD-01's schema has no comments table -- the demo only needs the
request to happen and land in request_logs, not to persist across cold
starts.
"""
from .. import http
from ..interfaces import Repository
from ..middleware import gated, logged

_COMMENTS = []


@logged
@gated
def handle(event, context, repo: Repository):
    method = event.get("httpMethod", "GET")

    if method == "POST":
        body = http.parse_json_body(event)
        text = body.get("text", "")
        if not text:
            return http.json_response(400, {"error": "text required"})
        _COMMENTS.append(text)
        return http.json_response(201, {"stored": True, "count": len(_COMMENTS)})

    return http.json_response(200, {"comments": list(_COMMENTS)})
