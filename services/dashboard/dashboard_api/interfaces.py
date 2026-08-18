"""Structural (`typing.Protocol`) interface for the dashboard's `repo`
parameter, matching the convention `patrol_agent`/`demo_target_app`
already use (see their own `interfaces.py`). Documentation/type-checker
aid only: `DashboardRepository` (db.py) and tests' fakes already satisfy
this without inheriting from it.
"""
from typing import Optional, Protocol


class Repository(Protocol):
    def recent_logs(self, *, limit: int = 100, ip: Optional[str] = None, status_code: Optional[int] = None) -> list: ...

    def active_blacklist(self) -> list: ...

    def active_rate_limits(self) -> list: ...

    def episodes_for_ip(self, ip: str, *, limit: int = 50) -> list: ...
