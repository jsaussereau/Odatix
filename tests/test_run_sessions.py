"""
What a script can do with a run once its jobs are handed over, and the cases a
run used to get wrong: a misspelled option, an empty plan, the resource guard of
the workspace.
"""

import os
import sys

import pytest

import odatix.lib.parallel_job_handler.daemon_control as daemon_control
from odatix.lib.parallel_job_handler import handler_core
from odatix.run import NothingToRun, Run, RunError, Session, SessionError, sessions
from odatix.run.errors import NOTHING_TO_RUN
from odatix.workspace import Workspace


######################################
# Options
######################################

class TestUnknownOptions:
    def test_a_misspelled_option_is_refused(self, example_workspace):
        with pytest.raises(TypeError) as raised:
            Run(Workspace.open(), "workflow", overwite=True)
        assert "'overwite'" in str(raised.value)
        assert "overwrite" in str(raised.value)  # the suggestion

    def test_an_options_dict_is_checked_too(self, example_workspace):
        with pytest.raises(TypeError):
            Run(Workspace.open(), "workflow", options={"nb_job": 2})

    def test_known_options_are_accepted(self, example_workspace):
        run = Run(Workspace.open(), "fmax_synthesis", tool="vivado", nb_jobs=2, overwrite=True)
        assert run.options.nb_jobs == 2


######################################
# Nothing to run
######################################

class TestNothingToRun:
    def _plan(self, *categories):
        from odatix.lib.run_report import JobPlan

        plan = JobPlan()
        for index, category in enumerate(categories):
            plan.add("job{}".format(index), category)
        return plan

    def test_jobs_all_in_a_session_is_nothing_to_run(self, capsys):
        from odatix.components.run_common import confirm_valid_jobs

        with pytest.raises(SystemExit) as stop:
            confirm_valid_jobs(0, False, None, plan=self._plan("daemon", "daemon"))
        assert stop.value.code == NOTHING_TO_RUN
        assert "already in a session (running or over)" in capsys.readouterr().out

    def test_jobs_done_or_in_a_session_is_nothing_to_run(self, capsys):
        from odatix.components.run_common import confirm_valid_jobs

        with pytest.raises(SystemExit) as stop:
            confirm_valid_jobs(0, False, None, plan=self._plan("cached", "daemon"))
        assert stop.value.code == NOTHING_TO_RUN

    def test_an_invalid_job_is_still_a_failure(self):
        from odatix.components.run_common import confirm_valid_jobs

        with pytest.raises(SystemExit) as stop:
            confirm_valid_jobs(0, False, None, plan=self._plan("daemon", "error"))
        assert stop.value.code == -1

    def test_the_api_raises_a_distinct_error_with_a_message(self, example_workspace):
        run = Run(Workspace.open(), "fmax_synthesis")

        def nothing():
            raise SystemExit(NOTHING_TO_RUN)

        with pytest.raises(NothingToRun) as raised:
            run._step("check", nothing)
        assert isinstance(raised.value, RunError)
        assert raised.value.code == NOTHING_TO_RUN
        assert "Nothing to run" in str(raised.value)

    def test_the_command_exits_with_success(self, example_workspace):
        from odatix.run import cli

        class _Run(object):
            workspace = Workspace.open()

            def execute(self):
                raise NothingToRun("nothing")

        with pytest.raises(SystemExit) as stop:
            cli.execute(_Run())
        assert stop.value.code == 0


######################################
# The resource guard of the workspace
######################################

class TestWorkspaceGuard:
    @pytest.fixture(autouse=True)
    def guard_available(self, monkeypatch):
        monkeypatch.setattr(handler_core, "_resource_guard_unavailable", [None])

    def _prepared(self, example_workspace, settings):
        path = example_workspace / "odatix.yml"
        path.write_text(path.read_text(encoding="utf-8") + "\n" + settings + "\n", encoding="utf-8")
        run = Run(Workspace.open(), "fmax_synthesis")
        handler = handler_core.ParallelJobHandler([], format_yaml="")
        return run._with_workspace_guard(handler)

    def test_the_guard_can_be_turned_off_in_odatix_yml(self, example_workspace):
        handler = self._prepared(example_workspace, "resource_guard: No")
        assert handler.resource_guard_enabled is False

    def test_the_limits_come_from_odatix_yml(self, example_workspace):
        handler = self._prepared(example_workspace, "cpu_limit: 50\nmem_limit: 60")
        assert (handler.cpu_limit, handler.mem_limit) == (50.0, 60.0)
        assert handler.resource_guard_enabled is True

    def test_they_reach_the_session(self, example_workspace, monkeypatch):
        sent = {}
        monkeypatch.setattr(daemon_control, "ensure_daemon_running", lambda **kw: {"session_id": "1.s"})
        monkeypatch.setattr(
            daemon_control, "_api_request",
            lambda state, method, path, payload=None, **kw: sent.update(payload=payload) or {},
        )
        handler = self._prepared(example_workspace, "resource_guard: No\ncpu_limit: 50")
        daemon_control.enqueue_parallel_jobs(handler, session="s")
        assert sent["payload"]["options"]["resource_guard"] is False
        assert sent["payload"]["options"]["cpu_limit"] == 50.0


