"""Tests for odatix.lib.architecture_handler and odatix.lib.simulation_handler.

The integration tests run against a copy of the packaged example workspace
(fixture `example_workspace`), without any EDA tool installed: they only cover
job preparation (architecture/simulation resolution), not synthesis itself.
"""

import os
import shutil

import pytest

import odatix.lib.hard_settings as hard_settings
from odatix.lib.architecture_handler import Architecture, ArchitectureHandler
from odatix.lib.settings import OdatixSettings
from odatix.lib.simulation_handler import SimulationHandler


######################################
# get_basic (architecture request parsing)
######################################

class TestGetBasic:
    def test_simple_configuration(self):
        arch, param_dir, config, display, param_dir_work, config_dir_work, domains = ArchitectureHandler.get_basic(
            "counter/08bits"
        )
        assert arch == "counter/08bits"
        assert param_dir == "counter"
        assert config == "08bits"
        assert display == "counter/08bits"
        assert config_dir_work == "08bits"
        assert domains == []

    def test_txt_suffix_is_stripped(self):
        arch, _, config, _, _, _, _ = ArchitectureHandler.get_basic("counter/08bits.txt")
        assert arch == "counter/08bits"
        assert config == "08bits"

    def test_trailing_slash_is_stripped(self):
        arch, _, _, _, _, _, _ = ArchitectureHandler.get_basic("counter/08bits/")
        assert arch == "counter/08bits"

    def test_param_domain_requests(self):
        _, _, _, display, _, config_dir_work, domains = ArchitectureHandler.get_basic(
            "counter/08bits+corner/tt"
        )
        assert domains == ["corner/tt"]
        assert config_dir_work == "08bits+corner_tt"
        assert "corner:tt" in display

    def test_multi_target_display_name(self):
        _, _, _, display, _, _, _ = ArchitectureHandler.get_basic("c/cfg", target="fpga1", only_one_target=False)
        assert display.endswith("(fpga1)")

    def test_spaces_are_removed(self):
        arch, _, _, _, _, _, domains = ArchitectureHandler.get_basic("counter/08bits + corner/tt")
        assert arch == "counter/08bits"
        assert domains == ["corner/tt"]


######################################
# Integration: architecture resolution on the example workspace
######################################

def make_arch_handler(work_path="work/fmax_synthesis", overwrite=False):
    return ArchitectureHandler(
        work_path=work_path,
        arch_path="odatix_userconfig/architectures",
        script_path=OdatixSettings.odatix_eda_tools_path,
        log_path=hard_settings.work_log_path,
        work_rtl_path=hard_settings.work_rtl_path,
        work_script_path=hard_settings.work_script_path,
        work_log_path=hard_settings.work_log_path,
        work_report_path=hard_settings.work_report_path,
        process_group=False,
        command="",
        eda_target_filename=os.path.realpath(os.path.join("odatix_userconfig", "targets", "target_vivado.yml")),
        fmax_status_filename=hard_settings.fmax_status_filename,
        frequency_search_filename=hard_settings.frequency_search_filename,
        param_settings_filename=hard_settings.param_settings_filename,
        valid_status=hard_settings.valid_status,
        valid_frequency_search=hard_settings.valid_frequency_search,
        forced_fmax_lower_bound=None,
        forced_fmax_upper_bound=None,
        forced_custom_freq_list=None,
        overwrite=overwrite,
    )


TARGET = "xc7a100t-csg324-1"


