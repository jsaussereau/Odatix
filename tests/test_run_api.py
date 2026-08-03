"""
Tests for odatix.run: the API a script, the command line and the graphical
interface all start a run through.

What matters here is what makes it usable from a script: every path comes from
the workspace, what a run cannot do raises instead of stopping the interpreter,
and what it says is kept.
"""

import os

import pytest

from odatix.run import Run, RunError, RunOptions
from odatix.run.planner import JobPlanner
from odatix.workspace import Workspace


######################################
# Where a run works
######################################

class TestRunPaths:
    """A run started from a script names nothing: the workspace knows it all."""

    @pytest.mark.parametrize("mode,settings_file,work_path", [
        ("fmax_synthesis", "fmax_synthesis_settings.yml", "fmax_synthesis"),
        ("custom_freq_synthesis", "custom_freq_synthesis_settings.yml", "custom_freq_synthesis"),
        ("simulation", "simulations_settings.yml", "simulations"),
        ("workflow", "workflow_settings.yml", "workflows"),
    ])
    def test_paths_come_from_the_workspace(self, example_workspace, mode, settings_file, work_path):
        run = Run(Workspace.open(), mode)
        assert os.path.basename(run.settings_file) == settings_file
        assert os.path.basename(run.work_path) == work_path
        # Each job type works in its own directory, under the work directory.
        assert run.work_path.startswith(Workspace.open().paths.work_path)

    def test_a_run_can_be_pointed_elsewhere(self, example_workspace):
        run = Run(Workspace.open(), "fmax_synthesis", settings_file="my.yml", work_path="/tmp/work")
        assert run.settings_file == "my.yml"
        assert run.work_path == "/tmp/work"

    def test_the_work_directory_of_a_workspace_opened_from_elsewhere(self, example_workspace, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path.parent)
        run = Run(Workspace.open(root=str(tmp_path)), "fmax_synthesis")
        assert run.work_path == os.path.join(str(tmp_path), "work", "fmax_synthesis")

    def test_the_mode_can_be_named_as_the_command_does(self, example_workspace):
        assert Run(Workspace.open(), "fmax").mode == "fmax_synthesis"
        assert Run(Workspace.open(), "analyze").mode == "analysis"


######################################
# What a run is asked to do
######################################

class TestRunOptions:
    def test_options_are_read_as_their_type(self):
        options = RunOptions(overwrite="Yes", log_size_limit="42")
        assert options.overwrite is True
        assert options.log_size_limit == 42

    def test_keyword_arguments_become_options(self, example_workspace):
        run = Run(Workspace.open(), "fmax_synthesis", overwrite=True, nb_jobs="auto")
        assert run.options.overwrite is True
        assert run.options.nb_jobs == "auto"

    def test_a_script_is_never_asked_to_confirm(self, example_workspace):
        assert Run(Workspace.open(), "fmax_synthesis").options.noask is True

    def test_a_command_asks_when_its_settings_file_says_so(self, example_workspace):
        from odatix.run.cli import command_run

        assert command_run("fmax_synthesis").options.noask is False

    def test_the_tools_of_an_analysis_stay_a_list(self, example_workspace):
        run = Run(Workspace.open(), "analysis", tool=["vivado", "yosys"])
        assert run.options.tool == ["vivado", "yosys"]


######################################
# Checking
######################################

class TestCheck:
    def test_a_run_knows_what_it_would_do(self, example_workspace):
        run = Run(Workspace.open(), "custom_freq_synthesis", tool="dummy")
        plan = run.check()
        assert plan.run_count() > 0
        assert len(run.jobs) == plan.run_count()
        assert run.was_checked

    def test_checking_twice_does_not_check_twice(self, example_workspace):
        run = Run(Workspace.open(), "custom_freq_synthesis", tool="dummy")
        assert run.checked() is run.checked()

    def test_an_unusable_settings_file_raises(self, example_workspace):
        run = Run(Workspace.open(), "custom_freq_synthesis", tool="dummy", settings_file="nope.yml")
        with pytest.raises(RunError):
            run.check()

    def test_an_unknown_tool_raises_instead_of_exiting(self, example_workspace):
        run = Run(Workspace.open(), "fmax_synthesis", tool="no_such_tool")
        with pytest.raises(RunError) as raised:
            run.check()
        assert "no_such_tool" in str(raised.value)

    def test_what_the_run_said_is_kept(self, example_workspace):
        run = Run(Workspace.open(), "fmax_synthesis", tool="no_such_tool")
        with pytest.raises(RunError) as raised:
            run.check()
        assert raised.value.errors()
        assert run.reporter.errors

    def test_an_unknown_mode_is_refused(self, example_workspace):
        from odatix.workspace.errors import NotFoundError

        with pytest.raises(NotFoundError):
            Run(Workspace.open(), "no_such_mode")


