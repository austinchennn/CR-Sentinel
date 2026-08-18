"""Lambda entry points for the dashboard's read-only API (PRD-07). One
function per route, same pattern as `demo_target_app/app.py`."""
from .db import DashboardRepository
from .handlers import blacklist, episodes, logs

_repo = None


def _get_repo():
    global _repo
    if _repo is None:
        _repo = DashboardRepository.connect()
    return _repo


def logs_handler(event, context):
    return logs.handle(event, context, _get_repo())


def blacklist_handler(event, context):
    return blacklist.handle(event, context, _get_repo())


def episodes_handler(event, context):
    return episodes.handle(event, context, _get_repo())
