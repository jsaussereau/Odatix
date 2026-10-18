"""
The resource guard of the job scheduler: pausing jobs while the machine is
overloaded, set from the workspace settings and switched at runtime.
"""

import sys

import pytest

from odatix.lib.settings import OdatixSettings
from odatix.lib.parallel_job_handler import handler_core
from odatix.lib.parallel_job_handler.handler_core import ParallelJobHandler, RESOURCE_GUARD_HYSTERESIS

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="no SIGSTOP/SIGCONT on Windows")


class _PausedJob(object):
    """Just what the guard touches on a job it paused."""

    def __init__(self):
        self.status = "paused"
        self.log_history = []

    def resume(self, by="user", detail=None):
        self.status = "running"


@pytest.fixture
def workspace_guard(monkeypatch):
    # The guard can run (psutil is an optional dependency): these tests are
    # about what it does, not about where.
    monkeypatch.setattr(handler_core, "_resource_guard_unavailable", [None])

    def latch(value):
        monkeypatch.setattr(OdatixSettings, "resource_guard_settings", value)
    latch(None)
    return latch


class TestUnavailable:
    @pytest.fixture
    def no_psutil(self, workspace_guard, monkeypatch):
        monkeypatch.setattr(handler_core, "_resource_guard_unavailable", [])
        monkeypatch.setitem(sys.modules, "psutil", None)

    def test_the_reason_is_given(self, no_psutil):
        assert handler_core.resource_guard_unavailable_reason() == "psutil is not installed"

    def test_it_cannot_be_switched_on(self, no_psutil):
        handler = ParallelJobHandler([], resource_guard=True)
        assert handler.resource_guard_enabled is False
        handler.configure_runtime(resource_guard=True)
        assert handler.resource_guard_enabled is False
        handler._check_resource_guard_unlocked()  # nothing to sample, nothing raised

    def test_the_snapshot_and_the_monitor_say_why(self, no_psutil):
        from odatix.lib.parallel_job_handler.curses_ui import _resource_guard_label

        handler = ParallelJobHandler([])
        assert handler.snapshot()["handler"]["resource_guard"]["unavailable"] == "psutil is not installed"
        assert _resource_guard_label(handler) == "unavailable"


class TestDefaults:
    def test_without_settings_the_guard_is_on(self, workspace_guard):
        handler = ParallelJobHandler([])
        assert handler.resource_guard_enabled is OdatixSettings.DEFAULT_RESOURCE_GUARD
        assert handler.cpu_limit == OdatixSettings.DEFAULT_CPU_LIMIT
        assert handler.mem_limit == OdatixSettings.DEFAULT_MEM_LIMIT

    def test_the_workspace_settings_are_the_defaults(self, workspace_guard):
        workspace_guard((False, 80.0, 90.0))
        handler = ParallelJobHandler([])
        assert handler.resource_guard_enabled is False
        assert handler.cpu_limit == 80.0
        assert handler.mem_limit == 90.0

    def test_explicit_arguments_win_over_the_workspace(self, workspace_guard):
        workspace_guard((False, 80.0, 90.0))
        handler = ParallelJobHandler([], resource_guard=True, cpu_limit=70)
        assert handler.resource_guard_enabled is True
        assert handler.cpu_limit == 70.0
        assert handler.mem_limit == 90.0


