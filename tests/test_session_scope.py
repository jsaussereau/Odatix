"""
Which sessions "odatix monitor", "stop" and "ps" act on.

Every session of the user runs on the same machine, whatever project it belongs
to. A name like "nightly" means a different session in each of them, so a
session command keeps to the current workspace unless told otherwise.

The sessions of other users run there too. They are out of reach unless asked
for (--any-user), and even then only usable when their owner shares them, or
by root.
"""

import argparse
import os

import pytest

import odatix.lib.parallel_job_handler.daemon_control as daemon_control


ME, BOB = 1000, 1001


def _daemon(pid, name, root, uid=ME, **extra):
    daemon = {
        "pid": pid, "session_name": name, "session_id": "{}.{}".format(pid, name),
        "workspace_root": os.path.realpath(str(root)), "transport": "unix", "socket_path": "/tmp/s{}".format(pid),
        "uid": uid, "user": "me" if uid == ME else "bob",
    }
    daemon.update(extra)
    return daemon


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
    def list_daemons(*args, **kwargs):
        if kwargs.get("any_user"):
            return list(daemons)
        return [d for d in daemons if d["uid"] == daemon_control.current_uid()]

    monkeypatch.setattr(daemon_control, "list_daemons", list_daemons)
    monkeypatch.setattr(daemon_control, "daemon_is_alive", lambda state, timeout=0.6: False)
    monkeypatch.setattr(daemon_control, "current_uid", lambda: ME)
    monkeypatch.chdir(str(here))
    return {"here": here, "there": there, "daemons": daemons}


def _resolve(**kwargs):
    return daemon_control._resolve_state_for_attach_or_stop(**kwargs)


class TestSelector:
    def test_a_name_means_the_session_of_this_workspace(self, machine):
        assert _resolve(session="nightly")["pid"] == 11

    def test_a_session_of_another_workspace_is_not_reached(self, machine):
        with pytest.raises(daemon_control.OtherWorkspacesError) as error:
            _resolve(session="other_only")
        # An error, then where the sessions are (note), then how to reach them (tip).
        assert str(error.value) == "No session of this workspace matches 'other_only'"
        assert "22.other_only" in error.value.note
        assert "--any-workspace" in error.value.tip

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
            json=False, any_workspace=False, all=False, any_user=False,
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
            args = odatix_main.ArgParser.parse_arguments([command, "-Q", "--any-workspace", "--any-user"])
            assert args.nobanner is True and args.any_workspace is True and args.any_user is True


@pytest.fixture
def shared_machine(machine):
    """Bob's sessions in the current workspace: one shared with this user, one private."""
    machine["daemons"].extend([
        _daemon(31, "bob_shared", machine["here"], uid=BOB, access="group"),
        _daemon(32, "bob_private", machine["here"], uid=BOB, no_access=True),
    ])
    return machine


class TestOtherUsers:
    def test_their_sessions_are_out_of_reach_by_default(self, shared_machine):
        with pytest.raises(daemon_control.OutOfScopeError) as error:
            _resolve(session="bob_shared")
        assert str(error.value) == "No session of yours in this workspace matches 'bob_shared'"
        assert "31.bob_shared" in error.value.note and "user bob" in error.value.note
        assert error.value.tip == "add --any-user to reach them"

    def test_a_shared_session_is_reached_when_asked(self, shared_machine):
        assert _resolve(session="bob_shared", any_user=True)["pid"] == 31

    def test_a_private_session_is_refused(self, shared_machine):
        with pytest.raises(daemon_control.SessionAccessError) as error:
            _resolve(session="bob_private", any_user=True)
        assert str(error.value) == "Session 32.bob_private belongs to bob and is not shared with you"
        assert "sudo" in error.value.tip

    def test_no_selector_keeps_to_your_own_sessions(self, shared_machine):
        with pytest.raises(daemon_control.MultipleDaemonsError) as error:
            _resolve()
        assert sorted(d["pid"] for d in error.value.daemons) == [11, 12]

    def test_with_only_their_sessions_here_you_are_told(self, shared_machine):
        del shared_machine["daemons"][:4]
        with pytest.raises(daemon_control.OutOfScopeError) as error:
            _resolve()
        assert str(error.value) == "You have no session in this workspace"
        assert "--any-user" in error.value.tip

    def test_both_options_when_they_are_both_needed(self, shared_machine, tmp_path):
        shared_machine["daemons"].append(_daemon(41, "bob_far", shared_machine["there"], uid=BOB, access="other"))
        with pytest.raises(daemon_control.OutOfScopeError) as error:
            _resolve(session="bob_far")
        assert error.value.tip == "add --any-workspace --any-user to reach them"

    def test_root_reaches_every_session(self, shared_machine, monkeypatch):
        # Root reads every state file: no session is out of its access.
        shared_machine["daemons"][-1].pop("no_access")
        monkeypatch.setattr(daemon_control, "current_uid", lambda: 0)
        assert _resolve(session="bob_private", any_user=True)["pid"] == 32

    def test_stop_all_leaves_the_private_ones_running(self, shared_machine, monkeypatch):
        stopped = []
        monkeypatch.setattr(daemon_control, "_stop_daemon_from_state", lambda state, root: stopped.append(state["pid"]) or True)
        monkeypatch.setattr(daemon_control, "_cleanup_workspace_daemon_dir_if_empty", lambda root: None)
        result = daemon_control.stop_all_daemons(any_user=True)
        assert sorted(stopped) == [11, 12, 31]
        assert [d["pid"] for d in result["failed"]] == [32]

    def test_stop_all_without_the_option_stops_yours_only(self, shared_machine, monkeypatch):
        stopped = []
        monkeypatch.setattr(daemon_control, "_stop_daemon_from_state", lambda state, root: stopped.append(state["pid"]) or True)
        monkeypatch.setattr(daemon_control, "_cleanup_workspace_daemon_dir_if_empty", lambda root: None)
        daemon_control.stop_all_daemons()
        assert sorted(stopped) == [11, 12]

    def test_ps_counts_their_sessions(self, shared_machine, capsys):
        from odatix import odatix_main

        odatix_main.list_daemons(TestCommands()._args())
        out = capsys.readouterr().out
        assert "31.bob_shared" not in out
        assert "2 sessions of other users" in out

    def test_ps_any_user_says_whose_and_who_may_use_them(self, shared_machine, capsys, monkeypatch):
        from odatix import odatix_main

        monkeypatch.setattr(daemon_control, "daemon_jobs_summary", lambda state, timeout=1.5: "no jobs")
        odatix_main.list_daemons(TestCommands()._args(any_user=True))
        lines = capsys.readouterr().out.splitlines()
        header = next(line for line in lines if "session" in line and "access" in line)
        assert header.split()[1:3] == ["user", "access"]
        row = next(line for line in lines if "32.bob_private" in line)
        assert row.split()[1:4] == ["bob", "no", "-"]
        assert next(line for line in lines if "31.bob_shared" in line).split()[1:3] == ["bob", "group"]
