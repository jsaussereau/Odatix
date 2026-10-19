"""
Who may use a session besides its owner ("session_access").

Using a session is running commands as its owner: its token is that right, and
the token is in its state file. Sharing a session is therefore making its state
file (and its socket) reachable by those it is shared with, and by nobody else.
"""

import os
import stat
import sys

import pytest

import odatix.lib.parallel_job_handler.auth as auth
import odatix.lib.parallel_job_handler.daemon_control as daemon_control

posix_only = pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")


def _mode(path):
    return stat.S_IMODE(os.stat(str(path)).st_mode)


class TestLevels:
    def test_the_default_is_private(self):
        assert auth.normalize_access(None) == "user"
        assert auth.normalize_access("") == "user"

    def test_an_unknown_level_is_refused(self):
        with pytest.raises(ValueError, match="Unknown session access 'everyone'"):
            auth.normalize_access("everyone")

    @pytest.mark.parametrize("access, file_mode, socket_mode", [
        ("user", 0o600, 0o600), ("group", 0o640, 0o660), ("other", 0o644, 0o666),
    ])
    def test_modes(self, access, file_mode, socket_mode):
        assert auth.access_file_mode(access) == file_mode
        assert auth.access_socket_mode(access) == socket_mode


@posix_only
class TestFiles:
    def test_a_state_file_gets_its_exact_mode_whatever_the_umask(self, tmp_path):
        previous = os.umask(0o077)
        try:
            path = tmp_path / "state.json"
            auth.write_secret_json(str(path), {"token": "x"}, mode=0o640)
        finally:
            os.umask(previous)
        assert _mode(path) == 0o640

    def test_a_private_state_file_stays_private(self, tmp_path):
        path = tmp_path / "state.json"
        auth.write_secret_json(str(path), {"token": "x"})
        assert _mode(path) == 0o600

    def test_the_state_directory_can_be_traversed_never_listed(self, tmp_path):
        state_dir = tmp_path / "sessions"
        auth.prepare_state_dir(str(state_dir), "other")
        assert _mode(state_dir) == 0o711

    def test_a_private_session_does_not_cut_a_shared_one_off(self, tmp_path):
        state_dir = tmp_path / "sessions"
        auth.prepare_state_dir(str(state_dir), "group")
        auth.prepare_state_dir(str(state_dir), "user")
        assert _mode(state_dir) == 0o710

    def test_a_loose_directory_is_tightened(self, tmp_path):
        state_dir = tmp_path / "sessions"
        state_dir.mkdir()
        os.chmod(str(state_dir), 0o777)
        auth.prepare_state_dir(str(state_dir), "user")
        assert _mode(state_dir) == 0o711


class TestWorkspaceSetting:
    def test_it_is_read_from_odatix_yml(self, tmp_path):
        (tmp_path / "odatix.yml").write_text("workspace: odatix\nsession_access: group\n", encoding="utf-8")
        assert daemon_control.workspace_session_access(str(tmp_path)) == "group"

    def test_without_it_sessions_are_private(self, tmp_path):
        (tmp_path / "odatix.yml").write_text("workspace: odatix\n", encoding="utf-8")
        assert daemon_control.workspace_session_access(str(tmp_path)) == "user"

    def test_a_wrong_value_is_an_error_not_a_guess(self, tmp_path):
        (tmp_path / "odatix.yml").write_text("session_access: everybody\n", encoding="utf-8")
        with pytest.raises(daemon_control.DaemonControlError, match="Unknown session access"):
            daemon_control.workspace_session_access(str(tmp_path))

    def test_the_run_option_reaches_the_daemon(self, monkeypatch):
        seen = {}

        def ensure(**kwargs):
            seen.update(kwargs)
            return {"session_id": "1.s"}

        class Jobs(object):
            job_list = []
            session_access = "other"

        monkeypatch.setattr(daemon_control, "ensure_daemon_running", ensure)
        monkeypatch.setattr(daemon_control, "_api_request", lambda *args, **kwargs: {})
        daemon_control.enqueue_parallel_jobs(Jobs(), configure=False)
        assert seen["access"] == "other"


