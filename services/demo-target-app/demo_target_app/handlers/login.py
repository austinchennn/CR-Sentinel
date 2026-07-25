"""POST /login -- deliberately weak auth for the brute-force attack scenario.

No rate limiting or lockout-on-repeated-failure happens here; that is the
patrol agent's job (PRD-04/05) once it sees a pattern in request_logs. This
handler only checks credentials and respects a lock already placed by that
downstream process.
"""
from .. import http
from ..middleware import logged
from ..seed_accounts import WEAK_CREDENTIALS


@logged
def handle(event, context, repo):
    body = http.parse_json_body(event)
    username = body.get("username", "")
    password = body.get("password", "")

    if not username or not password:
        return http.json_response(400, {"error": "username and password required"})

    account = repo.get_account_by_username(username)
    if account is None:
        return http.json_response(401, {"error": "invalid credentials"})

    event["_resolved_user_id"] = account["user_id"]

    if account["locked"]:
        return http.json_response(403, {"error": "account locked", "reason": account["locked_reason"]})

    if WEAK_CREDENTIALS.get(username) != password:
        return http.json_response(401, {"error": "invalid credentials"})

    return http.json_response(200, {"user_id": account["user_id"], "username": username})
