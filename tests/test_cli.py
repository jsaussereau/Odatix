"""Tests for the Odatix command-line interfaces.

Covers the argument parsers of `odatix` (odatix_main), `odatix-explorer` and
`odatix-gui` — subcommands, defaults, flag aliases, invalid values — plus
subprocess smoke tests of the real entry point (marked `integration`).
"""

import argparse
import os
import subprocess
import sys

import pytest

from conftest import SOURCES_DIR

import odatix.odatix_main as odatix_main
import odatix.odatix_explorer as odatix_explorer
import odatix.odatix_gui as odatix_gui
from odatix.lib.settings import OdatixSettings


def parse(*argv):
    """Run the odatix argument parser on the given command line."""
    old_argv = sys.argv
    sys.argv = ["odatix", *argv]
    try:
        return odatix_main.ArgParser.parse_arguments()
    finally:
        sys.argv = old_argv


######################################
# Global flags
######################################

class TestGlobalFlags:
    def test_no_arguments(self):
        args = parse()
        assert args.command is None
        assert args.version is False
        assert args.help is False
        assert args.init is False

    def test_version_flag(self):
        assert parse("-v").version is True
        assert parse("--version").version is True

    def test_help_flag(self):
        assert parse("-h").help is True

    def test_init_flag(self):
        assert parse("--init").init is True

    def test_unknown_command_exits(self):
        with pytest.raises(SystemExit):
            parse("bogus_command")


######################################
# Subcommands
######################################

class TestInitCommand:
    def test_defaults(self):
        args = parse("init")
        assert args.command == "init"
        assert args.examples is False

    def test_examples_flag(self):
        assert parse("init", "-e").examples is True
        assert parse("init", "--examples").examples is True


class TestGenerateCommand:
    def test_defaults(self):
        args = parse("generate")
        assert args.command == "generate"
        assert args.overwrite is False
        assert args.noask is False
        assert args.debug is False
        assert args.nobanner is False

    def test_flags(self):
        args = parse("generate", "-o", "-y", "-D", "-Q")
        assert args.overwrite and args.noask and args.debug and args.nobanner


class TestReplaceCommand:
    def test_all_required_arguments(self):
        args = parse(
            "replace",
            "-s", "START", "-S", "STOP",
            "-i", "in.txt", "-o", "out.txt", "-r", "params.txt",
        )
        assert args.command == "replace"
        assert args.start_delimiter == "START"
        assert args.stop_delimiter == "STOP"
        assert args.base_text_file == "in.txt"
        assert args.output_file == "out.txt"
        assert args.replacement_text_file == "params.txt"
        assert args.replace_all_occurrences is False

    def test_replace_all_flag(self):
        args = parse(
            "replace", "-s", "a", "-S", "b", "-i", "i", "-o", "o", "-r", "r", "--all",
        )
        assert args.replace_all_occurrences is True

    def test_missing_required_argument_exits(self):
        with pytest.raises(SystemExit):
            parse("replace", "-s", "START")


class TestFmaxCommand:
    def test_defaults(self):
        args = parse("fmax")
        assert args.command == "fmax"
        assert args.tool == "vivado"
        assert args.overwrite is False
        assert args.noask is False
        assert args.noexport is False
        assert args.from_freq is None
        assert args.to_freq is None
        assert args.config == OdatixSettings.DEFAULT_SETTINGS_FILE

    def test_tool_and_bounds(self):
        args = parse("fmax", "-t", "openlane", "--from", "100", "--to", "500")
        assert args.tool == "openlane"
        assert args.from_freq == 100
        assert args.to_freq == 500

    def test_bounds_must_be_integers(self):
        with pytest.raises(SystemExit):
            parse("fmax", "--from", "fast")

    def test_flags(self):
        args = parse("fmax", "-o", "-y", "-e", "-k", "-T", "--continue-on-error", "-d", "-S", "mysession")
        assert args.overwrite and args.noask and args.noexport and args.keep
        assert args.trust and args.continue_on_error and args.detach
        assert args.session == "mysession"

    def test_force_is_a_deprecated_alias_of_continue_on_error(self):
        assert parse("fmax", "--force").continue_on_error is True

    def test_flow(self):
        assert parse("fmax").flow is None
        assert parse("fmax", "-f", "synthesis").flow == "synthesis"
        assert parse("freq", "--flow", "bitstream").flow == "bitstream"
        assert parse("analyze", "-f", "vivado:implementation").flow == ["vivado:implementation"]