@pytest.mark.integration
class TestArchitectureResolution:
    def test_single_configuration(self, example_workspace):
        handler = make_arch_handler()
        instances = handler.get_architectures(
            ["Example_Counter_verilog/04bits"], [TARGET], run_mode="fmax", timestamp="ts"
        )
        assert len(instances) == 1
        arch = instances[0]
        assert isinstance(arch, Architecture)
        assert arch.target == TARGET
        assert arch.top_level_module == "counter"
        assert arch.clock_signal == "clock"
        assert arch.use_parameters is True
        # target-specific bounds from the example settings file
        # (bounds are handled as strings internally)
        assert int(arch.fmax_lower_bound) == 250
        assert int(arch.fmax_upper_bound) == 900

    def test_wildcard_expands_configurations(self, example_workspace):
        handler = make_arch_handler()
        instances = handler.get_architectures(
            ["Example_Counter_verilog/*"], [TARGET], run_mode="fmax", timestamp="ts"
        )
        names = sorted(a.arch_name for a in instances)
        assert len(instances) >= 2
        assert any("04bits" in n for n in names)

    def test_unknown_architecture_is_rejected(self, example_workspace):
        handler = make_arch_handler()
        instances = handler.get_architectures(
            ["No_Such_Arch/cfg"], [TARGET], run_mode="fmax", timestamp="ts"
        )
        assert instances == []
        assert handler.get_valid_arch_count() == 0

    def test_unknown_configuration_is_rejected(self, example_workspace):
        handler = make_arch_handler()
        instances = handler.get_architectures(
            ["Example_Counter_verilog/13bits"], [TARGET], run_mode="fmax", timestamp="ts"
        )
        assert instances == []

    def test_custom_freq_mode_creates_one_instance_per_frequency(self, example_workspace):
        handler = make_arch_handler(work_path="work/custom_freq_synthesis")
        instances = handler.get_architectures(
            ["Example_Counter_verilog/04bits"], [TARGET], run_mode="custom_freq", timestamp="ts"
        )
        # example settings define custom_freq_synthesis list [50, 100] for this target
        assert len(instances) == 2
        assert sorted(a.target_frequency for a in instances) == [50, 100]

    def test_get_architectures_without_target_file(self, example_workspace):
        # RTL analysis passes eda_target_filename=None (no target definition file)
        # and a single generic target: get_architectures must still resolve the
        # architectures instead of crashing on the missing file, but only when
        # allow_missing_target_file is set (analysis flow).
        handler = make_arch_handler(work_path="work/analysis")
        handler.eda_target_filename = None
        instances = handler.get_architectures(
            ["Example_Counter_verilog/04bits"],
            [hard_settings.default_analysis_target],
            run_mode="default",
            timestamp="ts",
            allow_missing_target_file=True,
        )
        assert len(instances) == 1
        assert instances[0].target == hard_settings.default_analysis_target

    def test_get_architectures_missing_target_file_errors_for_synthesis(self, example_workspace):
        # Synthesis must NOT tolerate a missing target file: without
        # allow_missing_target_file, get_architectures exits.
        handler = make_arch_handler(work_path="work/fmax_synthesis")
        handler.eda_target_filename = None
        with pytest.raises(SystemExit):
            handler.get_architectures(
                ["Example_Counter_verilog/04bits"],
                [TARGET],
                run_mode="fmax",
                timestamp="ts",
            )


######################################
# Missing design_path is reported, not silently ignored
######################################
#
# copytree() walks the source directory (os.walk); if design_path does not
# exist, os.walk silently yields nothing and copytree does not raise, so a
# missing/mistyped design_path used to produce an empty work directory with no
# warning at all. Each job-preparation flow (synthesis, analysis, simulation)
# must check design_path itself and report it as an error.

@pytest.mark.integration
class TestMissingDesignPath:
    def _chisel_instance(self, work_path="work/missing_design_path"):
        handler = make_arch_handler(work_path=work_path)
        instances = handler.get_architectures(
            ["Example_Counter_chisel/04bits"], [TARGET], run_mode="fmax", timestamp="ts"
        )
        assert len(instances) == 1
        arch_instance = instances[0]
        assert arch_instance.design_path is not None  # sanity: this arch uses generate_rtl
        arch_instance.design_path = "this_design_path_does_not_exist"
        return arch_instance

    def test_synthesis_common_reports_missing_design_path(self, example_workspace, capsys):
        import odatix.components.synthesis_common as synthesis_common

        arch_instance = self._chisel_instance()
        prepare_job = synthesis_common.build_prepare_synthesis_job(
            arch_handler=make_arch_handler(),
            arch_path="odatix_userconfig/architectures",
            tool="vivado",
            log_size_limit=300,
            debug=False,
            timestamp="ts",
            progress_mode="fmax",
            script_name="test",
        )
        job_list = []
        prepare_job(arch_instance, job_list)
        assert job_list == []
        assert "does not exist" in capsys.readouterr().out

    def test_run_analysis_reports_missing_design_path(self, example_workspace, capsys):
        import odatix.components.run_analysis as run_analysis

        arch_instance = self._chisel_instance()
        tool_context = run_analysis.load_tool_context("vivado", "odatix_userconfig")
        context = run_analysis.prepare_analysis(
            run_config_settings_filename="odatix_userconfig/analysis_settings.yml",
            arch_path="odatix_userconfig/architectures",
            tool="vivado",
            work_path="work/analysis",
            overwrite=False,
            noask=True,
            exit_when_done=False,
            log_size_limit=300,
            nb_jobs=4,
            tool_context=tool_context,
            job_list=[],
            timestamp="ts",
        )
        job_list = context["job_list"]
        context["prepare_job"](arch_instance)
        assert job_list == []
        assert "does not exist" in capsys.readouterr().out

    def test_run_simulations_reports_missing_design_path(self, example_workspace, capsys):
        import odatix.components.run_simulations as run_simulations

        # The packaged example only has the chisel (generate_rtl / design_path)
        # simulation commented out: enable it in a dedicated settings file.
        settings_path = "odatix_userconfig/tmp_simulations_settings.yml"
        with open(settings_path, "w") as f:
            f.write(
                "overwrite: No\n"
                "ask_continue: No\n"
                "exit_when_done: No\n"
                "log_size_limit: 300\n"
                "nb_jobs: 8\n"
                "simulations:\n"
                "  - TB_Example_Counter_Verilator:\n"
                "    - Example_Counter_chisel/04bits\n"
            )

        simulation_instances, prepare_job, job_list, *_ = run_simulations.check_settings(
            run_config_settings_filename=settings_path,
            arch_path="odatix_userconfig/architectures",
            sim_path="odatix_userconfig/simulations",
            work_path="work/simulations",
            overwrite=False,
            noask=True,
            exit_when_done=False,
            log_size_limit=300,
            nb_jobs=4,
        )
        sim_instance = next(
            (s for s in simulation_instances if s.architecture.design_path is not None), None
        )
        assert sim_instance is not None
        sim_instance.architecture.design_path = "this_design_path_does_not_exist"
        prepare_job(sim_instance)
        assert job_list == []
        assert "does not exist" in capsys.readouterr().out