@posix_only
class TestZombies:
    def test_a_session_not_shared_with_you_is_no_zombie(self, tmp_path, monkeypatch):
        # Its state file cannot be read, so it cannot be asked whether it
        # answers: taking it for a zombie had "stop -z" try to kill it.
        state_file = tmp_path / ".odatix_sessions" / "x.json"
        monkeypatch.setattr(daemon_control, "_iter_system_daemon_candidates", lambda: iter([{
            "pid": 4242, "uid": daemon_control.current_uid(), "state_file": str(state_file),
            "session_name": "x", "workspace_root": str(tmp_path),
        }]))
        monkeypatch.setattr(daemon_control, "_state_file_is_unreadable", lambda path: True)
        monkeypatch.setattr(daemon_control, "_daemon_is_alive_with_retries", lambda state: False)
        assert daemon_control.list_zombie_daemons(workspace_root=str(tmp_path)) == []


@posix_only
@pytest.mark.integration
class TestRealSession:
    """A daemon actually started shared with the group of its workspace."""

    @pytest.fixture
    def session(self, tmp_path, monkeypatch):
        pytest.importorskip("uvicorn")
        workspace = tmp_path / "ws"
        workspace.mkdir()
        (workspace / "odatix.yml").write_text("workspace: odatix\nsession_access: group\n", encoding="utf-8")
        monkeypatch.chdir(str(workspace))
        state = daemon_control.ensure_daemon_running(workspace_root=str(workspace), session="shared_test")
        yield workspace, state
        daemon_control.stop_daemon(workspace_root=str(workspace), session="shared_test")

    def test_its_files_are_shared_with_the_group_only(self, session):
        workspace, state = session
        assert state["access"] == "group"
        group = os.stat(str(workspace)).st_gid
        state_file = state["state_file"]
        assert _mode(state_file) == 0o640 and os.stat(state_file).st_gid == group
        assert _mode(os.path.dirname(state_file)) == 0o710
        socket_path = state["socket_path"]
        assert _mode(socket_path) == 0o660 and os.stat(socket_path).st_gid == group
        assert _mode(os.path.dirname(socket_path)) == 0o711

    def test_it_is_listed_as_yours_with_its_access(self, session):
        _workspace, state = session
        listed = [d for d in daemon_control.list_daemons() if d.get("session_id") == state["session_id"]]
        assert listed and listed[0]["uid"] == os.geteuid() and listed[0]["access"] == "group"


class TestOtherUsersHomes:
    def test_a_session_in_a_home_you_cannot_enter_is_listed_without_access(self, monkeypatch):
        # Its state file looks missing, not unreadable: it is still another
        # user's session, listed as one you cannot use, never dropped.
        monkeypatch.setattr(daemon_control, "current_uid", lambda: 1000)
        monkeypatch.setattr(daemon_control, "_iter_system_daemon_candidates", lambda: iter([{
            "pid": 4242, "uid": 1001, "state_file": "/closed/home/ws/.odatix_sessions/gui.json",
            "session_name": "gui", "workspace_root": "/closed/home/ws",
        }]))
        monkeypatch.setattr(daemon_control, "_daemon_is_alive_for_listing", lambda state: False)
        listed = daemon_control.list_daemons(any_user=True)
        assert [d["pid"] for d in listed] == [4242] and listed[0]["no_access"] is True
        assert daemon_control.list_daemons() == []
        assert daemon_control.list_zombie_daemons(any_user=True) == []


@posix_only
class TestReachableWorkspace:
    def test_a_closed_parent_is_found(self, tmp_path):
        home = tmp_path / "home"
        workspace = home / "ws"
        workspace.mkdir(parents=True)
        os.chmod(str(tmp_path), 0o755)
        os.chmod(str(home), 0o700)
        os.chmod(str(workspace), 0o755)
        assert daemon_control.unreachable_parent(str(workspace), "group") == str(home.resolve())
        assert daemon_control.unreachable_parent(str(workspace), "user") is None

    def test_an_open_path_is_fine(self, tmp_path):
        os.chmod(str(tmp_path), 0o755)
        if daemon_control.unreachable_parent(os.path.dirname(str(tmp_path)), "other") is not None:
            pytest.skip("the temporary directory itself is closed")
        assert daemon_control.unreachable_parent(str(tmp_path), "other") is None