class TestRuntime:
    def test_hysteresis_is_the_same_at_build_and_at_runtime(self, workspace_guard):
        handler = ParallelJobHandler([], cpu_limit=90, mem_limit=90)
        built = (handler.cpu_resume_limit, handler.mem_resume_limit)
        handler.configure_runtime(cpu_limit=90, mem_limit=90)
        assert (handler.cpu_resume_limit, handler.mem_resume_limit) == built
        assert built == (90 - RESOURCE_GUARD_HYSTERESIS, 90 - RESOURCE_GUARD_HYSTERESIS)

    def test_limits_are_kept_within_percentages(self, workspace_guard):
        handler = ParallelJobHandler([])
        handler.configure_runtime(cpu_limit=500, mem_limit=-3)
        assert handler.cpu_limit == 100.0
        assert handler.mem_limit == 1.0

    def test_omitted_values_are_kept(self, workspace_guard):
        handler = ParallelJobHandler([], resource_guard=False, cpu_limit=75)
        handler.configure_runtime(nb_jobs=2)
        assert handler.resource_guard_enabled is False
        assert handler.cpu_limit == 75.0

    def test_disabling_resumes_the_jobs_it_paused(self, workspace_guard):
        handler = ParallelJobHandler([])
        paused = [_PausedJob(), _PausedJob()]
        handler._auto_paused_jobs = list(paused)

        handler.configure_runtime(resource_guard=False)

        assert handler.resource_guard_enabled is False
        assert [job.status for job in paused] == ["running", "running"]
        assert handler._auto_paused_jobs == []

    def test_a_job_resumed_by_hand_is_left_alone(self, workspace_guard):
        handler = ParallelJobHandler([])
        job = _PausedJob()
        job.status = "running"
        handler._auto_paused_jobs = [job]

        handler.configure_runtime(resource_guard=False)
        assert job.log_history == []

    def test_a_disabled_guard_never_samples(self, workspace_guard, monkeypatch):
        handler = ParallelJobHandler([], resource_guard=False)
        monkeypatch.setitem(sys.modules, "psutil", None)  # importing it would fail
        handler._check_resource_guard_unlocked()  # would raise if it sampled

    def test_the_snapshot_reports_the_switch(self, workspace_guard):
        handler = ParallelJobHandler([])
        handler.configure_runtime(resource_guard=False, cpu_limit=85)
        guard = handler.snapshot()["handler"]["resource_guard"]
        assert guard["enabled"] is False
        assert guard["cpu_limit"] == 85.0


class TestDummySession:
    def test_the_monitor_switch_round_trips(self):
        from odatix.gui import dummy_session

        dummy_session.api_post("/config?resource_guard=false")
        assert dummy_session.get_session(dummy_session.DUMMY_SESSION_ID).resource_guard is False
        dummy_session.api_post("/config?resource_guard=true")
        assert dummy_session.get_session(dummy_session.DUMMY_SESSION_ID).resource_guard is True


class TestCursesMonitor:
    """The curses monitor switches the guard of the handler it shows."""

    def test_a_local_handler_switches_itself(self, workspace_guard):
        handler = ParallelJobHandler([])
        handler.set_resource_guard(False)
        assert handler.resource_guard_enabled is False
        handler.set_resource_guard(True)
        assert handler.resource_guard_enabled is True

    def test_the_header_says_what_the_guard_is_doing(self, workspace_guard):
        from odatix.lib.parallel_job_handler.curses_ui import _resource_guard_label

        handler = ParallelJobHandler([])
        assert _resource_guard_label(handler) == "on"
        handler._auto_paused_jobs = [_PausedJob(), _PausedJob()]
        assert _resource_guard_label(handler) == "on (2 paused)"
        handler.set_resource_guard(False)
        assert _resource_guard_label(handler) == "off"


class _DaemonEndpoint(object):
    """Answers the monitor from a local handler, like a daemon would."""

    def __init__(self, handler):
        self.handler = handler

    def request(self, method, path, payload=None, timeout=None):
        route, _, query = path.partition("?")
        params = dict(item.partition("=")[::2] for item in query.split("&") if item)
        if method == "POST" and route == "/config":
            self.handler.configure_runtime(resource_guard=params["resource_guard"] == "true")
            return {"ok": True}
        assert route == "/status"
        return self.handler.snapshot()


class TestDaemonMonitor:
    @pytest.fixture
    def pair(self, workspace_guard):
        from odatix.lib.parallel_job_handler.daemon_monitor import DaemonMonitorHandler

        daemon = ParallelJobHandler([], resource_guard=True)
        monitor = DaemonMonitorHandler(endpoint=_DaemonEndpoint(daemon), poll_interval=0.0)
        monitor._sync_snapshot(force=True)
        return daemon, monitor

    def test_the_monitor_shows_the_daemon_guard(self, pair):
        daemon, monitor = pair
        daemon._auto_paused_jobs = [_PausedJob()]
        monitor._sync_snapshot(force=True)
        assert monitor.resource_guard_enabled is True
        assert monitor.resource_guard_paused_count() == 1

    def test_the_switch_is_forwarded_to_the_daemon(self, pair):
        daemon, monitor = pair
        monitor.set_resource_guard(False)
        assert daemon.resource_guard_enabled is False
        monitor._sync_snapshot(force=True)
        assert monitor.resource_guard_enabled is False

    def test_the_monitor_never_pauses_anything_itself(self, pair, monkeypatch):
        _daemon, monitor = pair
        monkeypatch.setitem(sys.modules, "psutil", None)  # sampling would fail
        monitor._check_resource_guard_unlocked()
        assert monitor._auto_paused_jobs == []
