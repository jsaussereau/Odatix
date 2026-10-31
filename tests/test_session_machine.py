"""
Sessions of a workspace shared by several machines (network home directory).

A pid only means something on the machine that issued it: a session started
on another machine looks gone from here, and must not be treated as such --
its state file deleted, it is unreachable for good while its jobs keep running.
"""

import json

import pytest

import odatix.lib.parallel_job_handler.daemon_control as daemon_control

# No process has this pid here (above the Linux pid_max limit).
ABSENT_PID = 2 ** 23


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    (tmp_path / "odatix.yml").write_text("workspace: odatix\n", encoding="utf-8")
    monkeypatch.setattr(daemon_control, "_iter_system_daemon_candidates", lambda: iter([]))
    monkeypatch.setattr(daemon_control, "machine_name", lambda: "here")
    return tmp_path


def _write_state(workspace, session_name, **fields):
    paths = daemon_control.get_daemon_paths(str(workspace), session_name=session_name)
    state_dir = workspace / ".odatix_sessions"
    state_dir.mkdir(exist_ok=True)
    state = {"pid": ABSENT_PID, "session_name": session_name, "transport": "tcp",
             "host": "127.0.0.1", "port": 1}
    state.update(fields)
    with open(paths["state_file"], "w") as file:
        json.dump(state, file)
    return paths["state_file"]


def test_listing_keeps_the_state_file_of_another_machine(workspace):
    state_file = _write_state(workspace, "remote", machine="elsewhere")
    assert daemon_control.list_daemons(workspace_root=str(workspace)) == []
    assert (workspace / ".odatix_sessions" / state_file.split("/")[-1]).exists()


def test_listing_still_cleans_up_a_local_dead_session(workspace):
    state_file = _write_state(workspace, "local", machine="here")
    daemon_control.list_daemons(workspace_root=str(workspace))
    assert not (workspace / ".odatix_sessions" / state_file.split("/")[-1]).exists()


def test_another_machine_session_is_no_stale_zombie(workspace):
    _write_state(workspace, "remote", machine="elsewhere")
    assert daemon_control.list_zombie_daemons(workspace_root=str(workspace)) == []


def test_another_machine_session_name_is_not_taken_over(workspace):
    _write_state(workspace, "remote", machine="elsewhere")
    with pytest.raises(daemon_control.DaemonControlError, match="runs on elsewhere"):
        daemon_control.ensure_daemon_running(workspace_root=str(workspace), session="remote")
