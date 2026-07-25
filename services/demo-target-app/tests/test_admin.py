from conftest import make_event

from demo_target_app.handlers import admin


def test_admin_path_answers_with_no_auth_check(repo):
    event = make_event("GET", "/admin")
    resp = admin.handle(event, {}, repo)
    assert resp["statusCode"] == 200


def test_admin_hit_is_logged_for_the_patrol_agent_to_see(repo):
    admin.handle(make_event("GET", "/admin"), {}, repo)
    assert len(repo.request_logs) == 1
    assert repo.request_logs[0]["path"] == "/admin"
