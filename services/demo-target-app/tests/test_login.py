from conftest import make_event

from demo_target_app.handlers import login


def test_valid_login_succeeds(repo):
    event = make_event("POST", "/login", body={"username": "alice", "password": "alice123"})
    resp = login.handle(event, {}, repo)
    assert resp["statusCode"] == 200


def test_wrong_password_rejected(repo):
    event = make_event("POST", "/login", body={"username": "alice", "password": "wrong"})
    resp = login.handle(event, {}, repo)
    assert resp["statusCode"] == 401


def test_unknown_user_rejected(repo):
    event = make_event("POST", "/login", body={"username": "ghost", "password": "x"})
    resp = login.handle(event, {}, repo)
    assert resp["statusCode"] == 401


def test_locked_account_rejected_even_with_right_password(repo):
    repo.lock_account("u-1002", "brute force detected")
    event = make_event("POST", "/login", body={"username": "bob", "password": "password"})
    resp = login.handle(event, {}, repo)
    assert resp["statusCode"] == 403


def test_every_attempt_is_logged(repo):
    event = make_event("POST", "/login", body={"username": "alice", "password": "wrong"})
    login.handle(event, {}, repo)
    assert len(repo.request_logs) == 1
    assert repo.request_logs[0]["status_code"] == 401
