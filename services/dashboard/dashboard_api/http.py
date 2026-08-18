"""Small helpers for working with API Gateway (REST API, proxy
integration) Lambda events. Deliberately duplicated from
`demo_target_app/http.py` rather than shared -- each `services/*`
directory deploys as its own independent Lambda (`CodeUri: .`), same
reasoning as `patrol_agent/embeddings.py` being a copy of
`crdb_schema/titan_embeddings.py`.

Unlike demo-target-app's version, responses here need
`Access-Control-Allow-Origin` -- the frontend is static-hosted on
CloudFront, a different origin from the API Gateway URL it calls, so
every response needs a CORS header or the browser drops it -- and
`json.dumps(..., default=str)`, since CRDB rows here carry
`TIMESTAMPTZ`/`datetime` values (`ts`, `block_until`, `expires_at`) that
aren't JSON-serializable by default.
"""
import json


def json_response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body, default=str),
    }


def query_params(event):
    return event.get("queryStringParameters") or {}
