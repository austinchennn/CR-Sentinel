"""Scenario 2 (PRD-08): slow-paced ("温水煮青蛙") brute force against
POST /login. Spread out so a naive fixed-window rate limiter (like
demo-target-app's own gateway-layer PRD-05 rate limit, tuned for
requests/minute) wouldn't trigger on its own -- the patrol agent has to
recognize the pattern by intent across a window (repeated failed logins
for one username from one IP), not a single-request threshold.

Default delay is short so this stays runnable as a live demo within a
few-minute patrol window; pass a larger --delay-seconds via the CLI for a
more realistic slow-burn timeline.
"""
import time

from .base import ScenarioResult

NAME = "slow_bruteforce"
EXPECTED_RISK_LEVEL = "high"
EXPECTED_ATTACK_TYPE = "bruteforce"

USERNAME = "alice"
GUESSED_PASSWORDS = ["alice1", "alice2024", "alicepass", "qwerty123", "letmein", "alice123!"]


def run(client, *, sleep_fn=time.sleep, delay_seconds=5):
    print(
        f"[{NAME}] trying {len(GUESSED_PASSWORDS)} passwords for {USERNAME!r} "
        f"against POST /login, {delay_seconds}s apart"
    )
    for i, password in enumerate(GUESSED_PASSWORDS, start=1):
        resp = client.post("/login", json_body={"username": USERNAME, "password": password})
        print(f"  [{i}/{len(GUESSED_PASSWORDS)}] password={password!r} -> {resp.status_code}")
        if i < len(GUESSED_PASSWORDS):
            sleep_fn(delay_seconds)

    return ScenarioResult(
        name=NAME,
        requests_sent=len(GUESSED_PASSWORDS),
        expected_risk_level=EXPECTED_RISK_LEVEL,
        expected_attack_type=EXPECTED_ATTACK_TYPE,
        narrative=(
            f"{len(GUESSED_PASSWORDS)} failed logins for the same username, spaced "
            f"{delay_seconds}s apart -- slow enough to stay under a fixed "
            "request-count threshold in one patrol window, but the pattern across "
            "windows (via agent_episodes recall) should still read as brute force."
        ),
    )
