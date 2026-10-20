"""Who is allowed to reach a daemon session, and to ask what of it.

Enqueuing a job runs a command line on the machine hosting the session, so
these are not cosmetic checks: every hole here is arbitrary code execution for
whoever can reach the socket or the port.
"""

import json
import os
import stat
import sys

import pytest

from odatix.lib.parallel_job_handler import auth as auth_module
from odatix.lib.parallel_job_handler import transport
from odatix.lib.parallel_job_handler.auth import ApiAuth, SCOPE_CONTROL, SCOPE_READ


def _headers(token=None, host="localhost"):
    headers = {"host": host}
    if token is not None:
        headers["authorization"] = "Bearer " + token
    return headers


@pytest.fixture
def api_auth():
    return ApiAuth(control_token="control-secret", read_token="read-secret", allowed_hosts={"localhost"})


class TestTokens:
    def test_a_request_without_a_token_is_refused(self, api_auth):
        status, _ = api_auth.authorize(_headers(), required_scope=SCOPE_READ)
        assert status == 401

    def test_a_wrong_token_is_refused(self, api_auth):
        status, _ = api_auth.authorize(_headers("guessed"), required_scope=SCOPE_READ)
        assert status == 401

    def test_the_control_token_may_act(self, api_auth):
        status, _ = api_auth.authorize(_headers("control-secret"), required_scope=SCOPE_CONTROL)
        assert status == 0

    def test_the_read_token_may_look_but_not_act(self, api_auth):
        assert api_auth.authorize(_headers("read-secret"), required_scope=SCOPE_READ)[0] == 0
        assert api_auth.authorize(_headers("read-secret"), required_scope=SCOPE_CONTROL)[0] == 403

    def test_a_bare_token_without_the_bearer_scheme_is_accepted(self, api_auth):
        headers = {"host": "localhost", "authorization": "control-secret"}
        assert api_auth.authorize(headers, required_scope=SCOPE_CONTROL)[0] == 0

    def test_generated_tokens_differ_from_each_other_and_between_sessions(self):
        first = ApiAuth.generate()
        second = ApiAuth.generate()
        tokens = {first.control_token, first.read_token, second.control_token, second.read_token}
        assert len(tokens) == 4
        assert all(len(t) >= 32 for t in tokens)


class TestHostHeader:
    """A browser can be made to POST to a loopback port; it cannot fake Host."""

    def test_an_unknown_host_header_is_refused_even_with_a_valid_token(self, api_auth):
        status, message = api_auth.authorize(_headers("control-secret", host="attacker.example"))
        assert status == 403
        assert "Host" in message

    def test_the_port_is_ignored_when_matching(self, api_auth):
        assert api_auth.authorize(_headers("control-secret", host="localhost:8000"))[0] == 0

    def test_ipv6_literals_are_matched_without_their_port(self):
        api_auth = ApiAuth("t", allowed_hosts={"[::1]"})
        assert api_auth.authorize(_headers("t", host="[::1]:8000"))[0] == 0

    def test_loopback_names_are_allowed_by_default(self):
        allowed = auth_module.default_allowed_hosts()
        assert "localhost" in allowed and "127.0.0.1" in allowed

    def test_the_check_can_be_opened_up_explicitly(self):
        api_auth = ApiAuth("t", allowed_hosts={"*"})
        assert api_auth.authorize(_headers("t", host="anything.example"))[0] == 0


class TestSecretFiles:
    def test_a_state_file_is_written_unreadable_to_others(self, tmp_path):
        path = tmp_path / "state.json"
        auth_module.write_secret_json(str(path), {"token": "secret"})

        assert json.loads(path.read_text(encoding="utf-8"))["token"] == "secret"
        if sys.platform != "win32":
            mode = stat.S_IMODE(os.stat(str(path)).st_mode)
            assert mode == 0o600, oct(mode)

    def test_writing_twice_leaves_no_temporary_file_behind(self, tmp_path):
        path = tmp_path / "state.json"
        auth_module.write_secret_json(str(path), {"a": 1})
        auth_module.write_secret_json(str(path), {"a": 2})

        assert json.loads(path.read_text(encoding="utf-8")) == {"a": 2}
        assert os.listdir(str(tmp_path)) == ["state.json"]

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX modes")
    def test_a_session_directory_is_private(self, tmp_path):
        path = tmp_path / "sessions"
        auth_module.secure_makedirs(str(path))
        assert stat.S_IMODE(os.stat(str(path)).st_mode) == 0o700


