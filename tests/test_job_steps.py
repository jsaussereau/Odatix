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
Per-job step tracking (odatix.lib.job_steps).

A flow can be split into ordered steps that run as separate processes, so that a
run can stop at a given step and a later run picks up at the first step left to
do (generate the bitstream only for the implementations worth it, or resume
after a checkpoint).
"""

import pytest

import odatix.lib.job_steps as job_steps

STEPS = [
    {"name": "synthesis", "command": "synth"},
    {"name": "pnr", "command": "route"},
    {"name": "bitstream", "command": "bit"},
]


@pytest.fixture
def job_dir(tmp_path):
    return str(tmp_path / "job")


class TestState:
    def test_a_fresh_directory_has_no_step(self, job_dir):
        assert job_steps.completed_step_names(job_dir) == []
        assert job_steps.last_completed_step(job_dir) is None
        assert job_steps.resume_index(job_dir, ["synthesis"]) == 0

    def test_steps_are_recorded_in_order(self, job_dir):
        job_steps.record_completed_step(job_dir, "synthesis", flow="standard")
        job_steps.record_completed_step(job_dir, "pnr", flow="standard")
        assert job_steps.completed_step_names(job_dir) == ["synthesis", "pnr"]
        assert job_steps.last_completed_step(job_dir) == "pnr"
        assert job_steps.read_state(job_dir)["flow"] == "standard"

    def test_recording_a_step_again_drops_what_came_after_it(self, job_dir):
        for name in ("synthesis", "pnr", "bitstream"):
            job_steps.record_completed_step(job_dir, name)
        # Re-running place & route invalidates the bitstream that came from it.
        job_steps.record_completed_step(job_dir, "pnr")
        assert job_steps.completed_step_names(job_dir) == ["synthesis", "pnr"]

    def test_an_unreadable_state_is_treated_as_empty(self, job_dir, tmp_path):
        import os

        path = job_steps.state_file(job_dir)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write("{{{ not yaml")
        assert job_steps.completed_step_names(job_dir) == []


class TestResume:
    def test_only_a_leading_run_of_steps_counts(self, job_dir):
        job_steps.record_completed_step(job_dir, "synthesis")
        job_steps.record_completed_step(job_dir, "pnr")
        assert job_steps.resume_index(job_dir, ["synthesis", "pnr", "bitstream"]) == 2

    def test_a_changed_flow_restarts_at_the_first_difference(self, job_dir):
        job_steps.record_completed_step(job_dir, "synthesis")
        job_steps.record_completed_step(job_dir, "pnr")
        # The tool.yml gained a step between the two: everything after it is
        # stale, so the run restarts there rather than trusting the old state.
        assert job_steps.resume_index(job_dir, ["synthesis", "opt", "pnr"]) == 1

    def test_start_index_never_goes_past_the_rerun_point(self, job_dir):
        for name in ("synthesis", "pnr", "bitstream"):
            job_steps.record_completed_step(job_dir, name)
        assert job_steps.start_index(job_dir, STEPS) == 3
        # "--rerun-from pnr": synthesis stays reusable, the rest is re-run.
        assert job_steps.start_index(job_dir, STEPS, rerun_index=1) == 1


class TestSelectSteps:
    def test_until_truncates_the_list(self):
        selected, _, error = job_steps.select_steps(STEPS, until="pnr")
        assert error is None
        assert [step["name"] for step in selected] == ["synthesis", "pnr"]

    def test_rerun_from_returns_its_index(self):
        selected, rerun_index, error = job_steps.select_steps(STEPS, rerun_from="bitstream")
        assert error is None and rerun_index == 2

    def test_rerun_from_is_looked_up_within_the_selection(self):
        # "--until pnr --rerun-from bitstream" cannot re-run a dropped step.
        _, _, error = job_steps.select_steps(STEPS, until="pnr", rerun_from="bitstream")
        assert error is not None and "bitstream" in error

    def test_an_unknown_step_is_reported_with_the_valid_ones(self):
        _, _, error = job_steps.select_steps(STEPS, until="nope")
        assert error is not None
        assert "synthesis, pnr, bitstream" in error

    def test_no_selection_keeps_every_step(self):
        selected, rerun_index, error = job_steps.select_steps(STEPS)
        assert error is None
        assert len(selected) == len(STEPS)
        # Nothing is forced to re-run.
        assert rerun_index == len(STEPS)