######################################
# Job-preparation progress bar (run_common.PrepareProgress)
######################################

class TestPrepareProgress:
    def teardown_method(self):
        from odatix.components import run_common
        run_common.reset_prepare_progress()

    def test_counts_and_shared_state(self):
        import io
        from odatix.components import run_common

        progress = run_common.PrepareProgress(total=4, stream=io.StringIO())
        progress.update(ok=True)
        progress.update(ok=True)
        progress.update(ok=False)
        progress.finish()

        state = run_common.get_prepare_progress()
        assert state == {"label": "Preparing jobs", "total": 4, "done": 3, "ok": 2, "failed": 1, "active": False}

    def test_non_tty_prints_single_summary_line(self):
        import io
        from odatix.components import run_common

        buf = io.StringIO()  # StringIO.isatty() is False, like the GUI log buffer
        progress = run_common.PrepareProgress(total=2, stream=buf)
        progress.update(ok=True)
        progress.update(ok=False)
        progress.finish()
        assert buf.getvalue().strip() == "Preparing jobs: 1/2 prepared (1 failed)"

    def test_tty_bar_has_green_and_red_sections(self):
        import io
        from odatix.components import run_common

        class FakeTTY(io.StringIO):
            def isatty(self):
                return True

        stream = FakeTTY()
        progress = run_common.PrepareProgress(total=2, stream=stream)
        progress.update(ok=True)
        progress.update(ok=False)
        progress.finish()
        out = stream.getvalue()
        assert "\033[92m" in out  # green (ok) section
        assert "\033[91m" in out  # red (failed) section
        assert "✔ 1" in out
        assert "✘ 1" in out
        assert "2/2" in out

    def test_tty_redraws_live_independently_of_job_completion(self):
        # A background thread must keep redrawing the bar on its own cadence,
        # decoupled from job completion: this is what makes the CLI bar look
        # live even when every job finishes almost instantly (previously the
        # bar only ever appeared once, at finish()).
        import io
        import time
        from odatix.components import run_common

        class FakeTTY(io.StringIO):
            def isatty(self):
                return True

        stream = FakeTTY()
        progress = run_common.PrepareProgress(total=3, stream=stream)
        assert progress._redraw_thread is not None
        progress.update(ok=True)
        progress.update(ok=True)
        progress.update(ok=True)
        # All jobs are already "done", but nothing has told the bar to stop:
        # the redraw thread must still be ticking on its own.
        writes_before = stream.getvalue().count("\r")
        time.sleep(run_common.PrepareProgress.REDRAW_INTERVAL * 3)
        writes_after = stream.getvalue().count("\r")
        assert writes_after > writes_before

        progress.finish()
        assert progress._redraw_thread.is_alive() is False

    def test_run_prepare_loop_detects_failures_from_job_list(self):
        import io
        from unittest import mock
        from odatix.components import run_common

        job_list = []

        def build_job(i):
            # failed preparations do not append to job_list (like the real
            # prepare_job implementations, e.g. on a missing design_path)
            if i != 1:
                job_list.append(i)

        with mock.patch("sys.stdout", io.StringIO()):
            run_common.run_prepare_loop([0, 1, 2], build_job, job_list)

        state = run_common.get_prepare_progress()
        assert state["done"] == 3
        assert state["ok"] == 2
        assert state["failed"] == 1

    def test_reset_clears_state(self):
        import io
        from odatix.components import run_common

        run_common.PrepareProgress(total=1, stream=io.StringIO())
        assert run_common.get_prepare_progress() is not None
        run_common.reset_prepare_progress()
        assert run_common.get_prepare_progress() is None


