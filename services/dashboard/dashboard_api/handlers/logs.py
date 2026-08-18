"""GET /logs?ip=&status_code=&limit= -- recent request_logs, optionally
filtered by source IP and/or status code (PRD-07 functional requirement
1: "展示最近 request_logs，可按 IP/状态码筛选")."""
from .. import http
from ..interfaces import Repository


def handle(event, context, repo: Repository):
    params = http.query_params(event)

    ip = params.get("ip") or None
    raw_status_code = params.get("status_code")
    if raw_status_code:
        try:
            status_code = int(raw_status_code)
        except ValueError:
            return http.json_response(400, {"error": "status_code must be an integer"})
    else:
        status_code = None

    try:
        limit = int(params.get("limit", 100))
    except ValueError:
        return http.json_response(400, {"error": "limit must be an integer"})

    rows = repo.recent_logs(limit=limit, ip=ip, status_code=status_code)
    return http.json_response(200, {"logs": rows})
