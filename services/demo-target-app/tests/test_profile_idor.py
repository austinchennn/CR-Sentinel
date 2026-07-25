from conftest import make_event

from demo_target_app.handlers import profile


def test_can_read_any_users_profile_by_id(repo):
    event = make_event("GET", "/profile", query={"id": "u-1002"})
    resp = profile.handle(event, {}, repo)
    assert resp["statusCode"] == 200
    assert '"username": "bob"' in resp["body"]


def test_switching_id_returns_a_different_user(repo):
    event_a = make_event("GET", "/profile", query={"id": "u-1001"})
    event_b = make_event("GET", "/profile", query={"id": "u-1002"})
    resp_a = profile.handle(event_a, {}, repo)
    resp_b = profile.handle(event_b, {}, repo)
    assert resp_a["body"] != resp_b["body"]


def test_missing_id_is_a_400(repo):
    event = make_event("GET", "/profile", query={})
    resp = profile.handle(event, {}, repo)
    assert resp["statusCode"] == 400


def test_unknown_id_is_a_404(repo):
    event = make_event("GET", "/profile", query={"id": "u-9999"})
    resp = profile.handle(event, {}, repo)
    assert resp["statusCode"] == 404
