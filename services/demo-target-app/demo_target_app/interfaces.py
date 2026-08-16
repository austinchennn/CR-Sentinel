"""Structural (`typing.Protocol`) interface for demo_target_app's request
handlers and middleware -- the `repo` parameter every handler
(handlers/*.py) and middleware decorator (middleware.py) receive rather
than construct themselves, wired at the composition root in `app.py`'s
`_get_repo`.

Documentation and type-checker aid only, not a runtime contract:
`CockroachRepository` (db.py) and tests' `FakeRepository`
(tests/conftest.py) already satisfy this structurally without inheriting
from it or importing this module.
"""
from typing import Optional, Protocol


class Repository(Protocol):
    def log_request(
        self, *, src_ip, method, path, query_params="", body_snippet="",
        user_agent="", status_code=200, user_id=None, response_time_ms=0,
    ) -> None: ...

    def get_account_by_user_id(self, user_id) -> Optional[dict]: ...

    def get_account_by_username(self, username) -> Optional[dict]: ...

    def lock_account(self, user_id, reason) -> None: ...

    def upsert_account(self, user_id, username, locked=False, locked_reason=None) -> None: ...

    def is_ip_blacklisted(self, ip) -> bool: ...

    def get_active_rate_limit(self, ip) -> Optional[int]: ...

    def count_recent_requests(self, ip, window_seconds=60) -> int: ...