class TestFreqCommand:
    def test_defaults(self):
        args = parse("freq")
        assert args.command == "freq"
        assert args.tool == "vivado"
        assert args.at_freq is None
        assert args.step_freq is None

    def test_at_is_repeatable(self):
        args = parse("freq", "--at", "50", "--at", "100")
        assert args.at_freq == [50, 100]

    def test_range_override(self):
        args = parse("freq", "--from", "50", "--to", "200", "--step", "25")
        assert (args.from_freq, args.to_freq, args.step_freq) == (50, 200, 25)


class TestAnalyzeCommand:
    def test_tool_accepts_multiple_values(self):
        args = parse("analyze", "-t", "vivado", "openlane")
        assert args.command == "analyze"
        assert args.tool == ["vivado", "openlane"]

    def test_default_tool(self):
        # -t / --tool defaults to None so that main() can fall back to the
        # "tools" list of the analysis settings file when it is not given.
        assert parse("analyze").tool is None

    def test_tools_from_settings_file(self, tmp_path):
        import odatix.components.run_analysis as run_analysis

        settings = tmp_path / "analysis_settings.yml"
        settings.write_text("tools:\n  - vivado\n  - design_compiler\n  - openlane\n")
        assert run_analysis.get_analysis_tools_from_settings(str(settings)) == [
            "vivado", "design_compiler", "openlane",
        ]

    def test_tools_single_scalar_is_wrapped(self, tmp_path):
        import odatix.components.run_analysis as run_analysis

        settings = tmp_path / "analysis_settings.yml"
        settings.write_text("tools: verilator\n")
        assert run_analysis.get_analysis_tools_from_settings(str(settings)) == ["verilator"]

    def test_tools_missing_key_defaults(self, tmp_path):
        import odatix.components.run_analysis as run_analysis

        settings = tmp_path / "analysis_settings.yml"
        settings.write_text("architectures:\n  - Foo/8bits\n")
        assert run_analysis.get_analysis_tools_from_settings(str(settings)) == run_analysis.DEFAULT_ANALYSIS_TOOLS

    def test_tools_missing_file_defaults(self):
        import odatix.components.run_analysis as run_analysis

        assert run_analysis.get_analysis_tools_from_settings("nope.yml") == run_analysis.DEFAULT_ANALYSIS_TOOLS

    def test_load_tool_context_ignores_target_files(self, tmp_path):
        # RTL analysis must not use target definition files ("target_<tool>.yml"):
        # load_tool_context works even when no such file exists in target_path.
        import odatix.components.run_analysis as run_analysis
        import odatix.lib.hard_settings as hard_settings

        # tmp_path has no target_verilator.yml
        ctx = run_analysis.load_tool_context("verilator", str(tmp_path))
        assert ctx["eda_target_filename"] is None
        assert ctx["targets"] == [hard_settings.default_analysis_target]
        # Must be a plain filename, not empty: the shared init_script.tcl always
        # creates this file, and an empty constraint_filename resolves to the
        # tmp_dir path itself (a directory), which crashes tcl's "open ... w".
        assert ctx["constraint_file"] == hard_settings.default_analysis_constraint_file
        assert ctx["constraint_file"] != ""


