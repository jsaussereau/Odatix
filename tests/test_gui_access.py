"""Tests for the access control of the GUI: token, cookie and Host header."""

import pytest

pytestmark = pytest.mark.gui

flask = pytest.importorskip("flask")

from odatix.gui.access import AccessGuard


@pytest.fixture
def client():
    app = flask.Flask(__name__)
    app.add_url_rule("/page", "page", lambda: "content")
    AccessGuard(token="secret", port=8050, allowed_hosts={"localhost", "127.0.0.1"}).install(app)
    return app.test_client()


def test_without_token_nothing_is_served(client):
    response = client.get("/page", headers={"Host": "localhost:8050"})
    assert response.status_code == 401
    assert b"content" not in response.data


def test_the_token_is_traded_for_a_cookie(client):
    response = client.get("/page?token=secret&x=1", headers={"Host": "localhost:8050"})
    # Not an HTTP redirect: a cross-site visit would not send the Strict cookie
    # along it. The page goes on to the address without the token.
    assert response.status_code == 200
    assert b'location.replace("/page?x=1")' in response.data
    cookie = response.headers["Set-Cookie"]
    assert "odatix_gui_8050=secret" in cookie and "HttpOnly" in cookie and "SameSite=Strict" in cookie
    assert client.get("/page", headers={"Host": "localhost:8050"}).data == b"content"


def test_a_wrong_token_is_refused(client):
    assert client.get("/page?token=guess", headers={"Host": "localhost:8050"}).status_code == 401
    client.set_cookie("odatix_gui_8050", "guess") if _new_set_cookie() else client.set_cookie("localhost", "odatix_gui_8050", "guess")
    assert client.get("/page", headers={"Host": "localhost:8050"}).status_code == 401


def test_an_unknown_host_is_refused_even_with_the_token(client):
    response = client.get("/page?token=secret", headers={"Host": "evil.example:8050"})
    assert response.status_code == 403


def test_url_suffix():
    guard = AccessGuard(token="t", port=1)
    assert guard.url_suffix("/") == "/?token=t"
    assert guard.url_suffix("/a?b=1") == "/a?b=1&token=t"


def _new_set_cookie():
    import inspect
    from werkzeug.test import Client
    return list(inspect.signature(Client.set_cookie).parameters)[1] == "key"


def test_every_answer_carries_the_security_headers(client):
    for response in (client.get("/page", headers={"Host": "localhost:8050"}),
                     client.get("/page?token=secret", headers={"Host": "localhost:8050"})):
        assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
        assert response.headers["Referrer-Policy"] == "no-referrer"
        assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_the_browser_is_opened_on_a_private_redirect_file():
    import os
    import stat
    from urllib.request import url2pathname
    from odatix.gui.access import launch_url
    url = launch_url("http://127.0.0.1:1/?token=t</script>")
    assert url.startswith("file:")
    path = url2pathname(url[len("file:"):])
    try:
        if os.name != "nt":
            assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
        text = open(path, encoding="utf-8").read()
        assert "token=t" in text and "</script>\")" not in text
    finally:
        os.remove(path)


def test_a_name_starting_like_a_loopback_address_is_not_one():
    guard = AccessGuard(token="t", port=1, allowed_hosts=set())
    assert guard.host_allowed("127.0.0.2:8050") and guard.host_allowed("[::1]:8050")
    assert not guard.host_allowed("127.evil.example:8050")
