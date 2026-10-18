"""What the monitors show of a job's run time, and what the help says of the keys."""

import sys
import time

import pytest

from odatix.lib.parallel_job_handler import curses_ui
from odatix.lib.parallel_job_handler.daemon_monitor import DaemonMonitorHandler
from odatix.lib.parallel_job_handler.handler_core import ParallelJobHandler
from odatix.lib.parallel_job_handler.job import ParallelJob
from odatix.lib.parallel_job_handler.utils import get_elapsed_time_str


class _NoEndpoint(object):
    def request(self, *args, **kwargs):
        raise RuntimeError("not used")


def _monitor():
    return DaemonMonitorHandler(endpoint=_NoEndpoint(), poll_interval=0.0)


def _remote(status, elapsed):
    return {"id": 0, "display_name": "a", "status": status, "progress": 10, "elapsed_time": elapsed}


class TestPausedClock:
    def test_a_paused_job_clock_stands_still_between_snapshots(self):
        monitor = _monitor()
        job = monitor._new_local_job(remote_id=0, display_name="a", directory=".", tmp_dir=".")
        now = time.time()
        monitor._sync_job_from_remote(job, _remote("paused", "00:00:10"), now)
        # No new snapshot comes for a job that does not change: its elapsed
        # time, read later, must still say 10 seconds.
        assert job.stop_time is not None
        assert job.stop_time - job.start_time == pytest.approx(10.0)

    def test_a_running_job_clock_keeps_going(self):
        monitor = _monitor()
        job = monitor._new_local_job(remote_id=0, display_name="a", directory=".", tmp_dir=".")
        monitor._sync_job_from_remote(job, _remote("running", "00:00:10"), time.time())
        assert job.stop_time is None

    def test_a_paused_job_without_elapsed_time_shows_none_running(self):
        monitor = _monitor()
        job = monitor._new_local_job(remote_id=0, display_name="a", directory=".", tmp_dir=".")
        monitor._sync_job_from_remote(job, _remote("paused", "00:00:00"), time.time())
        assert job.stop_time == job.start_time


@pytest.mark.skipif(sys.platform == "win32", reason="no SIGSTOP on Windows")
class TestKillingAPausedJob:
    def test_the_pause_is_not_counted(self, monkeypatch):
        import odatix.lib.parallel_job_handler.handler_core as handler_core

        job = ParallelJob(
            process=None, command="true", directory=".", generate_rtl=False, generate_command="",
            target="", arch="", display_name="a", status_file="", progress_file="", tmp_dir=".",
            log_size_limit=10, status="paused",
        )
        now = time.time()
        job.start_time = now - 100.0  # ran 13 s, then paused for 87 s
        job.stop_time = now - 87.0
        job.process = object()
        handler = ParallelJobHandler([job], format_yaml="")
        monkeypatch.setattr(handler_core.process_control, "request_stop", lambda job: False)
        monkeypatch.setattr(handler, "_drain_process_pipes", lambda job: None)
        monkeypatch.setattr(handler, "_close_process_pipes", lambda process: None)

        handler.kill_or_cancel_job(0)
        assert job.status == "killed"
        assert get_elapsed_time_str(job.start_time, job.stop_time) == "00:00:13"


class TestHelp:
    def _keys(self):
        lines = []

        class _Window(object):
            def erase(self):
                pass

            def box(self):
                pass

            def refresh(self):
                pass

            def addstr(self, y, x, text, *attributes):
                lines.append((y, x, text))

        monkey = pytest.MonkeyPatch()
        monkey.setattr(curses_ui.curses, "color_pair", lambda index: 0, raising=False)
        try:
            curses_ui.update_help_popup(_Window(), 60, curses_ui.HELP_POPUP_HEIGHT)
        finally:
            monkey.undo()
        rows = {}
        for y, x, text in lines:
            rows.setdefault(y, {})[x] = text
        return dict((row.get(3, "").strip(), row.get(17, "")) for row in rows.values() if 3 in row and 17 in row)

    def test_page_down_selects_the_next_job(self):
        keys = self._keys()
        assert keys["PageDown  n"] == "Select next job"
        assert keys["PageUp    p"] == "Select previous job"

    def test_sideways_scrolling_is_listed(self):
        assert "Left/Right" in self._keys()

    def test_every_key_fits_in_the_popup(self):
        keys = self._keys()
        assert "h         ?" in keys


class TestHeader:
    def _header(self, handler, monkeypatch):
        texts = []

        class _Window(object):
            def __getattr__(self, name):
                return lambda *args, **kwargs: None

            def addstr(self, y, x, text, *attributes):
                texts.append(text)

        monkeypatch.setattr(curses_ui.curses, "color_pair", lambda index: 0, raising=False)
        curses_ui.update_header(handler, _Window(), 1, 0, 2, 120)
        return texts[0]

    def test_it_names_the_session(self, monkeypatch):
        handler = _monitor()
        handler.session_label = "4242.nightly"
        assert self._header(handler, monkeypatch).startswith("session 4242.nightly")

    def test_a_local_run_has_no_session_to_name(self, monkeypatch):
        handler = ParallelJobHandler([], format_yaml="")
        assert "session" not in self._header(handler, monkeypatch)


class TestSessionStoppedElsewhere:
    """B-05: "odatix stop" on a session a monitor watches."""

    class _Gone(object):
        def __init__(self, error):
            self.error = error

        def request(self, *args, **kwargs):
            raise self.error

    def _poll(self, monitor, monkeypatch, at):
        import odatix.lib.parallel_job_handler.daemon_monitor as daemon_monitor

        if not getattr(monitor, "_test_clock", False):
            monitor._test_clock = True
            monitor._unreachable_since = None  # whatever building it polled, in real time
        monkeypatch.setattr(daemon_monitor.time, "time", lambda: at)
        monitor._sync_snapshot(force=True)

    def test_a_vanished_socket_ends_the_monitor(self, monkeypatch):
        monitor = DaemonMonitorHandler(endpoint=self._Gone(FileNotFoundError(2, "No such file or directory")), poll_interval=0.0)
        self._poll(monitor, monkeypatch, 100.0)
        assert monitor.session_gone is False  # one failure is not enough
        self._poll(monitor, monkeypatch, 103.0)
        assert monitor.session_gone is True

    def test_a_refused_connection_too(self, monkeypatch):
        monitor = DaemonMonitorHandler(endpoint=self._Gone(ConnectionRefusedError(111, "refused")), poll_interval=0.0)
        self._poll(monitor, monkeypatch, 100.0)
        self._poll(monitor, monkeypatch, 103.0)
        assert monitor.session_gone is True

    def test_a_busy_session_is_not_gone(self, monkeypatch):
        import socket

        monitor = DaemonMonitorHandler(endpoint=self._Gone(socket.timeout("timed out")), poll_interval=0.0)
        self._poll(monitor, monkeypatch, 100.0)
        self._poll(monitor, monkeypatch, 110.0)
        assert monitor.session_gone is False

    def test_the_monitor_says_so_and_fails(self, monkeypatch):
        from odatix.lib.parallel_job_handler import daemon_control, daemon_monitor

        def gone_run(handler):
            handler.session_gone = True

        monkeypatch.setattr(daemon_monitor.curses_ui, "run", gone_run)
        with pytest.raises(daemon_control.SessionGoneError) as raised:
            daemon_monitor.run_monitor(endpoint=_NoEndpoint(), session_label="7.s")
        assert "Session 7.s was stopped" in str(raised.value)
