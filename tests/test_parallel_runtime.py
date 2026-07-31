"""Unit tests for daemon selection, job progress and the headless job API."""

import os
import re
from types import SimpleNamespace

import pytest

import odatix.lib.parallel_job_handler.daemon_control as daemon_control
import odatix.lib.parallel_job_handler.handler_core as handler_core
from odatix.lib.parallel_job_handler.job import ParallelJob


def _job(name="job", progress_file="", status_file=""):
    return ParallelJob(
        process=None, command="echo test", directory="work", generate_rtl=False, generate_command="",
        target="target", arch="architecture", display_name=name, status_file=status_file,
        progress_file=progress_file, tmp_dir="work", log_size_limit=100, status="idle",
    )


def test_daemon_session_names_paths_and_workspace_detection(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    nested = workspace / "a" / "b"
    nested.mkdir(parents=True)
    (workspace / "odatix.yml").write_text("{}")

    assert daemon_control.detect_workspace_root(str(nested)) == str(workspace)
    assert daemon_control._session_slug(" tty / 2 @ host ") == "tty-2-host"
    assert daemon_control._session_slug("... ") is None
    assert daemon_control._state_filename_for_session(None) == daemon_control.DAEMON_STATE_FILE
    assert daemon_control._log_filename_for_session("night run").endswith("night-run" + daemon_control.DAEMON_LOG_SUFFIX)
    assert daemon_control.get_daemon_paths(str(nested), "night run")["workspace_root"] == str(workspace)

    monkeypatch.setattr(daemon_control, "_generate_default_session_name", lambda host: "no_tty.host")
    active = [{"session_name": "no_tty.host"}, {"session_name": "no_tty.host.2"}]
    assert daemon_control._unique_default_session_name("host", active) == "no_tty.host.3"


def test_daemon_session_selector_and_state_helpers():
    first = {"pid": "12", "host": "localhost", "port": "9001", "session_name": "build"}
    second = {"pid": 13, "host": "remote", "port": 9002, "session_id": "13.deploy"}
    daemons = [first, second]

    assert daemon_control._state_key(first) == (12, "localhost", 9001)
    assert daemon_control._session_id_from_state(first) == "12.build"
    assert daemon_control._session_name_from_state(second) == "deploy"
    assert daemon_control._resolve_session_selector(daemons, "build") is first
    assert daemon_control._resolve_session_selector(daemons, "dep") is second
    assert daemon_control._resolve_session_selector(daemons, "missing", allow_missing=True) is None
    with pytest.raises(daemon_control.MultipleDaemonsError):
        daemon_control._resolve_session_selector(daemons, "")
    with pytest.raises(daemon_control.DaemonControlError):
        daemon_control._resolve_session_selector([], "missing")


def test_daemon_api_request_and_liveness(monkeypatch):
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"ok": true}'

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["method"] = request.method
        captured["body"] = request.data
        assert timeout in (0.5, 0.6)
        return Response()

    monkeypatch.setattr(daemon_control.urllib.request, "urlopen", fake_urlopen)
    assert daemon_control._api_request("http://host:9", "POST", "/jobs", {"count": 2}, timeout=0.5) == {"ok": True}
    assert captured == {"url": "http://host:9/jobs", "method": "POST", "body": b'{"count": 2}'}
    assert daemon_control.daemon_is_alive({"host": "host", "port": 9}) is True


def test_parallel_job_extracts_progress_and_scales_steps(tmp_path):
    progress_file = tmp_path / "progress.log"
    progress_file.write_text("progress=12\nprogress=150\n")
    job = _job(progress_file=str(progress_file))
    ParallelJob.set_patterns(re.compile(r"progress=(\d+)"))
    job.step_names = ["prepare", "run", "report"]
    job.current_step_index = 1
    job.resume_step_index = 0

    assert ParallelJob._extract_int_from_pattern("first 8\nlast 42", re.compile(r"last (\d+)")) == 42
    assert ParallelJob._extract_int_from_pattern("unmatched 7", re.compile(r"value=(\d+)")) == 7
    assert ParallelJob._extract_int_from_pattern("", None) is None
    assert job.get_progress() == pytest.approx((100 + 100) / 3)


def test_parallel_job_reads_fmax_and_ignores_stale_status_files(tmp_path):
    status_file = tmp_path / "status.log"
    progress_file = tmp_path / "progress.log"
    status_file.write_text("fmax state 40 2 4\n")
    progress_file.write_text("progress=80\n")
    job = _job(progress_file=str(progress_file), status_file=str(status_file))
    job.progress_mode = "fmax"
    ParallelJob.set_patterns(re.compile(r"progress=(\d+)"), re.compile(r"fmax (state) (\d+) (\d+) (\d+)"))

    assert ParallelJob._extract_fmax_status(status_file.read_text(), ParallelJob.status_file_pattern) == (40, 2, 4)
    assert job.get_progress_fmax() == 60
    job.current_step_started_at = os.path.getmtime(status_file) + 1
    assert job._read_status_file(str(status_file)) is None


def test_parallel_job_pause_and_resume_send_process_group_signals(monkeypatch):
    job = _job()
    job.process = SimpleNamespace(pid=123)
    job.status = "running"
    job.start_time = 10.0
    calls = []
    monkeypatch.setattr("odatix.lib.parallel_job_handler.job.os.getpgid", lambda pid: pid + 1)
    monkeypatch.setattr("odatix.lib.parallel_job_handler.job.os.killpg", lambda pid, signal: calls.append((pid, signal)))
    clock = iter((20.0, 25.0))
    monkeypatch.setattr("odatix.lib.parallel_job_handler.job.time.time", lambda: next(clock))

    job.pause()
    job.resume()

    assert job.status == "running"
    assert job.start_time == 15.0
    assert job.stop_time is None
    assert len(calls) == 2


def test_headless_handler_snapshot_log_controls_and_commands():
    first, second = _job("first"), _job("second")
    first.log_history = ["one", "two", "three"]
    handler = handler_core.ParallelJobHandler([first, second], nb_jobs=2, format_yaml="")
    handler.set_logs_height(2)
    handler.select_job(0)
    snapshot = handler.snapshot(logs_offset=1, logs_limit=1)

    assert snapshot["handler"]["job_count"] == 2
    assert snapshot["logs"]["lines"] == ["two"]
    handler.scroll_logs(0, -50)
    assert first.log_position == 0 and first.autoscroll is False
    handler.logs_end(0)
    assert first.log_position == 1 and first.autoscroll is True
    handler.enqueue_command("set_logs_height", height=5)
    handler.enqueue_command("select", job_id=1)
    handler.process_pending_commands()
    assert handler._headless_logs_height == 5
    assert handler.selected_job_index == 1
    handler.configure_runtime(nb_jobs=0, process_group=False, auto_exit=True, log_size_limit=25)
    assert (handler.nb_jobs, handler.process_group, handler.auto_exit, handler.log_size_limit) == (1, False, True, 25)
    with pytest.raises(IndexError):
        handler.select_job(9)