class TestEndpoints:
    def test_a_state_file_describes_a_unix_endpoint(self):
        endpoint = transport.Endpoint.from_state(
            {"transport": "unix", "socket_path": "/run/odatix/x.sock", "token": "t"}
        )
        assert endpoint.transport == "unix"
        assert endpoint.address == "unix:/run/odatix/x.sock"

    def test_a_state_file_describes_a_tcp_endpoint(self):
        endpoint = transport.Endpoint.from_state({"host": "127.0.0.1", "port": 8123, "token": "t"})
        assert endpoint.transport == "tcp"
        assert endpoint.address == "127.0.0.1:8123"

    def test_the_read_scope_picks_the_read_token(self):
        state = {"host": "h", "port": 1, "token": "control", "read_token": "read"}
        assert transport.Endpoint.from_state(state, scope=SCOPE_READ).token == "read"
        assert transport.Endpoint.from_state(state).token == "control"

    def test_a_token_can_come_from_the_environment(self, monkeypatch):
        monkeypatch.setenv("ODATIX_DAEMON_TOKEN", "from-env")
        assert transport.Endpoint.from_state({"host": "h", "port": 1}).token == "from-env"

    def test_a_unix_endpoint_without_a_socket_is_rejected(self):
        with pytest.raises(ValueError):
            transport.Endpoint(transport="unix")

    @pytest.mark.skipif(not transport.unix_sockets_supported(), reason="no unix sockets")
    def test_a_socket_path_too_long_for_the_address_falls_back_to_tcp(self, monkeypatch):
        monkeypatch.setattr(transport, "socket_dir", lambda: "/" + "d" * 120)
        assert transport.socket_path_for_session("/ws", "session") is None

    @pytest.mark.skipif(not transport.unix_sockets_supported(), reason="no unix sockets")
    def test_each_session_gets_its_own_socket(self, tmp_path, monkeypatch):
        monkeypatch.setattr(transport, "socket_dir", lambda: str(tmp_path))
        first = transport.socket_path_for_session("/ws", "one")
        second = transport.socket_path_for_session("/ws", "two")
        assert first != second
        assert first == transport.socket_path_for_session("/ws", "one")


class TestBinding:
    """Exposing a session to the network is a decision, never a default."""

    def _handler(self):
        from odatix.lib.parallel_job_handler.handler_core import ParallelJobHandler

        return ParallelJobHandler(
            job_list=[], nb_jobs=1, process_group=True, auto_exit=False, log_size_limit=10
        )

    def test_binding_a_routable_address_is_refused_by_default(self):
        from odatix.lib.parallel_job_handler.api import create_uvicorn_server

        with pytest.raises(ValueError):
            create_uvicorn_server(self._handler(), host="0.0.0.0", port=8999)

    def test_binding_a_routable_address_is_possible_on_purpose(self):
        from odatix.lib.parallel_job_handler.api import create_uvicorn_server

        server = create_uvicorn_server(
            self._handler(), host="0.0.0.0", port=8999, allow_remote_bind=True
        )
        assert server.session_auth.control_token

    def test_an_app_cannot_be_built_without_authentication(self):
        from odatix.lib.parallel_job_handler.api import create_parallel_job_app

        with pytest.raises(ValueError):
            create_parallel_job_app(self._handler(), auth=None)


class TestPublicState:
    def test_tokens_never_leave_through_a_session_listing(self):
        from odatix.lib.parallel_job_handler import daemon_control

        state = {"session_id": "1.a", "token": "control", "read_token": "read"}
        assert daemon_control.public_state(state) == {"session_id": "1.a"}

        listing = daemon_control.daemons_to_json([state])
        assert "control" not in listing and "read" not in listing

    def test_the_remote_listing_keeps_them_on_purpose(self):
        from odatix.lib.parallel_job_handler import daemon_control

        listing = daemon_control.daemons_to_json([{"token": "control"}], include_secrets=True)
        assert "control" in listing