######################################
# Following a session
######################################

class _FakeSession(object):
    """Answers like a session holding `jobs`, from the snapshot it would send."""

    def __init__(self, jobs, root):
        self.jobs = jobs
        self.root = root
        self.posted = []

    def request(self, state, method, path, payload=None, timeout=1.0, scope=None):
        if method == "POST":
            self.posted.append(path)
            return {"ok": True}
        return {
            "handler": {"nb_jobs": 2, "resource_guard": {"enabled": True}},
            "jobs": [dict(job, id=index) for index, job in enumerate(self.jobs)],
        }


@pytest.fixture
def fake_session(tmp_path, monkeypatch):
    (tmp_path / "odatix.yml").write_text("{}", encoding="utf-8")
    jobs = [
        {"display_name": "old/a", "status": "failed", "tmp_dir": "work/a", "progress": 10, "elapsed_time": "00:00:05"},
        {"display_name": "b", "status": "running", "tmp_dir": "work/b", "progress": 40, "elapsed_time": "00:00:09"},
        {"display_name": "a", "status": "success", "tmp_dir": "work/a", "progress": 100, "elapsed_time": "00:00:07"},
        {"display_name": "other", "status": "queued", "tmp_dir": "work/c", "progress": 0, "elapsed_time": "00:00:00"},
    ]
    fake = _FakeSession(jobs, str(tmp_path))
    monkeypatch.setattr(daemon_control, "_api_request", fake.request)
    monkeypatch.chdir(str(tmp_path))
    state = {"pid": 7, "session_name": "s", "session_id": "7.s", "workspace_root": os.path.realpath(str(tmp_path))}
    return fake, Session(state)


class TestSession:
    def test_what_it_is(self, fake_session):
        _fake, session = fake_session
        assert (session.id, session.name, session.pid) == ("7.s", "s", 7)

    def test_its_jobs(self, fake_session):
        _fake, session = fake_session
        jobs = session.jobs()
        assert [job["name"] for job in jobs] == ["old/a", "b", "a", "other"]
        assert jobs[1]["tmp_dir"] == os.path.realpath(os.path.join(session.workspace_root, "work", "b"))

    def test_its_counts(self, fake_session):
        _fake, session = fake_session
        assert session.counts() == {"total": 4, "running": 1, "queued": 1, "done": 1, "failed": 1}
        assert session.is_finished() is False

    def test_controls_go_through_its_api(self, fake_session):
        fake, session = fake_session
        session.pause(1)
        session.resume(1)
        session.kill(3)
        session.set_jobs(4)
        session.set_resource_guard(False)
        assert fake.posted == [
            "/jobs/1/pause", "/jobs/1/start", "/jobs/3/kill", "/config?nb_jobs=4", "/config?resource_guard=false",
        ]

    def test_waiting_times_out(self, fake_session):
        _fake, session = fake_session
        with pytest.raises(TimeoutError):
            session.wait(timeout=0.1, poll_interval=0.05)

    def test_waiting_for_finished_jobs_returns_them(self, fake_session):
        _fake, session = fake_session
        assert [job["name"] for job in session.wait(job_ids=[0, 2], timeout=1)] == ["old/a", "a"]

    def test_a_silent_session_raises(self, fake_session, monkeypatch):
        _fake, session = fake_session

        def silent(*args, **kwargs):
            raise OSError("no answer")

        monkeypatch.setattr(daemon_control, "_api_request", silent)
        with pytest.raises(SessionError):
            session.jobs()

    def test_stopping_it(self, fake_session, monkeypatch):
        _fake, session = fake_session
        stopped = []
        monkeypatch.setattr(daemon_control, "_stop_daemon_from_state", lambda state, root: stopped.append(state["pid"]) or True)
        assert session.stop() is True
        assert stopped == [7]

    def test_listing_keeps_to_the_workspace(self, fake_session, monkeypatch, tmp_path):
        _fake, session = fake_session
        here = session.workspace_root
        monkeypatch.setattr(daemon_control, "list_daemons", lambda **kwargs: [
            {"pid": 7, "session_name": "s", "workspace_root": here},
            {"pid": 8, "session_name": "x", "workspace_root": str(tmp_path.parent)},
        ])
        assert [s.pid for s in sessions()] == [7]
        assert [s.pid for s in sessions(any_workspace=True)] == [7, 8]

    def test_finding_one_by_name(self, fake_session, monkeypatch):
        _fake, session = fake_session
        monkeypatch.setattr(daemon_control, "list_daemons", lambda **kwargs: [dict(session._state)])
        assert Session.find("s").id == "7.s"
        with pytest.raises(SessionError):
            Session.find("nope")


