import pytest
from conftest import make_event

from demo_target_app.handlers import comments


@pytest.fixture(autouse=True)
def reset_comments():
    comments._COMMENTS.clear()
    yield
    comments._COMMENTS.clear()


def test_arbitrary_text_is_accepted_unfiltered(repo):
    payload = "<script>alert(document.cookie)</script>"
    event = make_event("POST", "/comments", body={"text": payload})
    resp = comments.handle(event, {}, repo)
    assert resp["statusCode"] == 201

    listing = comments.handle(make_event("GET", "/comments"), {}, repo)
    assert payload in listing["body"]


def test_missing_text_is_a_400(repo):
    event = make_event("POST", "/comments", body={})
    resp = comments.handle(event, {}, repo)
    assert resp["statusCode"] == 400
