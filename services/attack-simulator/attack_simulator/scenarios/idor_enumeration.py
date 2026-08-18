"""Scenario 3 (PRD-08): IDOR/enumeration -- purely syntactically valid
requests (no special characters at all), sequential `id` values against
GET /profile. Nothing here would trip a signature/regex-based WAF, which
is the point: the patrol agent has to reason about the *pattern of
access* (one IP walking through many different user_ids in a row), not
payload shape.
"""
import time

from .base import ScenarioResult

NAME = "idor_enumeration"
EXPECTED_RISK_LEVEL = "high"
EXPECTED_ATTACK_TYPE = "idor"

USER_IDS = [f"u-{n}" for n in range(1000, 1010)]


def run(client, *, sleep_fn=time.sleep, delay_seconds=0.3):
    print(f"[{NAME}] walking {len(USER_IDS)} sequential ids against GET /profile?id=...")
    for i, user_id in enumerate(USER_IDS, start=1):
        resp = client.get("/profile", params={"id": user_id})
        print(f"  [{i}/{len(USER_IDS)}] id={user_id} -> {resp.status_code}")
        sleep_fn(delay_seconds)

    return ScenarioResult(
        name=NAME,
        requests_sent=len(USER_IDS),
        expected_risk_level=EXPECTED_RISK_LEVEL,
        expected_attack_type=EXPECTED_ATTACK_TYPE,
        narrative=(
            "Every request here is syntactically normal -- no injection payload, "
            "no malformed input. A signature-based WAF sees nothing wrong with any "
            "single request; the attack only exists in the *sequence*, one IP "
            "reading many different users' profiles in a row."
        ),
    )