class TestSimCommand:
    def test_defaults(self):
        args = parse("sim")
        assert args.command == "sim"
        assert args.overwrite is False
        assert args.config == OdatixSettings.DEFAULT_SETTINGS_FILE

    def test_paths(self):
        args = parse("sim", "-i", "s.yml", "-a", "archs", "-s", "sims", "-w", "work", "-j", "4")
        assert args.input == "s.yml"
        assert args.archpath == "archs"
        assert args.simpath == "sims"
        assert args.work == "work"
        assert args.jobs == "4"


class TestWorkflowCommand:
    def test_defaults(self):
        args = parse("workflow")
        assert args.command == "workflow"
        assert args.resume is False
        assert args.noexport is False

    def test_flags(self):
        args = parse("workflow", "-r", "-e", "-p", "wfs", "-w", "work")
        assert args.resume and args.noexport
        assert args.workflowpath == "wfs"
        assert args.work == "work"


class TestDaemonCommands:
    def test_monitor(self):
        args = parse("monitor", "-S", "sess", "--host", "127.0.0.1", "--port", "8000")
        assert args.command == "monitor"
        assert args.session == "sess"
        assert args.host == "127.0.0.1"
        assert args.port == 8000

    def test_monitor_defaults(self):
        args = parse("monitor")
        assert args.session is None
        assert args.host is None
        assert args.port is None

    def test_stop_all(self):
        assert parse("stop", "-a").all is True

    def test_stop_session_and_all_are_exclusive(self):
        with pytest.raises(SystemExit):
            parse("stop", "-a", "-S", "sess")

    def test_ls(self):
        args = parse("ls", "-S", "prefix")
        assert args.command == "ls"
        assert args.session == "prefix"

    def test_port_must_be_integer(self):
        with pytest.raises(SystemExit):
            parse("ls", "--port", "not_a_port")


class TestResultsCommands:
    def test_results_defaults(self):
        args = parse("results")
        assert args.command == "results"
        assert args.tool == "all"
        assert args.format is None
        assert args.use_benchmark is False

    def test_results_format_choices(self):
        assert parse("results", "-f", "csv").format == "csv"
        assert parse("results", "-f", "yml").format == "yml"
        assert parse("results", "-f", "all").format == "all"

    def test_results_invalid_format_exits(self):
        with pytest.raises(SystemExit):
            parse("results", "-f", "xml")

    def test_res_benchmark(self):
        args = parse("res_benchmark", "-w", "work")
        assert args.command == "res_benchmark"
        assert args.work == "work"

    def test_res_synth(self):
        args = parse("res_synth", "-t", "vivado")
        assert args.command == "res_synth"
        assert args.tool == "vivado"

    def test_res_workflow(self):
        args = parse("res_workflow", "-w", "work")
        assert args.command == "res_workflow"
        assert args.work == "work"


class TestCleanCommand:
    def test_defaults(self):
        args = parse("clean")
        assert args.command == "clean"
        assert args.force is False
        assert args.verbose is False
        assert args.quiet is False

    def test_flags(self):
        args = parse("clean", "-f", "-v")
        assert args.force and args.verbose


######################################
# main() dispatch
######################################

class TestMainDispatch:
    def test_version_exits_zero(self, capsys):
        args = argparse.Namespace(version=True, help=False, init=False, command=None)
        with pytest.raises(SystemExit) as exc:
            odatix_main.main(args)
        assert exc.value.code == 0
        assert capsys.readouterr().out.strip() != ""

    def test_no_command_exits_zero(self, capsys):
        args = argparse.Namespace(version=False, help=False, init=False, command=None)
        with pytest.raises(SystemExit) as exc:
            odatix_main.main(args)
        assert exc.value.code == 0


######################################
# odatix-explorer / odatix-gui parsers
######################################

