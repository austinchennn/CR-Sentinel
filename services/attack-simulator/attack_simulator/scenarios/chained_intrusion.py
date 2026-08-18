"""Scenario 4 (PRD-08): chained intrusion -- probe -> weak-credential
login -> IDOR read -> admin re-scan, run as one continuous sequence from a
single IP. Each individual request looks like ordinary (if slightly odd)
traffic on its own; only the sequence across all four steps tells the
real story -- this is the scenario PRD-04's system prompt already asks
Claude to weigh agent_episodes history for ("a second suspicious round
from an IP you already flagged should usually escalate").
"""
import time

from .base import ScenarioResult

NAME = "chained_intrusion"
EXPECTED_RISK_LEVEL = "high"
EXPECTED_ATTACK_TYPE = "chained_intrusion"

LOGIN_USERNAME = "bob"
LOGIN_PASSWORD = "password"
IDOR_TARGET_IDS = ("u-1001", "u-1003")


def run(client, *, sleep_fn=time.sleep, delay_seconds=1):
    print(f"[{NAME}] step 1/4: probing GET /admin")
    resp = client.get("/admin")
    print(f"  -> {resp.status_code}")
    sleep_fn(delay_seconds)

    print(f"[{NAME}] step 2/4: weak-credential login on POST /login ({LOGIN_USERNAME!r})")
    resp = client.post("/login", json_body={"username": LOGIN_USERNAME, "password": LOGIN_PASSWORD})
    print(f"  -> {resp.status_code}")
    sleep_fn(delay_seconds)

    print(f"[{NAME}] step 3/4: IDOR read of other accounts via GET /profile")
    for user_id in IDOR_TARGET_IDS:
        resp = client.get("/profile", params={"id": user_id})
        print(f"  id={user_id} -> {resp.status_code}")
        sleep_fn(delay_seconds)

    print(f"[{NAME}] step 4/4: re-probing GET /admin after the walk")
    resp = client.get("/admin")
    print(f"  -> {resp.status_code}")

    requests_sent = 2 + len(IDOR_TARGET_IDS) + 1
    return ScenarioResult(
        name=NAME,
        requests_sent=requests_sent,
        expected_risk_level=EXPECTED_RISK_LEVEL,
        expected_attack_type=EXPECTED_ATTACK_TYPE,
        narrative=(
            "Recon (/admin probe) -> a successful weak-credential login -> IDOR "
            "reads of accounts that aren't the logged-in user -> a second /admin "
            "probe. Each step alone looks like normal-ish traffic from one IP; the "
            "chain across all four is what should read as an intrusion."
        ),
    )
