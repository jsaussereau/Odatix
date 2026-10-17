"""
A clear and consistent command line: the former spellings it still accepts,
the default eda tool, the targets a run is told, "odatix results <type>", and
the way it reports.
"""

import argparse
import os
import shutil

import pytest

import odatix.lib.printc as printc
import odatix.odatix_main as odatix_main
from odatix.run import Run, RunError
from odatix.workspace import Workspace

needs_tclsh = pytest.mark.skipif(shutil.which("tclsh") is None, reason="the dummy tool runs tclsh")


def workspace_with(tmp_path, monkeypatch, settings="", target_files=()):
    """A workspace whose odatix.yml says `settings`, with a target file per tool given."""
    (tmp_path / "odatix.yml").write_text("workspace: odatix\n" + settings)
    targets = tmp_path / "odatix_userconfig" / "targets"
    targets.mkdir(parents=True)
    for tool in target_files:
        (targets / ("target_" + tool + ".yml")).write_text("targets:\n  - some_target\n")
    monkeypatch.chdir(tmp_path)
    return Workspace.open()


######################################
# Former spellings
######################################

class TestNormalizeArgv:
    def test_a_current_command_line_is_left_alone(self):
        assert odatix_main.normalize_argv(["fmax", "-t", "vivado"]) == (["fmax", "-t", "vivado"], [])

    def test_root_flags_come_before_the_command(self):
        argv, _warnings = odatix_main.normalize_argv(["-v", "res_synth"])
        assert argv == ["-v", "results", "synth"]

    @pytest.mark.parametrize("argv, expected", [
        (["results"], ["results", "all"]),
        (["results", "-w", "work"], ["results", "all", "-w", "work"]),
        (["results", "sim", "-w", "work"], ["results", "sim", "-w", "work"]),
        (["results", "-h"], ["results", "-h"]),
    ])
    def test_results_without_a_type_is_all(self, argv, expected):
        assert odatix_main.normalize_argv(argv) == (expected, [])

    def test_a_former_command_is_rewritten_and_said_so(self):
        argv, warnings = odatix_main.normalize_argv(["res_simulation", "-r", "out"])
        assert argv == ["results", "sim", "-r", "out"]
        assert len(warnings) == 1 and '"odatix results sim"' in warnings[0]

    def test_init_flag_becomes_the_init_command(self):
        argv, warnings = odatix_main.normalize_argv(["--init"])
        assert argv == ["init"]
        assert warnings

    def test_a_removed_command_stops_with_what_to_do(self, capsys):
        with pytest.raises(SystemExit) as stop:
            odatix_main.normalize_argv(["res_benchmark"])
        assert stop.value.code != 0
        assert "simulation metric" in capsys.readouterr().out


######################################
# What a command says
######################################

class TestPrefix:
    def test_messages_carry_the_command_rather_than_the_module(self, capsys):
        printc.set_command("odatix fmax")
        try:
            printc.error("broken", "run_fmax_synthesis.py")
        finally:
            printc.set_command(None)
        out = capsys.readouterr().out
        assert "[odatix fmax]" in out and "run_fmax_synthesis.py" not in out

    def test_without_a_command_the_module_is_named(self, capsys):
        printc.note("hello", "module.py")
        assert "[module.py]" in capsys.readouterr().out

    def test_an_unexpected_error_is_a_short_message_and_a_log(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)

        def broken(args):
            raise ValueError("boom")

        monkeypatch.setitem(odatix_main.COMMANDS, "migrate", broken)
        with pytest.raises(SystemExit) as stop:
            odatix_main.main(odatix_main.ArgParser.parse_arguments(["migrate", "-Q"]))
        assert stop.value.code == 1
        out = capsys.readouterr().out
        assert "ValueError: boom" in out and "Traceback" not in out
        assert (tmp_path / odatix_main.error_logfile).exists()


######################################
# The eda tool of a run
######################################

class TestDefaultTool:
    def test_the_workspace_names_it(self, tmp_path, monkeypatch):
        workspace = workspace_with(tmp_path, monkeypatch, "default_tool: genus\n", ["vivado", "genus"])
        assert workspace.default_tool == "genus"

    def test_a_single_target_file_names_it(self, tmp_path, monkeypatch):
        assert workspace_with(tmp_path, monkeypatch, target_files=["verilator"]).default_tool == "verilator"

    def test_several_target_files_name_none(self, tmp_path, monkeypatch):
        workspace = workspace_with(tmp_path, monkeypatch, target_files=["vivado", "genus"])
        assert workspace.default_tool is None
        assert workspace.configured_tools() == ["genus", "vivado"]

    def test_init_names_one(self):
        from odatix.lib.settings import OdatixSettings
        from odatix.workspace.yaml_io import read_yaml

        init_settings = os.path.join(OdatixSettings.odatix_init_path, "odatix.yml")
        assert read_yaml(init_settings)["default_tool"]