######################################
# If every job fails to build, the monitor/daemon session must not launch
######################################
#
# design_path (or any other) failures happen *after* the initial checklist
# confirmation (confirm_valid_jobs), while each job is actually being built.
# abort_if_empty_job_list() is the guard that stops the session from launching
# with zero jobs when every one of them failed this way.

class TestAbortIfEmptyJobList:
    def test_raises_on_empty_list(self, capsys):
        from odatix.components.run_common import abort_if_empty_job_list

        with pytest.raises(SystemExit):
            abort_if_empty_job_list([], script_name="test")
        assert "None of the selected jobs could be prepared" in capsys.readouterr().out

    def test_does_not_raise_when_jobs_exist(self):
        from odatix.components.run_common import abort_if_empty_job_list

        abort_if_empty_job_list(["a job"], script_name="test")  # must not raise


@pytest.mark.integration
class TestSessionAbortsWhenAllJobsFail:
    def test_synthesis_common_prepare_synthesis_jobs_aborts(self, example_workspace):
        import odatix.components.synthesis_common as synthesis_common

        handler = make_arch_handler(work_path="work/missing_design_path")
        instances = handler.get_architectures(
            ["Example_Counter_chisel/04bits"], [TARGET], run_mode="fmax", timestamp="ts"
        )
        instances[0].design_path = "this_design_path_does_not_exist"
        prepare_job = synthesis_common.build_prepare_synthesis_job(
            arch_handler=handler,
            arch_path="odatix_userconfig/architectures",
            tool="vivado",
            log_size_limit=300,
            debug=False,
            timestamp="ts",
            progress_mode="fmax",
            script_name="test",
        )
        with pytest.raises(SystemExit):
            synthesis_common.prepare_synthesis_jobs(
                architecture_instances=instances,
                prepare_job=prepare_job,
                job_list=[],
                process_group=handler.process_group,
                tool_settings_file="tool.yml",
                exit_when_done=False,
                log_size_limit=300,
                nb_jobs=4,
                script_name="test",
            )

    def test_run_analysis_prepare_synthesis_aborts(self, example_workspace):
        import odatix.components.run_analysis as run_analysis

        handler = make_arch_handler(work_path="work/analysis")
        instances = handler.get_architectures(
            ["Example_Counter_chisel/04bits"], [hard_settings.default_analysis_target], run_mode="default", timestamp="ts",
            allow_missing_target_file=True,
        )
        instances[0].design_path = "this_design_path_does_not_exist"

        tool_context = run_analysis.load_tool_context("vivado", "odatix_userconfig")
        context = run_analysis.prepare_analysis(
            run_config_settings_filename="odatix_userconfig/analysis_settings.yml",
            arch_path="odatix_userconfig/architectures",
            tool="vivado",
            work_path="work/analysis",
            overwrite=False,
            noask=True,
            exit_when_done=False,
            log_size_limit=300,
            nb_jobs=4,
            tool_context=tool_context,
            job_list=[],
            timestamp="ts",
        )
        with pytest.raises(SystemExit):
            run_analysis.prepare_synthesis(
                architecture_instances=[instances[0]],
                prepare_job=context["prepare_job"],
                job_list=context["job_list"],
                tool_settings_file=context["tool_settings_file"],
                arch_handler=context["arch_handler"],
                exit_when_done=context["exit_when_done"],
                log_size_limit=context["log_size_limit"],
                nb_jobs=context["nb_jobs"],
            )

    def test_run_simulations_prepare_simulations_aborts(self, example_workspace):
        import odatix.components.run_simulations as run_simulations

        settings_path = "odatix_userconfig/tmp_simulations_settings_abort.yml"
        with open(settings_path, "w") as f:
            f.write(
                "overwrite: No\n"
                "ask_continue: No\n"
                "exit_when_done: No\n"
                "log_size_limit: 300\n"
                "nb_jobs: 8\n"
                "simulations:\n"
                "  - TB_Example_Counter_Verilator:\n"
                "    - Example_Counter_chisel/04bits\n"
            )
        simulation_instances, prepare_job, job_list, exit_when_done, log_size_limit, nb_jobs, _plan = run_simulations.check_settings(
            run_config_settings_filename=settings_path,
            arch_path="odatix_userconfig/architectures",
            sim_path="odatix_userconfig/simulations",
            work_path="work/simulations",
            overwrite=False,
            noask=True,
            exit_when_done=False,
            log_size_limit=300,
            nb_jobs=4,
        )
        for sim_instance in simulation_instances:
            sim_instance.architecture.design_path = "this_design_path_does_not_exist"

        with pytest.raises(SystemExit):
            run_simulations.prepare_simulations(
                simulation_instances=simulation_instances,
                prepare_job=prepare_job,
                job_list=job_list,
                exit_when_done=exit_when_done,
                log_size_limit=log_size_limit,
                nb_jobs=nb_jobs,
            )


