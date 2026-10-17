# ********************************************************************** #
#                                Odatix                                  #
# ********************************************************************** #
#
# Copyright (C) 2022 Jonathan Saussereau
#
# This file is part of Odatix.
# Odatix is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Odatix is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Odatix. If not, see <https://www.gnu.org/licenses/>.
#

"""
One record per step: what a job directory split into steps exports.
"""

import os

import pytest
import yaml

import odatix.components.export_results as export_results


TARGET = "target"
ARCHITECTURE = "arch"
CONFIGURATION = "config"

# A metric read from the report of each step, one read from the whole job, and
# one belonging to a single step.
METRICS_DATA = {
    "metrics": {
        "LUT_count": {
            "type": "regex",
            "settings": {"file": "report/$step/utilization.rep", "pattern": "LUTs: ([0-9]+)", "group_id": 1},
            "format": "%.0f",
        },
        "Frequency": {
            "type": "regex",
            "settings": {"file": "frequency.txt", "pattern": "([0-9]+) MHz", "group_id": 1},
            "format": "%.0f",
        },
        "Bitstream_size": {
            "type": "regex",
            "step": "bitstream",
            "error_if_missing": False,
            "settings": {"file": "report/size.rep", "pattern": "size: ([0-9]+)", "group_id": 1},
            "format": "%.0f",
        },
    }
}


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


@pytest.fixture
def job(tmp_path):
    """A finished job directory, with the reports of a synthesis and a place & route."""
    job_path = tmp_path / TARGET / ARCHITECTURE / CONFIGURATION
    write(str(job_path / "log" / "status.log"), "Done: 100%")
    write(str(job_path / "frequency.txt"), "100 MHz")
    write(str(job_path / "report" / "synthesis" / "utilization.rep"), "LUTs: 10")
    write(str(job_path / "report" / "pnr" / "utilization.rep"), "LUTs: 12")
    return tmp_path


def set_steps(work_path, steps):
    job_path = work_path / TARGET / ARCHITECTURE / CONFIGURATION
    write(
        str(job_path / "log" / "steps.yml"),
        yaml.dump({"flow": "standard", "completed": [{"name": name, "timestamp": None} for name in steps]}),
    )


def export(work_path, units=None):
    return export_results.process_configuration(
        input=str(work_path),
        target=TARGET,
        architecture=ARCHITECTURE,
        configuration=CONFIGURATION,
        frequency=None,
        type="fmax_synthesis",
        result_key="fmax_synthesis",
        units=units if units is not None else {},
        metrics_data=METRICS_DATA,
        metrics_file="metrics.yml",
        use_benchmark=False,
        benchmark_file=None,
        tool="dummy",
        flow="standard",
    )


class TestStepRecords:
    def test_one_record_per_step(self, job):
        set_steps(job, ["synthesis", "pnr"])
        records = export(job)
        assert [record["meta"]["step"] for record in records] == ["synthesis", "pnr"]

    def test_a_metric_is_read_from_the_report_of_its_own_step(self, job):
        set_steps(job, ["synthesis", "pnr"])
        records = export(job)
        assert [record["metrics"]["LUT_count"] for record in records] == [10, 12]

    def test_a_metric_of_the_whole_job_is_repeated_in_every_record(self, job):
        set_steps(job, ["synthesis", "pnr"])
        records = export(job)
        assert [record["metrics"]["Frequency"] for record in records] == [100, 100]

    def test_the_last_step_is_flagged(self, job):
        set_steps(job, ["synthesis", "pnr"])
        records = export(job)
        assert [record["meta"]["_last_step"] for record in records] == [False, True]

    def test_the_step_index_follows_the_flow(self, job):
        set_steps(job, ["synthesis", "pnr"])
        records = export(job)
        assert [record["meta"]["_step_index"] for record in records] == [0, 1]

    def test_a_step_that_measured_nothing_of_its_own_gets_no_record(self, job):
        # "bitstream" writes no report: it would only repeat the metrics of the
        # job under another step name. It is the last step, so it keeps a record;
        # were it not, it would have none.
        set_steps(job, ["synthesis", "pnr", "bitstream"])
        records = export(job)
        assert [record["meta"]["step"] for record in records] == ["synthesis", "pnr", "bitstream"]
        assert records[-1]["metrics"]["LUT_count"] is None

        set_steps(job, ["synthesis", "bitstream", "pnr"])
        records = export(job)
        assert [record["meta"]["step"] for record in records] == ["synthesis", "pnr"]

    def test_a_job_without_steps_yields_a_single_record(self, job):
        records = export(job)
        assert len(records) == 1
        assert "step" not in records[0]["meta"]
        assert "_last_step" not in records[0]["meta"]

    def test_a_stopped_job_only_has_the_steps_it_ran(self, job):
        set_steps(job, ["synthesis"])
        records = export(job)
        assert [record["meta"]["step"] for record in records] == ["synthesis"]
        assert records[0]["meta"]["_last_step"] is True

    def test_a_metric_declared_for_a_step_stays_out_of_the_others(self, job):
        set_steps(job, ["synthesis", "pnr"])
        records = export(job)
        assert all("Bitstream_size" not in record["metrics"] for record in records)
