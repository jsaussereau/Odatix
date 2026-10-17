"""Tests for the curses monitor's delta polling.

`DaemonMonitorHandler` mirrors a remote session so the legacy curses UI can
render it. It asks `/status` for a delta (`since`/`epoch`), which means the
mirror -- not the response -- holds the job list: a poll that returns two jobs
must not make the other ninety-eight disappear. These tests pin that, and the
one case where jobs may legitimately go away (a full snapshot).
"""

import pytest

from odatix.lib.parallel_job_handler.daemon_monitor import DaemonMonitorHandler
from odatix.lib.parallel_job_handler.handler_core import ParallelJobHandler

from test_monitor_snapshot import FakeJob


class RecordingEndpoint:
    """An `Endpoint` that answers `/status` straight from a local handler."""

    def __init__(self, handler):
        self.handler = handler
        self.paths = []

    def request(self, method, path, payload=None, timeout=None):
        self.paths.append(path)
        assert method == "GET"
        head, _, query = path.partition("?")
        assert head == "/status"
        params = {}
        for item in query.split("&"):
            if item:
                key, _, value = item.partition("=")
                params[key] = value
        return self.handler.snapshot(
            logs_job_id=int(params.get("logs_job_id", -1)),
            since=params.get("since"),
            epoch=params.get("epoch"),
        )


@pytest.fixture
def remote():
    handler = ParallelJobHandler([FakeJob("job%d" % index) for index in range(5)], nb_jobs=2)
    handler.job_count = 5
    return handler


@pytest.fixture
def monitor(remote):
    endpoint = RecordingEndpoint(remote)
    monitor = DaemonMonitorHandler(endpoint=endpoint, poll_interval=0.0)
    monitor.endpoint = endpoint
    return monitor


def names(monitor):
    return [job.display_name for job in monitor.job_list]


class TestDeltaPolling:
    def test_first_poll_is_full(self, monitor):
        assert monitor.endpoint.paths == ["/status?logs_job_id=-1"]
        assert names(monitor) == ["job0", "job1", "job2", "job3", "job4"]

    def test_next_poll_asks_for_a_delta(self, monitor):
        monitor._sync_snapshot(force=True)
        assert "since=" in monitor.endpoint.paths[-1]
        assert "epoch=" in monitor.endpoint.paths[-1]

    def test_unchanged_jobs_survive_an_empty_delta(self, monitor):
        monitor._sync_snapshot(force=True)
        assert names(monitor) == ["job0", "job1", "job2", "job3", "job4"]

    def test_changed_job_is_applied_without_losing_the_others(self, monitor, remote):
        monitor._sync_snapshot(force=True)
        remote.job_list[2].status = "running"
        remote.job_list[2].progress = 42
        monitor._sync_snapshot(force=True)

        assert names(monitor) == ["job0", "job1", "job2", "job3", "job4"]
        assert monitor.job_list[2].status == "running"
        assert monitor.job_list[2].progress == 42
        assert monitor.running_job_list == [monitor.job_list[2]]

    def test_new_job_appears_through_a_delta(self, monitor, remote):
        monitor._sync_snapshot(force=True)
        remote.job_list.append(FakeJob("job5"))
        remote.job_count = 6
        monitor._sync_snapshot(force=True)

        assert names(monitor) == ["job0", "job1", "job2", "job3", "job4", "job5"]

    def test_removed_jobs_disappear_on_the_forced_full_snapshot(self, monitor, remote):
        monitor._sync_snapshot(force=True)
        # The daemon rerolls its epoch when its list shrinks, which is what
        # forces the full snapshot a delta could never express.
        del remote.job_list[3:]
        remote.job_count = 3
        monitor._sync_snapshot(force=True)

        assert names(monitor) == ["job0", "job1", "job2"]
        assert monitor.job_count == 3
        assert monitor.selected_job_index < 3

    def test_aggregates_come_from_every_job_not_the_delta(self, monitor, remote):
        monitor._sync_snapshot(force=True)
        remote.job_list[0].status = "running"
        remote.running_job_list = [remote.job_list[0]]
        monitor._sync_snapshot(force=True)

        assert monitor._remote_total_jobs == 5
        assert monitor._remote_running == 1

    def test_empty_session_falls_back_to_the_placeholder(self, remote):
        del remote.job_list[:]
        remote.job_count = 0
        monitor = DaemonMonitorHandler(endpoint=RecordingEndpoint(remote), poll_interval=0.0)

        assert monitor.job_count == 1
        assert names(monitor) == ["Waiting for jobs..."]


def test_log_requests_do_not_carry_the_job_list(remote, monitor):
    """Fetching a job's log must not drag every job along with it.

    `_sync_selected_logs` only reads "logs" from the reply, but `/status`
    serializes the whole job list by default -- at a few hundred jobs that made
    every selection change cost more than a full poll, which is exactly what
    the delta polling exists to avoid.
    """
    monitor._sync_snapshot(force=True)
    monitor.selected_job_index = 3
    monitor._sync_selected_logs()

    log_paths = [path for path in monitor.endpoint.paths if "logs_job_id=3" in path]
    assert log_paths, "selecting a job should fetch its log"
    for path in log_paths:
        assert "include_jobs=0" in path

    full = remote.snapshot(logs_job_id=3, logs_offset=0, logs_limit=-1)
    lean = remote.snapshot(logs_job_id=3, logs_offset=0, logs_limit=-1, include_jobs=False)
    assert full["jobs"] and lean["jobs"] == []
    # A caller must not read the empty list as "the jobs are gone".
    assert lean["full"] is False
    assert lean["logs"] == full["logs"]
    assert lean["handler"]["job_count"] == full["handler"]["job_count"]