######################################
# Integration: simulation resolution on the example workspace
######################################

@pytest.mark.integration
class TestSimulationResolution:
    def make_sim_handler(self):
        return SimulationHandler(
            work_path="work/simulations",
            arch_path="odatix_userconfig/architectures",
            sim_path="odatix_userconfig/simulations",
            work_rtl_path=hard_settings.work_rtl_path,
            work_script_path=hard_settings.work_script_path,
            work_log_path=hard_settings.work_log_path,
            log_path=hard_settings.work_log_path,
            param_settings_filename=hard_settings.param_settings_filename,
            sim_settings_filename=hard_settings.sim_settings_filename,
            sim_makefile_filename="Makefile",
            overwrite=False,
        )

    def test_resolves_example_simulation(self, example_workspace):
        handler = self.make_sim_handler()
        simulations = handler.get_simulations(
            [{"TB_Example_Counter_Verilator": ["Example_Counter_verilog/04bits"]}]
        )
        assert len(simulations) == 1
        assert handler.get_valid_sim_count() == 1

    def test_unknown_simulation_is_rejected(self, example_workspace):
        handler = self.make_sim_handler()
        simulations = handler.get_simulations([{"No_Such_TB": ["Example_Counter_verilog/04bits"]}])
        assert simulations == []

    def test_a_simulation_without_settings_file_uses_the_makefile(self, example_workspace):
        # No "_settings.yml": no task, so the Makefile "sim" rule is what runs.
        handler = self.make_sim_handler()
        simulations = handler.get_simulations(
            [{"TB_Example_Counter_Verilator": ["Example_Counter_verilog/04bits"]}]
        )
        assert simulations[0].tasks == []
        assert simulations[0].progress_regex == hard_settings.sim_status_pattern.pattern

    def test_tasks_and_progress_are_read_from_the_settings_file(self, example_workspace):
        os.makedirs("odatix_userconfig/simulations/TB_Tasks", exist_ok=True)
        with open("odatix_userconfig/simulations/TB_Tasks/_settings.yml", "w") as f:
            f.write(
                "use_parameters: No\n"
                "progress:\n"
                "  file: progress.txt\n"
                "  regex: 'Progress: ([0-9]+)'\n"
                "tasks:\n"
                "  - name: main\n"
                "    commands:\n"
                "      - 'echo hello'\n"
            )
        handler = self.make_sim_handler()
        simulations = handler.get_simulations([{"TB_Tasks": ["Example_Counter_verilog/04bits"]}])

        assert len(simulations) == 1
        instance = simulations[0]
        assert [task["name"] for task in instance.tasks] == ["main"]
        assert instance.progress_file == "progress.txt"
        assert instance.progress_regex == "Progress: ([0-9]+)"
        # A task-based simulation needs no Makefile.
        assert not os.path.isfile("odatix_userconfig/simulations/TB_Tasks/Makefile")

    def test_a_simulation_without_task_nor_makefile_is_rejected(self, example_workspace):
        os.makedirs("odatix_userconfig/simulations/TB_Empty", exist_ok=True)
        with open("odatix_userconfig/simulations/TB_Empty/_settings.yml", "w") as f:
            f.write("use_parameters: No\n")
        handler = self.make_sim_handler()
        assert handler.get_simulations([{"TB_Empty": ["Example_Counter_verilog/04bits"]}]) == []


