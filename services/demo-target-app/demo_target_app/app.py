"""Lambda entry points. One function per route, each a thin wrapper that
resolves a repository and delegates to the matching handler in handlers/.

Kept as separate entry points (rather than one router Lambda) so each route
gets its own SAM function / IAM scoping, and so a change to one endpoint's
code doesn't redeploy the others.
"""
from .db import CockroachRepository
from .handlers import admin, comments, login, profile
from .interfaces import Repository

_repo: Repository = None


def _get_repo() -> Repository:
    global _repo
    if _repo is None:
        _repo = CockroachRepository.connect()
    return _repo


def login_handler(event, context):
    return login.handle(event, context, _get_repo())


def profile_handler(event, context):
    return profile.handle(event, context, _get_repo())


def comments_handler(event, context):
    return comments.handle(event, context, _get_repo())


def admin_handler(event, context):
    return admin.handle(event, context, _get_repo())
