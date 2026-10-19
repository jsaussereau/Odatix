"""
What a simulation run does with the work it finds, how it is prepared, and what
reaches the results: regressions found by a new user going through the
simulation tutorials.
"""

import os

import pytest
import yaml

import odatix.lib.simulation_handler as simulation_handler
from odatix.lib.run_report import Category
from odatix.run import Run
from odatix.workspace import Workspace
from sim_fixtures import fake_simulators  # noqa: F401 (fixture)


def write(path, text):
    os.makedirs(os.path.dirname(str(path)), exist_ok=True)
    with open(str(path), "w", encoding="utf-8") as f:
        f.write(text)


######################################
# What is in cache
######################################

class TestJobCategory:
    def test_a_new_directory_is_new(self, tmp_path):
        assert simulation_handler.job_category(str(tmp_path / "job"), overwrite=False) == Category.NEW

    def test_only_a_simulation_that_succeeded_is_in_cache(self, tmp_path):
        job = tmp_path / "job"
        job.mkdir()
        # failed, or stopped: run again
        assert simulation_handler.job_category(str(job), overwrite=False) == Category.INCOMPLETE
        assert simulation_handler.job_category(str(job), overwrite=False, resume=True) == Category.RESUME
        (job / simulation_handler.SIM_DONE_FILENAME).write_text("done\n", encoding="utf-8")
        assert simulation_handler.job_category(str(job), overwrite=False) == Category.CACHED
        assert simulation_handler.job_category(str(job), overwrite=True) == Category.OVERWRITE


def _counter_run(**options):
    return Run(
        Workspace.open(), "simulation", simulations=["TB_Example_Counter_GHDL"],
        architectures=["Example_Counter_vhdl/16bits"], noask=True, **options
    )


@pytest.mark.integration
class TestFailedSimulation:
    def test_a_failed_simulation_runs_again(self, example_workspace):
        jobs = _counter_run().prepare().job_list
        tmp_dir = jobs[0].tmp_dir
        # The job ran and failed: no mark
        assert _counter_run().check().names(Category.INCOMPLETE, colored=False) == [
            "TB_Example_Counter_GHDL: Example_Counter_vhdl/16bits"
        ]
        # It succeeded (with another job, the run has something left to do)
        write(os.path.join(tmp_dir, simulation_handler.SIM_DONE_FILENAME), "done\n")
        run = Run(
            Workspace.open(), "simulation", simulations=["TB_Example_Counter_GHDL"],
            architectures=["Example_Counter_vhdl/16bits", "Example_Counter_vhdl/08bits"], noask=True,
        )
        assert run.check().names(Category.CACHED, colored=False) == [
            "TB_Example_Counter_GHDL: Example_Counter_vhdl/16bits"
        ]

    def test_resuming_keeps_the_directory_and_forgets_the_mark(self, example_workspace):
        jobs = _counter_run().prepare().job_list
        tmp_dir = jobs[0].tmp_dir
        write(os.path.join(tmp_dir, "kept.txt"), "kept\n")
        write(os.path.join(tmp_dir, simulation_handler.SIM_DONE_FILENAME), "done\n")
        _counter_run(overwrite=True, resume=True).prepare()
        assert os.path.isfile(os.path.join(tmp_dir, "kept.txt"))
        assert not os.path.isfile(os.path.join(tmp_dir, simulation_handler.SIM_DONE_FILENAME))


######################################
# Preparing a job
######################################

@pytest.mark.integration
class TestPreparation:
    def test_the_log_directory_exists_before_the_first_task(self, example_workspace):
        write(
            example_workspace / "odatix_userconfig" / "simulations" / "TB_Tee" / "_settings.yml",
            "tasks:\n  - name: main\n    commands:\n      - echo run | tee ${log_path}/sim.log\n",
        )
        run = Run(
            Workspace.open(), "simulation", simulations=["TB_Tee"],
            architectures=["Example_Counter_vhdl/08bits"], noask=True,
        )
        job = run.prepare().job_list[0]
        assert os.path.isdir(os.path.join(job.tmp_dir, "log"))

    def test_main_writes_the_configuration_into_the_testbench(self, example_workspace):
        # "__main__" with only a target file: the configuration itself is what
        # is written there, with the delimiters of the architecture.
        job = _counter_run().prepare().job_list[0]
        with open(os.path.join(job.tmp_dir, "tb", "tb_counter.vhdl"), encoding="utf-8") as f:
            assert "BITS : integer := 16" in f.read()

    def test_a_design_is_copied_into_the_simulation_directory(self, example_workspace):
        run = Run(
            Workspace.open(), "simulation", simulations=["TB_Example_Counter_Verilator"],
            architectures=["Example_Counter_chisel/16bits"], noask=True,
        )
        job = run.prepare().job_list[0]
        source = os.path.join(job.tmp_dir, "src", "main", "scala", "counter.scala")
        # The design is there, with the configuration written into it
        with open(source, encoding="utf-8") as f:
            assert "new Counter(BITS = 16)" in f.read()
        assert os.path.isfile(os.path.join(job.tmp_dir, "build.sbt"))


