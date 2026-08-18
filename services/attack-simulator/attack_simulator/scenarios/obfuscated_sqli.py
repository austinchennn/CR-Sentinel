"""Scenario 1 (PRD-08): encoded/obfuscated SQL injection variants sent to
GET /profile?id=... . demo-target-app has no real SQL execution behind
`id` (db.py does a plain key lookup, see docs/prd/PRD-02) -- this isn't
exploiting a real injection. The point is testing whether the patrol
agent recognizes the *semantic shape* of these payloads (via Bedrock +
vector recall against attack_signatures), not whether heuristics.py's
regex keyword-matches them: PRD-08 scenario 1 frames this as "展示 AI 识别
底层语义而非关键词匹配" -- a WAF that only matches the plain-text variant
would miss the other three.
"""
import time

from .base import ScenarioResult

NAME = "obfuscated_sqli"
EXPECTED_RISK_LEVEL = "high"
EXPECTED_ATTACK_TYPE = "sqli"

PAYLOADS = [
    "1' UNION SELECT username,password FROM accounts--",
    "1' uNiOn/**/sElEcT username,password FROM accounts--",
    "1%27%20UNION%20SELECT%20username%2Cpassword%20FROM%20accounts--",
    "1'/**/UNION/**/SELECT/**/username,password/**/FROM/**/accounts--",
]


def run(client, *, sleep_fn=time.sleep, delay_seconds=0.2):
    print(f"[{NAME}] sending {len(PAYLOADS)} obfuscated SQLi variants to GET /profile?id=...")
    for i, payload in enumerate(PAYLOADS, start=1):
        resp = client.get("/profile", params={"id": payload})
        print(f"  [{i}/{len(PAYLOADS)}] id={payload!r} -> {resp.status_code}")
        sleep_fn(delay_seconds)

    return ScenarioResult(
        name=NAME,
        requests_sent=len(PAYLOADS),
        expected_risk_level=EXPECTED_RISK_LEVEL,
        expected_attack_type=EXPECTED_ATTACK_TYPE,
        narrative=(
            "Same UNION SELECT intent sent 4 different ways (plain, case-mixed, "
            "URL-encoded, /**/-split). A keyword/regex WAF needs one rule per "
            "variant; the patrol agent should recognize all 4 as the same attack "
            "via semantic embedding recall against attack_signatures, not string "
            "matching."
        ),
    )