class TestFollowingARun:
    def _started(self, fake_session, example_workspace):
        fake, session = fake_session
        run = Run(Workspace.open(), "workflow")
        run._session = session
        run._job_dirs = [os.path.realpath(os.path.join(session.workspace_root, "work", name)) for name in ("a", "b")]
        run._started = True
        return run

    def test_its_status_holds_its_own_jobs_only(self, fake_session, example_workspace):
        run = self._started(fake_session, example_workspace)
        # "a" was run twice in that session: this run's is the last one.
        assert [(job["name"], job["status"]) for job in run.status()] == [("a", "success"), ("b", "running")]

    def test_waiting_for_it(self, fake_session, example_workspace):
        run = self._started(fake_session, example_workspace)
        fake, _session = fake_session
        fake.jobs[1]["status"] = "success"
        # The queued job of another run of the session does not hold it up.
        assert [job["status"] for job in run.wait(timeout=1)] == ["success", "success"]

    def test_a_run_not_started_has_nothing_to_follow(self, example_workspace):
        run = Run(Workspace.open(), "workflow")
        assert run.session is None
        with pytest.raises(RunError):
            run.status()

    def test_starting_records_the_session(self, example_workspace, monkeypatch):
        run = Run(Workspace.open(), "workflow")
        handler = handler_core.ParallelJobHandler([], format_yaml="")
        run._parallel_jobs = handler

        def start(run_, jobs):
            jobs.session_state = {"pid": 9, "session_name": "n", "session_id": "9.n", "workspace_root": "/w"}

        monkeypatch.setattr(run.flow, "start", start)
        run.start()
        assert run.session.id == "9.n"


######################################
# "-E": the session closes with the monitor
######################################

class TestExitWhenDone:
    def _close(self, fake_session, monkeypatch, alive=True):
        from odatix.components.run_common import close_finished_session

        _fake, session = fake_session
        stopped = []
        monkeypatch.setattr(daemon_control, "daemon_is_alive", lambda state, timeout=0.6: alive)
        monkeypatch.setattr(daemon_control, "_stop_daemon_from_state", lambda state, root: stopped.append(1) or True)
        return close_finished_session(dict(session._state)), stopped

    def test_a_finished_session_is_closed_with_a_summary(self, fake_session, monkeypatch, capsys):
        fake, _session = fake_session
        for job in fake.jobs:
            job["status"] = "success" if job["display_name"] != "old/a" else "failed"
        counts, stopped = self._close(fake_session, monkeypatch)
        out = capsys.readouterr().out
        assert stopped == [1]
        assert "3/4 jobs succeeded, 1 failed" in out
        assert "Session 7.s closed" in out

    def test_a_session_with_jobs_left_stays(self, fake_session, monkeypatch, capsys):
        counts, stopped = self._close(fake_session, monkeypatch)
        assert stopped == []
        assert 'odatix monitor -S s' in capsys.readouterr().out

    def test_a_session_already_closed_is_left_alone(self, fake_session, monkeypatch, capsys):
        counts, stopped = self._close(fake_session, monkeypatch, alive=False)
        assert counts is None and stopped == []


class TestDetachedRunNote:
    def test_it_says_where_the_jobs_went(self, monkeypatch, capsys):
        from odatix.components import run_common

        monkeypatch.setattr(
            run_common, "enqueue_parallel_jobs",
            lambda jobs, session=None, configure=True: ({"session_id": "5.nightly", "session_name": "nightly"}, {}),
        )
        handler = handler_core.ParallelJobHandler([], format_yaml="")
        run_common.start_parallel_jobs(handler, detach=True, session="nightly")
        out = capsys.readouterr().out
        assert "handed to session 5.nightly" in out
        assert 'odatix monitor -S nightly' in out and 'odatix stop -S nightly' in out

    def test_an_exploration_batch_says_nothing(self, monkeypatch, capsys):
        from odatix.components import run_common

        monkeypatch.setattr(
            run_common, "enqueue_parallel_jobs",
            lambda jobs, session=None, configure=True: ({"session_id": "5.dse", "session_name": "dse"}, {}),
        )
        run_common.start_parallel_jobs(handler_core.ParallelJobHandler([], format_yaml=""), detach=True, configure=False)
        assert "handed to session" not in capsys.readouterr().out


######################################
# Colors
######################################

class TestPlainOutput:
    def test_colors_are_dropped_outside_a_terminal(self, monkeypatch):
        import io

        from odatix.lib import printc

        buffer = io.StringIO()
        monkeypatch.setattr(sys, "stdout", buffer)
        monkeypatch.setattr(sys, "stderr", io.StringIO())
        printc.plain_unless_terminal()
        printc.note("hello", "odatix")
        assert "\033" not in buffer.getvalue()
        assert "note: hello" in buffer.getvalue()

    def test_no_color_drops_them_in_a_terminal_too(self, monkeypatch):
        from odatix.lib import printc

        class _Tty(object):
            def isatty(self):
                return True

        monkeypatch.setenv("NO_COLOR", "1")
        assert printc.wants_color(_Tty()) is False
        monkeypatch.delenv("NO_COLOR")
        assert printc.wants_color(_Tty()) is True