######################################
# Results
######################################

class TestResults:
    def test_a_failed_simulation_is_exported(self, tmp_path):
        import odatix.components.export_simulation_results as exp_sim_res

        class Jobs(object):
            job_list = [type("Job", (object,), {"tmp_dir": str(tmp_path / "work" / "sim" / "arch" / "conf")})()]

        os.makedirs(Jobs.job_list[0].tmp_dir)
        assert exp_sim_res.configure_simulation_job_exports(
            Jobs, work_root=str(tmp_path / "work"), sim_path=str(tmp_path), output_dir=str(tmp_path),
        ) == 1
        assert Jobs.job_list[0].post_run_export["on_failure"] is True

    def test_every_record_says_how_its_run_ended(self, tmp_path):
        import odatix.components.export_simulation_results as exp_sim_res

        def records():
            return [{"meta": {}, "metrics": {"cycles": None}}]

        run_dir = str(tmp_path)
        # A directory that does not say: nothing is made up
        assert exp_sim_res._with_status(records(), run_dir) == records()
        assert exp_sim_res._with_status(records(), run_dir, failed=True)[0]["metrics"]["sim_status"] == "failed"
        write(os.path.join(run_dir, simulation_handler.SIM_DONE_FILENAME), "done\n")
        assert exp_sim_res._with_status(records(), run_dir)[0]["metrics"]["sim_status"] == "passed"
        # What the simulation reports itself (a template does) is kept
        reported = [{"meta": {}, "metrics": {"sim_status": "failed"}}]
        assert exp_sim_res._with_status(reported, run_dir)[0]["metrics"]["sim_status"] == "failed"

    def test_a_text_metric_is_a_dimension_of_the_explorer(self, tmp_path):
        import odatix.explorer.core.query as query
        import odatix.explorer.core.schema as schema
        from odatix.explorer.core.store import ResultStore

        (tmp_path / "results_simulation.yml").write_text(yaml.safe_dump({"schema": 2, "units": {}, "results": [
            {"meta": {"type": "simulation", "simulation": "ghdl", "architecture": "counter", "configuration": "8"},
             "metrics": {"sim_status": "passed", "sim_errors": 0}},
            {"meta": {"type": "simulation", "simulation": "ghdl", "architecture": "counter", "configuration": "16"},
             "metrics": {"sim_status": "failed", "sim_errors": 3}},
        ]}))
        store = ResultStore()
        store.configure(tmp_path)
        dimensions, metrics = query.discover(store.dataframe(), store)
        assert dimensions["sim_status"] == ["failed", "passed"]
        assert "sim_status" not in metrics
        assert "sim_errors" in metrics
        selected = query.select_dataframe(store, filters={"sim_status": ["failed"]})
        assert selected[schema.COL_CONFIGURATION].astype(str).tolist() == ["16"]


######################################
# odatix migrate
######################################

class TestMigrate:
    def test_the_deprecated_keys_of_a_simulation_are_listed(self, example_workspace):
        import odatix.components.migrate as migrate

        write(
            example_workspace / "odatix_userconfig" / "simulations" / "TB_Old" / "_settings.yml",
            "use_parameters: Yes\nparam_target_file: tb/tb.vhdl\nstart_delimiter: '('\nstop_delimiter: ')'\n",
        )
        found = migrate.deprecated_simulation_keys(Workspace.open())
        assert [(os.path.basename(os.path.dirname(path)), keys) for path, keys in found] == [
            ("TB_Old", ["use_parameters", "param_target_file", "start_delimiter", "stop_delimiter"]),
        ]
        # Something is left to the user: the command says so
        assert migrate.report([], deprecated=found) is False

    def test_the_examples_use_no_deprecated_key(self, example_workspace):
        import odatix.components.migrate as migrate

        assert migrate.deprecated_simulation_keys(Workspace.open()) == []


######################################
# Python API
######################################

class TestSettingsAttributes:
    def test_an_unknown_setting_is_an_error(self):
        from odatix.workspace.simulations import SimulationSettings

        settings = SimulationSettings()
        with pytest.raises(AttributeError) as error:
            settings.testbenchh = {"top": "tb"}
        # The message names the settings there are
        assert '"testbenchh" is not a setting of SimulationSettings' in str(error.value)
        assert "testbench" in str(error.value)

    def test_declared_settings_and_mapping_keys_still_work(self):
        from odatix.workspace.simulations import SimulationSettings

        settings = SimulationSettings()
        settings.template = "ghdl"
        settings["my_own_key"] = 1
        assert settings.to_dict()["template"] == "ghdl"
        assert settings.extra == {"my_own_key": 1}
        settings.extra = {}
        assert settings.extra == {}