######################################
# Simulation commands
######################################

@pytest.mark.integration
class TestSimulationCommand:
    def _instance(self, example_workspace, settings, sim_name):
        import odatix.lib.simulation_handler as simulation_handler

        os.makedirs("odatix_userconfig/simulations/" + sim_name, exist_ok=True)
        with open("odatix_userconfig/simulations/" + sim_name + "/_settings.yml", "w") as f:
            f.write(settings)
        handler = simulation_handler.SimulationHandler(
            work_path="work/simulations",
            arch_path="odatix_userconfig/architectures",
            sim_path="odatix_userconfig/simulations",
            work_rtl_path=hard_settings.work_rtl_path,
            work_script_path=hard_settings.work_script_path,
            work_log_path=hard_settings.work_log_path,
            log_path=hard_settings.work_log_path,
            param_settings_filename=hard_settings.param_settings_filename,
            sim_settings_filename=hard_settings.sim_settings_filename,
            sim_makefile_filename="Makefile",
            overwrite=False,
        )
        instances = handler.get_simulations([{sim_name: ["Example_Counter_verilog/04bits"]}])
        assert len(instances) == 1
        return instances[0]

    def test_without_task_the_legacy_make_command_is_used(self, example_workspace):
        import odatix.components.run_simulations as run_simulations

        # No task: the Makefile is what runs, so borrow the example's one.
        os.makedirs("odatix_userconfig/simulations/TB_Cmd_Legacy", exist_ok=True)
        shutil.copy(
            "odatix_userconfig/simulations/TB_Example_Counter_GHDL/Makefile",
            "odatix_userconfig/simulations/TB_Cmd_Legacy/Makefile",
        )
        instance = self._instance(example_workspace, "use_parameters: No\n", "TB_Cmd_Legacy")

        command = run_simulations.build_simulation_command(instance)
        assert isinstance(command, str)
        assert command.startswith("make sim")
        assert 'TOP_LEVEL_MODULE="counter"' in command

    def test_command_placeholders_are_substituted(self, example_workspace):
        import odatix.components.run_simulations as run_simulations

        instance = self._instance(
            example_workspace,
            "use_parameters: No\n"
            "tasks:\n"
            "  - name: main\n"
            "    commands:\n"
            "      - 'run ${architecture}/${configuration} --top ${top_level_module}'\n",
            "TB_Cmd_Vars",
        )
        command = run_simulations.build_simulation_command(instance)
        assert command == "run Example_Counter_verilog/04bits --top counter"

    def test_a_multi_task_graph_becomes_execution_stages(self, example_workspace):
        import odatix.components.run_simulations as run_simulations

        instance = self._instance(
            example_workspace,
            "use_parameters: No\n"
            "tasks:\n"
            "  - name: compile\n"
            "    commands:\n"
            "      - 'echo compile'\n"
            "  - name: main\n"
            "    dependencies:\n"
            "      - compile\n"
            "    commands:\n"
            "      - 'echo run'\n",
            "TB_Cmd_Graph",
        )
        os.makedirs(instance.tmp_dir, exist_ok=True)
        # Several tasks: the job runs the wosit execution stages, not a command.
        command = run_simulations.build_simulation_command(instance)
        assert not isinstance(command, str)
        assert len(command) >= 2

    def test_a_task_graph_without_main_is_rejected(self, example_workspace):
        import odatix.components.run_simulations as run_simulations

        instance = self._instance(
            example_workspace,
            "use_parameters: No\n"
            "tasks:\n"
            "  - name: build\n"
            "    commands:\n"
            "      - 'echo build'\n",
            "TB_Cmd_NoMain",
        )
        assert run_simulations.build_simulation_command(instance) is None

    def test_platform_specific_tasks_select_one_implementation(self, example_workspace):
        import sys

        import odatix.components.run_simulations as run_simulations

        instance = self._instance(
            example_workspace,
            "use_parameters: No\n"
            "tasks:\n"
            "  - name: main\n"
            "    platforms: " + sys.platform + "\n"
            "    commands:\n"
            "      - 'echo this_platform'\n"
            "  - name: main\n"
            "    commands:\n"
            "      - 'echo default'\n",
            "TB_Cmd_Platform",
        )
        assert run_simulations.build_simulation_command(instance) == "echo this_platform"
