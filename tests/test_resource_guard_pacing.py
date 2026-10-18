"""
How fast the resource guard acts, and what it writes in the job log.

On a loaded machine, a guard acting on every sample paused a job, saw the load
drop (because of that very pause), resumed it, and started over every few
seconds, writing "paused by user" each time.
"""

import sys
import types

import pytest

from odatix.lib.parallel_job_handler import handler_core
from odatix.lib.parallel_job_handler.handler_core import (
    ParallelJobHandler,
    RESOURCE_GUARD_MIN_PAUSE,
    RESOURCE_GUARD_PAUSE_SAMPLES,
    RESOURCE_GUARD_RESUME_SAMPLES,
)
from odatix.lib.parallel_job_handler.job import ParallelJob

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="no SIGSTOP/SIGCONT on Windows")


class _Job(object):
    takes_a_slot = True

    def __init__(self, name):
        self.display_name = name
        self.status = "running"
        self.calls = []

    def pause(self, by="user", detail=None):
        self.calls.append(("pause", by, detail))
        self.status = "paused"

    def resume(self, by="user", detail=None):
        self.calls.append(("resume", by, detail))
        self.status = "running"


@pytest.fixture
def machine(monkeypatch):
    """A machine whose load and clock the test sets."""
    monkeypatch.setattr(handler_core, "_resource_guard_unavailable", [None])
    state = types.SimpleNamespace(cpu=10.0, mem=10.0, now=1000.0)
    psutil = types.ModuleType("psutil")
    psutil.cpu_percent = lambda interval=None: state.cpu
    psutil.virtual_memory = lambda: types.SimpleNamespace(percent=state.mem)
    monkeypatch.setitem(sys.modules, "psutil", psutil)
    import time as real_time

    clock = types.SimpleNamespace(**dict((name, getattr(real_time, name)) for name in dir(real_time) if not name.startswith("_")))
    clock.time = lambda: state.now
    monkeypatch.setattr(handler_core, "time", clock)
    return state


def _guarded(jobs):
    handler = ParallelJobHandler([], resource_guard=True, cpu_limit=90, mem_limit=90, resource_check_interval=0.0)
    handler.running_job_list = list(jobs)
    return handler


def _sample(handler, machine, count=1, step=2.0):
    for _ in range(count):
        machine.now += step
        handler._check_resource_guard_unlocked()


class TestPausing:
    def test_a_single_spike_pauses_nothing(self, machine):
        job = _Job("a")
        handler = _guarded([job])
        machine.cpu = 99.0
        _sample(handler, machine, RESOURCE_GUARD_PAUSE_SAMPLES - 1)
        assert job.status == "running"

    def test_a_lasting_overload_pauses_the_last_job_started(self, machine):
        first, last = _Job("first"), _Job("last")
        handler = _guarded([first, last])
        machine.cpu = 99.0
        _sample(handler, machine, RESOURCE_GUARD_PAUSE_SAMPLES)
        assert (first.status, last.status) == ("running", "paused")

    def test_the_log_says_the_guard_did_it_and_why(self, machine):
        job = _Job("a")
        handler = _guarded([job])
        machine.cpu = 99.0
        _sample(handler, machine, RESOURCE_GUARD_PAUSE_SAMPLES)
        action, by, detail = job.calls[0]
        assert (action, by) == ("pause", "resource guard")
        assert "CPU usage too high" in detail and "99% CPU" in detail


class TestResuming:
    def _paused(self, machine):
        job = _Job("a")
        handler = _guarded([job])
        machine.cpu = 99.0
        _sample(handler, machine, RESOURCE_GUARD_PAUSE_SAMPLES)
        assert job.status == "paused"
        return handler, job

    def test_one_calm_sample_does_not_resume(self, machine):
        handler, job = self._paused(machine)
        machine.cpu = 10.0
        _sample(handler, machine, 1, step=RESOURCE_GUARD_MIN_PAUSE)
        assert job.status == "paused"

    def test_a_calm_stretch_resumes_once_the_minimal_pause_is_over(self, machine):
        handler, job = self._paused(machine)
        machine.cpu = 10.0
        _sample(handler, machine, RESOURCE_GUARD_RESUME_SAMPLES, step=1.0)
        assert job.status == "paused"  # calm long enough, but paused too recently
        _sample(handler, machine, 1, step=RESOURCE_GUARD_MIN_PAUSE)
        assert job.status == "running"
        assert job.calls[-1][:2] == ("resume", "resource guard")

    def test_a_load_in_the_hysteresis_band_resumes_nothing(self, machine):
        handler, job = self._paused(machine)
        machine.cpu = 88.0  # under the limit, above the resume limit
        _sample(handler, machine, RESOURCE_GUARD_RESUME_SAMPLES + 5, step=RESOURCE_GUARD_MIN_PAUSE)
        assert job.status == "paused"

    def test_no_oscillation_on_a_loaded_machine(self, machine):
        # The load drops whenever the job is paused and comes back with it:
        # what used to be a pause/resume every two samples.
        job = _Job("a")
        handler = _guarded([job])
        for _ in range(60):  # two minutes of samples
            machine.cpu = 99.0 if job.status == "running" else 40.0
            _sample(handler, machine)
        pauses = [call for call in job.calls if call[0] == "pause"]
        assert len(pauses) <= 120 / RESOURCE_GUARD_MIN_PAUSE

    def test_turning_the_guard_off_says_so(self, machine):
        handler, job = self._paused(machine)
        handler.configure_runtime(resource_guard=False)
        assert job.calls[-1] == ("resume", "resource guard", "auto-pause turned off")


class TestJobLog:
    def test_a_user_pause_still_says_user(self):
        assert ParallelJob._control_message("paused", "user", None) == "Job paused by user"

    def test_the_guard_pause_says_resource_guard(self):
        text = ParallelJob._control_message("paused", "resource guard", "system CPU usage too high")
        assert text == "Job paused by resource guard: system CPU usage too high"
