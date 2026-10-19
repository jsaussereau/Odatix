"""
Which sessions "odatix monitor", "stop" and "ps" act on.

Every session of the user runs on the same machine, whatever project it belongs
to. A name like "nightly" means a different session in each of them, so a
session command keeps to the current workspace unless told otherwise.
"""

import argparse
import os

import pytest

import odatix.lib.parallel_job_handler.daemon_control as daemon_control


def _daemon(pid, name, root):
    return {
        "pid": pid, "session_name": name, "session_id": "{}.{}".format(pid, name),
        "workspace_root": os.path.realpath(str(root)), "transport": "unix", "socket_path": "/tmp/s{}".format(pid),
    }


@pytest.fixture
def machine(tmp_path, monkeypatch):
    """Two workspaces with sessions, the current directory in the first one."""
    here, there = tmp_path / "here", tmp_path / "there"
    for root in (here, there):
        root.mkdir()
        (root / "odatix.yml").write_text("{}")
    daemons = [
        _daemon(11, "nightly", here),
        _daemon(12, "build", here),
        _daemon(21, "nightly", there),
        _daemon(22, "other_only", there),
    ]
    monkeypatch.setattr(daemon_control, "list_daemons", lambda *args, **kwargs: list(daemons))
    monkeypatch.setattr(daemon_control, "daemon_is_alive", lambda state, timeout=0.6: False)
    monkeypatch.chdir(str(here))
    return {"here": here, "there": there, "daemons": daemons}


def _resolve(**kwargs):
    return daemon_control._resolve_state_for_attach_or_stop(**kwargs)


class TestSelector:
    def test_a_name_means_the_session_of_this_workspace(self, machine):
        assert _resolve(session="nightly")["pid"] == 11

    def test_a_session_of_another_workspace_is_not_reached(self, machine):
        with pytest.raises(daemon_control.DaemonControlError) as error:
            _resolve(session="other_only")
        assert "--any-workspace" in str(error.value)
        assert "22.other_only" in str(error.value)

    def test_it_is_reached_when_asked(self, machine):
        assert _resolve(session="other_only", any_workspace=True)["pid"] == 22

    def test_an_unknown_name_says_so(self, machine):
        with pytest.raises(daemon_control.DaemonControlError) as error:
            _resolve(session="nothing")
        assert "No session matches 'nothing'" in str(error.value)


class TestNoSelector:
    def test_the_ambiguity_lists_the_sessions_of_this_workspace_only(self, machine):
        with pytest.raises(daemon_control.MultipleDaemonsError) as error:
            _resolve()
        assert sorted(d["pid"] for d in error.value.daemons) == [11, 12]

    def test_the_only_session_of_the_workspace_is_the_one(self, machine):
        machine["daemons"].pop(1)
        assert _resolve()["pid"] == 11

    def test_no_session_here_points_at_the_others(self, machine):
        del machine["daemons"][:2]
        with pytest.raises(daemon_control.DaemonControlError) as error:
            _resolve()
        assert "No session in this workspace" in str(error.value)

    def test_outside_of_any_workspace_every_session_is_in_reach(self, machine, tmp_path, monkeypatch):
        outside = tmp_path / "outside"
        outside.mkdir()
        monkeypatch.chdir(str(outside))
        assert _resolve(session="other_only")["pid"] == 22


class TestStopAll:
    def test_it_stops_the_sessions_of_this_workspace_only(self, machine, monkeypatch):
        stopped = []
        monkeypatch.setattr(daemon_control, "_stop_daemon_from_state", lambda state, root: stopped.append(state["pid"]) or True)
        monkeypatch.setattr(daemon_control, "_cleanup_workspace_daemon_dir_if_empty", lambda root: None)
        result = daemon_control.stop_all_daemons()
        assert sorted(stopped) == [11, 12]
        assert result["total"] == 2

    def test_every_workspace_when_asked(self, machine, monkeypatch):
        stopped = []
        monkeypatch.setattr(daemon_control, "_stop_daemon_from_state", lambda state, root: stopped.append(state["pid"]) or True)
        monkeypatch.setattr(daemon_control, "_cleanup_workspace_daemon_dir_if_empty", lambda root: None)
        daemon_control.stop_all_daemons(any_workspace=True)
        assert sorted(stopped) == [11, 12, 21, 22]


class TestZombies:
    def test_only_the_zombies_of_this_workspace_are_killed(self, machine, monkeypatch):
        zombies = [dict(machine["daemons"][0], status="stale"), dict(machine["daemons"][2], status="stale")]
        monkeypatch.setattr(daemon_control, "list_zombie_daemons", lambda **kwargs: list(zombies))
        monkeypatch.setattr(daemon_control, "_pid_is_running", lambda pid: False)
        removed = []
        monkeypatch.setattr(daemon_control, "_delete_state_files_for_daemon", lambda paths, zombie: removed.append(zombie["pid"]))
        monkeypatch.setattr(daemon_control, "_cleanup_workspace_daemon_dir_if_empty", lambda root: None)
        assert daemon_control.kill_zombie_daemons()["total"] == 1
        assert removed == [11]


class TestCommands:
    def _args(self, **values):
        defaults = dict(
            host=None, port=None, session=None, token=None, remote=None, zombies=False,
            json=False, any_workspace=False, all=False,
        )
        defaults.update(values)
        return argparse.Namespace(**defaults)

    def test_ps_lists_this_workspace_and_counts_the_others(self, machine, capsys):
        from odatix import odatix_main

        assert odatix_main.list_daemons(self._args()) is True
        out = capsys.readouterr().out
        assert "11.nightly" in out and "12.build" in out
        assert "21.nightly" not in out
        assert "2 more sessions in other workspaces" in out

    def test_ps_any_workspace_lists_them_all(self, machine, capsys):
        from odatix import odatix_main

        odatix_main.list_daemons(self._args(any_workspace=True))
        out = capsys.readouterr().out
        assert "21.nightly" in out and "22.other_only" in out

    def test_the_session_commands_accept_the_banner_option(self):
        from odatix import odatix_main

        for command in ("ps", "monitor", "stop"):
            args = odatix_main.ArgParser.parse_arguments([command, "-Q", "--any-workspace"])
            assert args.nobanner is True and args.any_workspace is True
