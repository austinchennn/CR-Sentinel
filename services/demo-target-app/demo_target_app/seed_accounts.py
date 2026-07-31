"""Seed data for the demo target app.

Deliberately weak credentials -- this is the attack surface, not a bug.
`accounts` rows go into CockroachDB (schema: PRD-01); credentials stay in
this in-process map because the `accounts` table (per PRD-01) has no
password column -- the demo app is not meant to model a real auth system.
"""

SEED_ACCOUNTS = [
    {"user_id": "u-1001", "username": "alice", "locked": False, "locked_reason": None},
    {"user_id": "u-1002", "username": "bob", "locked": False, "locked_reason": None},
    {"user_id": "u-1003", "username": "admin", "locked": False, "locked_reason": None},
]

# Intentionally weak, for the brute-force attack scenario in the demo script.
WEAK_CREDENTIALS = {
    "alice": "alice123",
    "bob": "password",
    "admin": "admin123",
}


def seed(repo):
    for account in SEED_ACCOUNTS:
        repo.upsert_account(**account)


if __name__ == "__main__":
    from demo_target_app.db import CockroachRepository

    seed(CockroachRepository.connect())
    print(f"seeded {len(SEED_ACCOUNTS)} accounts")