class TestRunTool:
    def test_without_a_default_the_run_asks_for_one(self, tmp_path, monkeypatch):
        workspace = workspace_with(tmp_path, monkeypatch, target_files=["vivado", "genus"])
        with pytest.raises(RunError) as error:
            Run(workspace, "fmax_synthesis").check()
        assert "-t/--tool" in str(error.value)
        assert any("genus, vivado" in text for _level, text in error.value.messages)

    def test_an_unknown_tool_is_refused_with_the_known_ones(self, tmp_path, monkeypatch):
        workspace = workspace_with(tmp_path, monkeypatch, target_files=["vivado"])
        with pytest.raises(RunError) as error:
            Run(workspace, "custom_freq_synthesis", tool="no_such_tool").check()
        assert "no_such_tool" in str(error.value)
        assert any("vivado" in text for _level, text in error.value.messages)

    def test_an_analysis_takes_the_default_as_its_list(self, tmp_path, monkeypatch):
        workspace = workspace_with(tmp_path, monkeypatch, "default_tool: verilator\n")
        run = Run(workspace, "analysis")
        run.resolve_tool()
        assert run.options.tool == ["verilator"]

    def test_a_simulation_needs_no_tool(self, tmp_path, monkeypatch):
        run = Run(workspace_with(tmp_path, monkeypatch), "simulation")
        run.resolve_tool()
        assert not run.options.tool

    @needs_tclsh
    def test_a_run_uses_the_default_tool(self, dummy_workspace):
        settings = dummy_workspace / "odatix.yml"
        settings.write_text(settings.read_text().replace("default_tool: vivado", "default_tool: dummy"))
        run = Run(Workspace.open(), "custom_freq_synthesis")
        assert run.check().run_count() > 0
        assert run.options.tool == "dummy"


class TestTargets:
    def test_a_place_and_route_is_told_its_targets(self, tmp_path, monkeypatch):
        import odatix.components.run_pnr as run_pnr

        seen = {}

        def check_settings(**kwargs):
            seen.update(kwargs)
            raise SystemExit(-1)

        monkeypatch.setattr(run_pnr, "check_settings", check_settings)
        workspace = workspace_with(tmp_path, monkeypatch, target_files=["vivado"])
        with pytest.raises(RunError):
            Run(workspace, "pnr", tool="vivado", targets=["a", "b"]).check()
        assert seen["selected_targets"] == ["a", "b"]


######################################
# odatix results
######################################

class TestResultsAll:
    def test_every_kind_that_was_run_is_exported_then_derived(self, example_workspace, monkeypatch):
        from odatix.lib.settings import OdatixSettings

        calls = []
        for name, module in (("synth", odatix_main.exp_res), ("sim", odatix_main.exp_sim_res), ("workflow", odatix_main.exp_workflow_res)):
            monkeypatch.setattr(module, "main", lambda args, name=name: calls.append((name, args.work_path)))
        monkeypatch.setattr(odatix_main.exp_derived, "run", lambda **kwargs: calls.append(("derived", None)) or True)

        settings = OdatixSettings()
        work = example_workspace / "w"
        (work / settings.simulation_work_path).mkdir(parents=True)

        args = odatix_main.ArgParser.parse_arguments(["results", "-w", str(work)])
        assert odatix_main.export_results_command(args) is True
        assert [name for name, _path in calls] == ["synth", "sim", "derived"]
        assert calls[1][1] == os.path.join(str(work), settings.simulation_work_path)


######################################
# odatix init
######################################

class TestInit:
    @pytest.mark.parametrize("argv, examples", [(["init"], False), (["init", "--examples"], True)])
    def test_without_a_terminal_nothing_is_asked(self, argv, examples, monkeypatch):
        from odatix.lib.settings import OdatixSettings

        seen = {}
        monkeypatch.setattr(odatix_main.sys.stdin, "isatty", lambda: False)
        monkeypatch.setattr(OdatixSettings, "init_directory_nodialog", staticmethod(lambda examples, prog: seen.setdefault("examples", examples) or True))
        monkeypatch.setattr(OdatixSettings, "init_directory_dialog", staticmethod(lambda **kwargs: pytest.fail("asked")))
        odatix_main.init_directory(odatix_main.ArgParser.parse_arguments(argv))
        assert seen["examples"] is examples

    def test_yes_asks_nothing_even_in_a_terminal(self, monkeypatch):
        from odatix.lib.settings import OdatixSettings

        seen = []
        monkeypatch.setattr(odatix_main.sys.stdin, "isatty", lambda: True)
        monkeypatch.setattr(OdatixSettings, "init_directory_nodialog", staticmethod(lambda examples, prog: seen.append(examples) or True))
        monkeypatch.setattr(OdatixSettings, "init_directory_dialog", staticmethod(lambda **kwargs: pytest.fail("asked")))
        odatix_main.init_directory(odatix_main.ArgParser.parse_arguments(["init", "-y"]))
        assert seen == [False]


######################################
# odatix dse -c
######################################

class TestDseConfig:
    def test_an_exploration_settings_file_given_as_config_is_refused(self, tmp_path, capsys):
        from odatix.components.run_dse import refuse_former_config

        settings = tmp_path / "dse_settings.yml"
        settings.write_text("campaigns: [fir]\nnb_jobs: 4\n")
        with pytest.raises(SystemExit):
            refuse_former_config(str(settings))
        assert "-i/--input" in capsys.readouterr().out

    def test_a_workspace_settings_file_is_accepted(self, tmp_path):
        from odatix.components.run_dse import refuse_former_config

        settings = tmp_path / "odatix.yml"
        settings.write_text("workspace: odatix\n")
        refuse_former_config(str(settings))


######################################
# Benchmark metrics
######################################

class TestBenchmarkMetrics:
    def test_a_benchmark_metric_is_skipped_with_a_warning(self, tmp_path, capsys):
        import odatix.components.export_results as export_results

        metrics = {"metrics": {
            "DMIPS_per_MHz": {"type": "benchmark", "settings": {"key": "DMIPS_per_MHz"}},
            "DMIPS": {"type": "operation", "benchmark_only": True, "settings": {"op": "DMIPS_per_MHz * 2"}},
        }}
        export_results._reset_banned_lists()
        results, _units, _measured = export_results.extract_metrics(
            metrics, str(tmp_path / "metrics.yml"), str(tmp_path), "arch", str(tmp_path),
        )
        assert results == {}
        out = capsys.readouterr().out
        assert "DMIPS_per_MHz" in out and "simulation metric" in out
