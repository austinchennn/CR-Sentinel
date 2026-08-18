"""GET /episodes?ip=&limit= -- one IP's agent_episodes history in
chronological order (PRD-07 functional requirement 3, the core view):
"按 IP 展示 agent_episodes 的时间序列...清晰展示'第一轮记录为可疑 → 第二轮结合历史
记忆升级为高危 → 处置'这个演化过程". Ordered oldest-first (db.py's
episodes_for_ip) so the frontend can render it as a left-to-right/top-to-
bottom timeline without re-sorting."""
from .. import http
from ..interfaces import Repository


def handle(event, context, repo: Repository):
    params = http.query_params(event)
    ip = params.get("ip")
    if not ip:
        return http.json_response(400, {"error": "ip query param required"})

    try:
        limit = int(params.get("limit", 50))
    except ValueError:
        return http.json_response(400, {"error": "limit must be an integer"})

    episodes = repo.episodes_for_ip(ip, limit=limit)
    return http.json_response(200, {"ip": ip, "episodes": episodes})