class TestExplorerAndGuiParsers:
    def build_parser(self, add_arguments):
        parser = argparse.ArgumentParser()
        add_arguments(parser)
        return parser

    @pytest.mark.parametrize("add_arguments", [odatix_explorer.add_arguments, odatix_gui.add_arguments])
    def test_defaults(self, add_arguments):
        args = self.build_parser(add_arguments).parse_args([])
        assert args.input == "results"
        assert args.network is False
        assert args.nobrowser is False
        assert args.safe_mode is False
        assert args.normal_term_mode is False
        assert args.theme is None
        assert isinstance(args.port, int)

    @pytest.mark.parametrize("add_arguments", [odatix_explorer.add_arguments, odatix_gui.add_arguments])
    def test_options(self, add_arguments):
        args = self.build_parser(add_arguments).parse_args(
            ["-i", "my_results", "-n", "-p", "9000", "-B", "-T", "dark"]
        )
        assert args.input == "my_results"
        assert args.network is True
        assert args.port == 9000
        assert args.nobrowser is True
        assert args.theme == "dark"

    @pytest.mark.parametrize("add_arguments", [odatix_explorer.add_arguments, odatix_gui.add_arguments])
    def test_port_must_be_integer(self, add_arguments):
        with pytest.raises(SystemExit):
            self.build_parser(add_arguments).parse_args(["-p", "abc"])


######################################
# Real entry point (subprocess smoke tests)
######################################

def run_cli(*argv, cwd=None):
    env = dict(os.environ, PYTHONPATH=SOURCES_DIR)
    return subprocess.run(
        [sys.executable, "-m", "odatix.odatix_main", *argv],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        cwd=cwd or SOURCES_DIR,
        env=env,
        timeout=120,
    )


@pytest.mark.integration
class TestCliSubprocess:
    def test_version(self):
        result = run_cli("-v")
        assert result.returncode == 0
        assert result.stdout.strip() != ""

    def test_no_command_shows_hint(self):
        result = run_cli()
        assert result.returncode == 0
        assert "-h" in result.stdout

    def test_help(self):
        result = run_cli("-h")
        assert result.returncode == 0
        for keyword in ("fmax", "sim", "workflow", "generate", "clean"):
            assert keyword in result.stdout

    def test_subcommand_help(self):
        result = run_cli("fmax", "--help")
        assert result.returncode == 0
        assert "--tool" in result.stdout or "-t" in result.stdout

    def test_invalid_command_fails(self):
        result = run_cli("bogus")
        assert result.returncode != 0

    def test_generate_end_to_end(self, example_workspace):
        """`odatix generate -y -Q` generates configuration files in a workspace."""
        result = run_cli("generate", "-y", "-Q", cwd=str(example_workspace))
        assert result.returncode == 0, result.stdout + result.stderr
        generated = example_workspace / (
            "odatix_userconfig/architectures/Example_Config_Generation/01_Range/config_10.txt"
        )
        assert generated.is_file()
        assert "parameter VALUE = 10;" in generated.read_text()

    def test_generate_twice_without_overwrite_fails(self, example_workspace):
        """Second run without -o: everything already exists, no valid config -> exit != 0."""
        first = run_cli("generate", "-y", "-Q", cwd=str(example_workspace))
        assert first.returncode == 0
        second = run_cli("generate", "-y", "-Q", cwd=str(example_workspace))
        assert second.returncode != 0

    def test_generate_twice_with_overwrite_succeeds(self, example_workspace):
        first = run_cli("generate", "-y", "-Q", cwd=str(example_workspace))
        assert first.returncode == 0
        second = run_cli("generate", "-y", "-Q", "-o", cwd=str(example_workspace))
        assert second.returncode == 0

    def test_replace_end_to_end(self, tmp_path):
        base = tmp_path / "top.v"
        base.write_text("module m #(\n  parameter W = 4\n)();\nendmodule\n")
        replacement = tmp_path / "params.txt"
        replacement.write_text("\n  parameter W = 32\n")
        output = tmp_path / "out.v"

        result = run_cli(
            "replace", "-Q",
            "-s", "#(", "-S", ")(",
            "-i", str(base), "-o", str(output), "-r", str(replacement),
            cwd=str(tmp_path),
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "parameter W = 32" in output.read_text()