######################################
# What to do with a job directory
######################################

class TestJobPlanner:
    def planner(self, tmp_path, **kwargs):
        settings = dict(
            work_path=str(tmp_path), work_log_path="log", status_filename="status.log",
            valid_status="Success",
        )
        settings.update(kwargs)
        return JobPlanner(**settings)

    def job_directory(self, tmp_path, status=None):
        directory = tmp_path / "job"
        (directory / "log").mkdir(parents=True)
        if status is not None:
            (directory / "log" / "status.log").write_text(status)
        return str(directory)

    def test_a_directory_that_does_not_exist_is_a_new_job(self, tmp_path):
        state, _ = self.planner(tmp_path).classify_job(str(tmp_path / "nope"), '"job"')
        assert state == "new"

    def test_a_finished_job_is_cached(self, tmp_path):
        directory = self.job_directory(tmp_path, status="Success")
        assert self.planner(tmp_path).classify_job(directory, '"job"')[0] == "cached"

    def test_a_finished_job_is_run_again_when_overwriting(self, tmp_path):
        directory = self.job_directory(tmp_path, status="Success")
        planner = self.planner(tmp_path, overwrite=True)
        assert planner.classify_job(directory, '"job"')[0] == "overwrite"

    def test_a_job_that_did_not_finish_is_incomplete(self, tmp_path):
        directory = self.job_directory(tmp_path, status="started")
        assert self.planner(tmp_path).classify_job(directory, '"job"')[0] == "incomplete"

    def test_a_flow_that_is_not_stepped_has_no_step_decision(self, tmp_path):
        assert self.planner(tmp_path).steps_decision(str(tmp_path)) is None

    def test_every_requested_step_done_is_cached(self, tmp_path, monkeypatch):
        import odatix.lib.job_steps as job_steps

        monkeypatch.setattr(job_steps, "resume_index", lambda directory, steps: len(steps))
        planner = self.planner(tmp_path, requested_steps=["synth", "pnr"])
        assert planner.steps_decision(str(tmp_path)) == "cached"

    def test_some_steps_left_is_resumed(self, tmp_path, monkeypatch):
        import odatix.lib.job_steps as job_steps

        monkeypatch.setattr(job_steps, "resume_index", lambda directory, steps: 1)
        planner = self.planner(tmp_path, requested_steps=["synth", "pnr"])
        assert planner.steps_decision(str(tmp_path)) == "resume"

    def test_rerunning_from_a_step_forgets_what_follows(self, tmp_path, monkeypatch):
        import odatix.lib.job_steps as job_steps

        monkeypatch.setattr(job_steps, "resume_index", lambda directory, steps: len(steps))
        planner = self.planner(tmp_path, requested_steps=["synth", "pnr"], rerun_step_index=0)
        assert planner.steps_decision(str(tmp_path)) == "new"

    def test_a_job_a_session_is_running_is_left_to_it(self, tmp_path, monkeypatch):
        import odatix.run.planner as planner_module

        directory = self.job_directory(tmp_path)
        monkeypatch.setattr(planner_module, "list_daemon_jobs", lambda workspace_root=None: [
            {"tmp_dir": directory, "status": "running", "session_id": "s1"},
        ])
        state, entry = self.planner(tmp_path).classify_job(directory, '"job"')
        assert state == "daemon"
        assert entry["session_id"] == "s1"

    def test_a_job_a_session_failed_is_taken_over(self, tmp_path, monkeypatch):
        import odatix.run.planner as planner_module

        directory = self.job_directory(tmp_path)
        monkeypatch.setattr(planner_module, "list_daemon_jobs", lambda workspace_root=None: [
            {"tmp_dir": directory, "status": "failed", "session_id": "s1"},
        ])
        assert self.planner(tmp_path).classify_job(directory, '"job"')[0] == "new"

    def test_the_plan_only_holds_what_will_be_run(self, tmp_path):
        from odatix.lib.run_report import Category

        planner = self.planner(tmp_path)
        assert planner.record("a", "new") is True
        assert planner.record("b", "cached") is False
        assert planner.plan.names(Category.NEW, colored=False) == ["a"]
        assert planner.plan.names(Category.CACHED, colored=False) == ["b"]
