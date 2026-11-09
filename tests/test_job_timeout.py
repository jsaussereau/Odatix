"""
The timeout of the jobs of a run: what sets it, and how it reaches the daemon.
"""

import pytest

from odatix.lib.parallel_job_handler import serialization
from odatix.lib.parallel_job_handler.job import ParallelJob
from odatix.run import Run
from odatix.run.errors import RunError
from odatix.workspace import Workspace


def _job():
    return ParallelJob(
        process=None, command="true", directory=".", generate_rtl=False, generate_command="",
        target="t", arch="a", display_name="job", status_file="", progress_file="", tmp_dir=".",
        log_size_limit=10,
    )


def test_the_timeout_travels_with_the_job():
    job = _job()
    job.timeout = 90.0
    assert serialization.payload_to_job(serialization.job_to_payload(job)).timeout == 90.0
    job.timeout = None
    assert serialization.payload_to_job(serialization.job_to_payload(job)).timeout is None


def test_a_job_from_an_older_client_has_no_timeout():
    payload = serialization.job_to_payload(_job())
    del payload["timeout"]
    assert serialization.payload_to_job(payload).timeout is None


@pytest.fixture
def workspace(example_workspace):
    return Workspace.open(str(example_workspace))


def test_the_run_takes_its_timeout_from_the_option_then_the_settings_file(workspace, example_workspace):
    run = Run(workspace, "analysis", tool="verilator", check_eda_tool=False, quiet=True)
    assert run.job_timeout is None

    settings = example_workspace / run.settings_file
    settings.write_text("job_timeout: 30\n" + settings.read_text().replace("---\n", "", 1))
    assert run.job_timeout == 30.0

    run = Run(workspace, "analysis", tool="verilator", check_eda_tool=False, quiet=True, job_timeout="2.5")
    assert run.job_timeout == 2.5

    run = Run(workspace, "analysis", tool="verilator", check_eda_tool=False, quiet=True, job_timeout=0)
    assert run.job_timeout is None

    run = Run(workspace, "analysis", tool="verilator", check_eda_tool=False, quiet=True, job_timeout="soon")
    with pytest.raises(RunError):
        run.job_timeout


def test_a_wait_without_monitor_says_which_running_job_is_silent(tmp_path, capsys):
    import os
    import time

    from odatix.components import run_common

    quiet, busy = tmp_path / "quiet", tmp_path / "busy"
    for job_dir in (quiet, busy):
        (job_dir / "log").mkdir(parents=True)
        (job_dir / "log" / "tool.log").write_text("...")
    long_ago = time.time() - 3600
    os.utime(str(quiet / "log" / "tool.log"), (long_ago, long_ago))

    class Session(object):
        def jobs(self):
            return [
                {"id": 0, "name": "quiet", "status": "running", "elapsed": "01:10:00", "tmp_dir": str(quiet)},
                {"id": 1, "name": "busy", "status": "running", "elapsed": "01:10:00", "tmp_dir": str(busy)},
                {"id": 2, "name": "over", "status": "success", "elapsed": "00:01:00", "tmp_dir": str(busy)},
            ]

    run_common._say_running_jobs(Session(), None, time.time(), "run")
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("  quiet: running for 01:10:00, nothing written to ") and "for 60 min" in lines[0]
    assert lines[1] == "  busy: running for 01:10:00"
