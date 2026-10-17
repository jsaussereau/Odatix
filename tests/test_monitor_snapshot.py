"""Tests for the incremental snapshot the monitor polls.

`ParallelJobHandler.snapshot(since=..., epoch=...)` is what keeps the GUI
monitor usable on large sessions: instead of shipping every job on every tick,
it returns only the jobs whose public state changed, plus aggregates covering
all of them. These tests pin the delta protocol -- getting it subtly wrong
would leave the monitor showing stale rows rather than failing loudly.
"""

import pytest

from odatix.lib.parallel_job_handler.handler_core import ParallelJobHandler


class FakeJob:
    """The attributes `snapshot()` reads off a job, and nothing else."""

    kind = "job"

    def __init__(self, name):
        self.display_name = name
        self.status = "queued"
        self.progress = 0
        self.directory = "/d"
        self.tmp_dir = "/t"
        self.target = "target"
        self.arch = "arch"
        self.start_time = None
        self.stop_time = None
        self.log_history = []
        self.log_position = 0
        self.autoscroll = True


@pytest.fixture
def handler():
    handler = ParallelJobHandler([FakeJob("job%d" % index) for index in range(5)], nb_jobs=2)
    handler.job_count = 5
    return handler


class TestSnapshotDelta:
    def test_first_snapshot_is_full(self, handler):
        snap = handler.snapshot(logs_job_id=-1)
        assert snap["full"] is True
        assert [job["id"] for job in snap["jobs"]] == [0, 1, 2, 3, 4]
        assert snap["epoch"]

    def test_unchanged_session_returns_no_jobs(self, handler):
        first = handler.snapshot(logs_job_id=-1)
        second = handler.snapshot(logs_job_id=-1, since=first["revision"], epoch=first["epoch"])

        assert second["full"] is False
        assert second["jobs"] == []
        assert second["revision"] == first["revision"]

    def test_only_changed_jobs_come_back(self, handler):
        first = handler.snapshot(logs_job_id=-1)
        handler.job_list[2].status = "running"
        handler.job_list[2].progress = 42

        second = handler.snapshot(logs_job_id=-1, since=first["revision"], epoch=first["epoch"])

        assert second["full"] is False
        assert [job["id"] for job in second["jobs"]] == [2]
        assert second["revision"] > first["revision"]

    def test_a_delta_is_not_replayed_twice(self, handler):
        first = handler.snapshot(logs_job_id=-1)
        handler.job_list[1].status = "running"
        second = handler.snapshot(logs_job_id=-1, since=first["revision"], epoch=first["epoch"])
        third = handler.snapshot(logs_job_id=-1, since=second["revision"], epoch=second["epoch"])

        assert [job["id"] for job in second["jobs"]] == [1]
        assert third["jobs"] == []

    def test_foreign_epoch_falls_back_to_a_full_snapshot(self, handler):
        first = handler.snapshot(logs_job_id=-1)

        # A revision from another daemon: revisions restart at 0 with every
        # handler, so honouring it would silently skip real updates.
        stale = handler.snapshot(logs_job_id=-1, since=first["revision"], epoch="not-this-handler")

        assert stale["full"] is True
        assert len(stale["jobs"]) == 5

    def test_removing_a_job_invalidates_incremental_views(self, handler):
        first = handler.snapshot(logs_job_id=-1)
        handler.job_list.pop()

        second = handler.snapshot(logs_job_id=-1, since=first["revision"], epoch=first["epoch"])

        # No per-job revision can express a removal, so clients are sent back to
        # a full snapshot through a fresh epoch.
        assert second["full"] is True
        assert second["epoch"] != first["epoch"]
        assert len(second["jobs"]) == 4


class TestSnapshotAggregates:
    def test_counts_cover_every_job_even_on_a_delta(self, handler):
        first = handler.snapshot(logs_job_id=-1)
        handler.job_list[0].status = "running"
        handler.job_list[1].status = "success"
        handler.job_list[2].status = "failed"

        snap = handler.snapshot(logs_job_id=-1, since=first["revision"], epoch=first["epoch"])

        assert len(snap["jobs"]) == 3
        assert snap["handler"]["counts"] == {
            "total": 5, "running": 1, "queued": 2, "done": 1, "failed": 1,
        }

    def test_overall_progress_averages_every_job(self, handler):
        handler.job_list[0].progress = 100
        handler.job_list[1].progress = 50

        snap = handler.snapshot(logs_job_id=-1)

        assert snap["handler"]["overall_progress"] == 30

    def test_status_tables_are_published_to_the_client(self, handler):
        snap = handler.snapshot(logs_job_id=-1)
        handler_state = snap["handler"]

        assert handler_state["status_buckets"]["running"] == ["running", "starting", "export"]
        assert handler_state["status_sort_priority"]["running"] == 0
        assert handler_state["first_job_id"] == 0
