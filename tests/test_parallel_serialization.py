"""Regression tests for daemon-safe parallel job serialization."""

import pytest

from odatix.lib.parallel_job_handler.job import ParallelJob
from odatix.lib.parallel_job_handler.serialization import (
    deserialize_command,
    job_to_payload,
    payload_to_job,
    serialize_command,
)


def _job(command):
    return ParallelJob(
        process=None, command=command, directory="work", generate_rtl=False,
        generate_command="", target="target", arch="architecture", display_name="job",
        status_file="status.log", progress_file="progress.log", tmp_dir="work", log_size_limit=123,
    )


def test_pipeline_round_trip_preserves_stages_and_job_metadata():
    job = _job({"10": [{"name": "route", "command": ["route", "report"]}], 2: [{"name": "synth", "command": "synth"}]})
    job.post_run_export = {"kind": "simulation"}
    job.step_tracking = {"state_file": "steps.yml"}
    job.step_names = ["synth", "route"]
    job.resume_step_index = 1

    restored = payload_to_job(job_to_payload(job))

    assert list(restored.command) == [2, 10]
    assert restored.command[10][0] == {"name": "route", "command": "route\nreport"}
    assert restored.post_run_export == {"kind": "simulation"}
    assert restored.step_names == ["synth", "route"]
    assert restored.resume_step_index == 1


def test_shell_command_round_trip_and_invalid_payloads():
    assert deserialize_command(serialize_command("make sim")) == "make sim"
    with pytest.raises(TypeError):
        serialize_command(["not", "supported"])
    with pytest.raises(ValueError):
        deserialize_command({"type": "pipeline", "stages": "bad"})
    with pytest.raises(ValueError):
        payload_to_job({"command": {"type": "unknown"}})