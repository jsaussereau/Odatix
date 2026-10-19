"""
Lifecycle of the job processes, with real processes: pausing, killing and
stopping jobs, and what each signal reaches (see process_control).
"""

import os
import signal
import sys
import threading
import time

import pytest

import odatix.lib.parallel_job_handler.handler_core as handler_core
from odatix.lib.parallel_job_handler import process_control
from odatix.lib.parallel_job_handler.job import ParallelJob

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals")


def _job(tmp_path, command, generate_command=""):
    return ParallelJob(
        process=None, command=command, directory=str(tmp_path), generate_rtl=bool(generate_command),
        generate_command=generate_command, target="target", arch="architecture", display_name="job",
        status_file="", progress_file="", tmp_dir=str(tmp_path), log_size_limit=100,
    )


def _handler(job, process_group=True):
    handler = handler_core.ParallelJobHandler([job], nb_jobs=1, process_group=process_group, format_yaml="")
    handler._headless_initialized = True
    return handler


def _tick_until(handler, condition, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        with handler._lock:
            handler._update_jobs_state()
        if condition():
            return True
        time.sleep(0.05)
    return False


def _alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def _wait_for_file(path, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if os.path.isfile(path) and open(path, encoding="utf-8").read().strip():
            return open(path, encoding="utf-8").read().strip()
        time.sleep(0.02)
    raise AssertionError("{} was never written".format(path))


def test_a_job_in_its_own_group_is_started_apart_from_the_handler(tmp_path):
    job = _job(tmp_path, "sleep 30")
    handler = _handler(job)
    handler.start_job(job)
    try:
        assert job.own_group is True
        assert os.getpgid(job.process.pid) == job.process.pid
        assert os.getpgid(job.process.pid) != os.getpgid(0)
    finally:
        handler.terminate_all_jobs(timeout=2)


def test_a_paused_job_can_be_stopped(tmp_path):
    # SIGTERM stays pending on a stopped process: killing a paused job used to
    # leave it there, suspended, forever.
    job = _job(tmp_path, "sleep 30")
    handler = _handler(job)
    handler.start_job(job)
    handler.pause_job(0)
    assert job.status == "paused"

    handler.kill_or_cancel_job(0)

    assert job.status == "killed"
    assert job in handler._retired_jobs
    assert _tick_until(handler, lambda: job.process.returncode is not None)
    assert job.process.returncode == -signal.SIGTERM
    assert handler._stopping_jobs == []


def test_killing_a_job_without_its_own_group_spares_the_handler(tmp_path):
    # Without a group of its own the job shares the handler's: signaling the
    # group, as the handler used to, killed the handler (here: pytest).
    pid_file = tmp_path / "tool.pid"
    job = _job(tmp_path, "sleep 30 & echo $! > tool.pid; wait")
    handler = _handler(job, process_group=False)
    handler.start_job(job)
    tool_pid = int(_wait_for_file(str(pid_file)))
    try:
        assert job.own_group is False
        assert os.getpgid(job.process.pid) == os.getpgid(0)

        handler.kill_or_cancel_job(0)

        assert job.status == "killed"
        assert _tick_until(handler, lambda: job.process.returncode is not None)
        # Only the shell was signaled: what the tool started is the tool's own
        # business, as process_group: false asks.
        assert _alive(tool_pid)
        assert any("left running on purpose" in line for line in job.log_history)
    finally:
        if _alive(tool_pid):
            os.kill(tool_pid, signal.SIGKILL)


def test_a_job_can_be_killed_while_it_is_starting(tmp_path):
    marker = tmp_path / "ran"
    job = _job(tmp_path, "touch ran", generate_command="sleep 30")
    handler = _handler(job)
    handler.start_job(job)
    assert job.status == "starting"

    handler.kill_or_cancel_job(0)

    assert job.status == "killed"
    assert _tick_until(handler, lambda: job.process.returncode is not None)
    # The job command never runs once its generation was killed.
    _tick_until(handler, lambda: False, timeout=0.3)
    assert not marker.exists()
    assert job.status == "killed"


def test_killing_a_job_starts_the_next_queued_one(tmp_path):
    first, second = _job(tmp_path, "sleep 30"), _job(tmp_path, "sleep 30")
    handler = handler_core.ParallelJobHandler([first, second], nb_jobs=1, format_yaml="")
    handler._initialize_headless()
    assert (first.status, second.status) == ("running", "queued")
    try:
        handler.kill_or_cancel_job(0)
        assert second.status == "running"
    finally:
        handler.terminate_all_jobs(timeout=2)


def test_a_job_ignoring_the_request_to_stop_is_killed(tmp_path):
    job = _job(tmp_path, "trap '' TERM; while :; do sleep 0.05; done")
    handler = _handler(job)
    handler.start_job(job)
    time.sleep(0.2)  # let the shell install its trap

    with handler._lock:
        assert process_control.request_stop(job, timeout=0.2)
        handler._stopping_jobs.append(job)

    assert _tick_until(handler, lambda: job.process.returncode is not None)
    assert job.process.returncode == -signal.SIGKILL


def test_terminating_all_jobs_waits_without_the_lock(tmp_path):
    job = _job(tmp_path, "trap '' TERM; while :; do sleep 0.05; done")
    handler = _handler(job)
    handler.start_job(job)
    time.sleep(0.2)

    stopper = threading.Thread(target=handler.terminate_all_jobs, kwargs={"timeout": 1.0})
    stopper.start()
    time.sleep(0.2)
    # The API and the monitor need the lock while the jobs are being stopped.
    acquired = handler._lock.acquire(timeout=0.3)
    if acquired:
        handler._lock.release()
    stopper.join(timeout=5)

    assert acquired
    assert not stopper.is_alive()
    assert job.process.returncode == -signal.SIGKILL


def test_signals_reach_the_group_only_for_a_job_that_owns_one(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(process_control.os, "killpg", lambda group, sig: calls.append(("group", group, sig)))
    monkeypatch.setattr(process_control.os, "kill", lambda pid, sig: calls.append(("pid", pid, sig)))
    monkeypatch.setattr(process_control.os, "getpgid", lambda pid: 7 if pid else 1)

    class _Running:
        pid = 42

        def poll(self):
            return None

    job = _job(tmp_path, "true")
    job.process = _Running()

    job.own_group = True
    process_control.send(job, signal.SIGTERM)
    job.own_group = False
    process_control.send(job, signal.SIGTERM)
    # Defense in depth: a group that turns out to be the handler's is never signaled.
    job.own_group = True
    monkeypatch.setattr(process_control.os, "getpgid", lambda pid: 1)
    process_control.send(job, signal.SIGTERM)

    assert calls == [("group", 7, signal.SIGTERM), ("pid", 42, signal.SIGTERM), ("pid", 42, signal.SIGTERM)]


def test_stopping_sends_term_before_cont(monkeypatch, tmp_path):
    sent = []
    monkeypatch.setattr(process_control, "send", lambda job, sig: sent.append(sig) or True)

    class _Running:
        pid = 42

        def poll(self):
            return None

    job = _job(tmp_path, "true")
    job.process = _Running()
    process_control.request_stop(job)

    assert sent == [signal.SIGTERM, signal.SIGCONT]
