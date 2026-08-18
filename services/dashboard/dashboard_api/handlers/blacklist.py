"""GET /blacklist -- currently-active ip_blacklist and ip_rate_limit
entries, i.e. what the demo-target-app gateway (PRD-05's `gated`
middleware) is actually enforcing right now (PRD-07 functional
requirement 2: "展示 ip_blacklist/ip_rate_limit 当前生效记录，实时反映处置结果").
Both come back in one response since they're one dashboard view."""
from .. import http
from ..interfaces import Repository


def handle(event, context, repo: Repository):
    return http.json_response(200, {
        "blacklist": repo.active_blacklist(),
        "rate_limits": repo.active_rate_limits(),
    })
