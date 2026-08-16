"""GET /admin -- exists, answers, has no auth in front of it.

Bait for the scan/probe attack scenario: an attacker walking common admin
paths gets a real 200 instead of a 404, which is itself the signal the
patrol agent should pick up on from request_logs.
"""
from .. import http
from ..interfaces import Repository
from ..middleware import gated, logged


@logged
@gated
def handle(event, context, repo: Repository):
    return http.json_response(200, {
        "panel": "cr-sentinel-demo-admin",
        "status": "ok",
    })
