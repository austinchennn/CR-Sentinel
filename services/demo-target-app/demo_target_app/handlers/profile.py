"""GET /profile?id=<user_id> -- intentional IDOR.

Returns whatever account the `id` query param points to, with no check that
the caller is actually that user. This is the vulnerability the IDOR attack
script (docs/prd/PRD-08) walks: request /profile?id=u-1001, then
/profile?id=u-1002, and read data that isn't yours.
"""
from .. import http
from ..middleware import logged


@logged
def handle(event, context, repo):
    user_id = http.query_params(event).get("id")
    if not user_id:
        return http.json_response(400, {"error": "id query param required"})

    account = repo.get_account_by_user_id(user_id)
    if account is None:
        return http.json_response(404, {"error": "not found"})

    return http.json_response(200, account)
