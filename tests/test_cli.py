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

    def test_version_flag(self):
        assert parse("-v").version is True
        assert parse("--version").version is True

    def test_help_flag(self):
        assert parse("-h").help is True

    def test_init_flag_is_a_deprecated_spelling_of_init(self, capsys):
        assert parse("--init").command == "init"
        assert "deprecated" in capsys.readouterr().out

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
        # None: the dialog asks whether to add the examples
        assert args.examples is None
        assert args.noask is False

    def test_examples_flag(self, capsys):
        assert parse("init", "--examples").examples is True
        assert "deprecated" not in capsys.readouterr().out
        assert parse("init", "-e").examples is True
        assert "deprecated" in capsys.readouterr().out

    def test_yes_skips_the_dialog(self):
        assert parse("init", "-y").noask is True
        assert parse("init", "--yes").noask is True


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
        # None: the run takes the default tool of the workspace
        assert args.tool is None
        assert args.targets is None
        assert args.overwrite is False
        assert args.noask is False
        assert args.noexport is False
        assert args.lower_bound is None
        assert args.upper_bound is None
        assert args.config == OdatixSettings.DEFAULT_SETTINGS_FILE

    def test_tool_and_bounds(self):
        args = parse("fmax", "-t", "openlane", "--from", "100", "--to", "500")
        assert args.tool == "openlane"
        assert args.lower_bound == 100
        assert args.upper_bound == 500

    def test_bounds_must_be_integers(self):
        with pytest.raises(SystemExit):
            parse("fmax", "--from", "fast")

    def test_flags(self):
        args = parse("fmax", "-o", "-y", "-e", "-k", "-T", "--continue-on-error", "-d", "-S", "mysession")
        assert args.overwrite and args.noask and args.noexport and args.keep
        assert args.check_eda_tool is False
        assert args.continue_on_error and args.detach
        assert args.session == "mysession"

    def test_force_is_no_longer_an_alias_of_continue_on_error(self):
        with pytest.raises(SystemExit):
            parse("fmax", "--force")

    @pytest.mark.parametrize("command", ["fmax", "synth", "pnr"])
    def test_target_is_repeatable_and_has_no_short_form(self, command):
        assert parse(command, "--target", "a", "--target", "b").targets == ["a", "b"]
        # -T is --trust everywhere
        assert parse(command, "-T").check_eda_tool is False

    def test_flow(self):
        assert parse("fmax").flow is None
        assert parse("fmax", "-f", "synthesis").flow == "synthesis"
        assert parse("synth", "--flow", "bitstream").flow == "bitstream"
        assert parse("analyze", "-f", "vivado:implementation").flow == ["vivado:implementation"]


class TestSynthCommand:
    def test_defaults(self):
        args = parse("synth")
        assert args.command == "synth"
        assert args.tool is None
        assert args.at_freq is None
        assert args.step_freq is None

    def test_at_is_repeatable(self):
        args = parse("synth", "--at", "50", "--at", "100")
        assert args.at_freq == [50, 100]

    def test_range_override(self):
        args = parse("synth", "--from", "50", "--to", "200", "--step", "25")
        assert (args.from_freq, args.to_freq, args.step_freq) == (50, 200, 25)

    def test_freq_is_a_deprecated_name_of_synth(self, capsys):
        assert parse("freq", "--at", "50").command == "synth"
        assert '"odatix synth"' in capsys.readouterr().out

    @pytest.mark.parametrize("command", ["synthesis", "explore", "res_benchmark"])
    def test_removed_commands_say_what_to_do_instead(self, command, capsys):
        with pytest.raises(SystemExit):
            parse(command)
        assert "no longer exists" in capsys.readouterr().out


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
        args = parse("sim", "-i", "s.yml", "--archpath", "archs", "--simpath", "sims", "-w", "work", "-j", "4")
        assert args.settings_file == "s.yml"
        assert args.arch_path == "archs"
        assert args.sim_path == "sims"
        assert args.work_path == "work"
        assert args.nb_jobs == "4"

    def test_noexport(self):
        assert parse("sim").noexport is False
        assert parse("sim", "-e").noexport is True


class TestWorkflowCommand:
    def test_defaults(self):
        args = parse("workflow")
        assert args.command == "workflow"
        assert args.resume is False
        assert args.noexport is False

    def test_flags(self):
        args = parse("workflow", "-r", "-e", "-p", "wfs", "-w", "work")
        assert args.resume and args.noexport
        assert args.workflow_path == "wfs"
        assert args.work_path == "work"


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
        args = parse("ps", "-S", "prefix")
        assert args.command == "ps"
        assert args.session == "prefix"

    def test_port_must_be_integer(self):
        with pytest.raises(SystemExit):
            parse("ps", "--port", "not_a_port")


class TestResultsCommands:
    def test_results_alone_exports_everything(self):
        args = parse("results")
        assert args.command == "results"
        assert args.result_type == "all"
        assert args.tool == "all"

    def test_options_without_a_type_are_those_of_all(self):
        args = parse("results", "-w", "work", "-r", "out")
        assert args.result_type == "all"
        assert (args.work_path, args.result_path) == ("work", "out")

    @pytest.mark.parametrize("result_type", ["all", "synth", "sim", "workflow", "analysis", "derived"])
    def test_every_type(self, result_type):
        assert parse("results", result_type).result_type == result_type

    @pytest.mark.parametrize("argv", [("results",), ("results", "synth")])
    def test_there_is_no_format_option(self, argv):
        # Results are only ever written as v2 YAML: there is nothing to choose.
        with pytest.raises(SystemExit):
            parse(*argv, "-f", "csv")

    @pytest.mark.parametrize("argv", [("results", "-u"), ("results", "synth", "-B", "b.yml"), ("results", "-S", "sim.log")])
    def test_the_benchmark_options_are_gone(self, argv):
        with pytest.raises(SystemExit):
            parse(*argv)

    @pytest.mark.parametrize("former, result_type", [
        ("res_synth", "synth"), ("res_simulation", "sim"), ("res_workflow", "workflow"),
        ("res_analysis", "analysis"), ("res_derived", "derived"),
    ])
    def test_the_former_commands_are_deprecated_names_of_a_type(self, former, result_type, capsys):
        args = parse(former, "-r", "out")
        assert (args.command, args.result_type, args.result_path) == ("results", result_type, "out")
        assert '"odatix results ' + result_type + '"' in capsys.readouterr().out

    def test_res_synth_keeps_its_options(self):
        args = parse("res_synth", "-t", "vivado")
        assert args.tool == "vivado"


class TestCleanCommand:
    def test_defaults(self):
        args = parse("clean")
        assert args.command == "clean"
        assert args.force is False
        assert args.verbose is False
        assert args.quiet is False

    def test_flags(self, capsys):
        args = parse("clean", "-y", "-V")
        assert args.force and args.verbose
        assert "deprecated" not in capsys.readouterr().out

    @pytest.mark.parametrize("former", ["-f", "--force"])
    def test_force_is_a_deprecated_spelling_of_yes(self, former, capsys):
        assert parse("clean", former).force is True
        assert '"-y/--yes"' in capsys.readouterr().out

    def test_v_is_only_the_version(self):
        with pytest.raises(SystemExit):
            parse("clean", "-v")


class TestRenamedOptions:
    def test_generate_takes_its_workflow_directory_like_workflow(self, capsys):
        assert parse("generate", "-p", "wfs").workflow_path == "wfs"
        assert "deprecated" not in capsys.readouterr().out
        assert parse("generate", "-w", "wfs").workflow_path == "wfs"
        assert '"-p/--workflowpath"' in capsys.readouterr().out

    def test_dse_reads_its_settings_file_as_an_input(self):
        args = parse("dse", "-i", "dse.yml")
        assert args.config_file == "dse.yml"
        assert args.config == OdatixSettings.DEFAULT_SETTINGS_FILE

    def test_dse_target_has_no_short_form_any_more(self, capsys):
        assert parse("dse", "--target", "a").targets == ["a"]
        assert parse("dse", "-T", "a").targets == ["a"]
        assert '"--target"' in capsys.readouterr().out


class TestHelp:
    def test_every_command_is_listed_in_a_group(self):
        parse()
        grouped = [name for _group, names in odatix_main.COMMAND_GROUPS for name in names]
        assert sorted(grouped) == sorted(odatix_main.COMMANDS)
        assert len(grouped) == len(set(grouped))

    def test_the_help_is_generated(self, capsys):
        parse()
        odatix_main.ArgParser.help()
        out = capsys.readouterr().out
        for name in odatix_main.COMMANDS:
            assert odatix_main.ArgParser.command_help(name)
            assert name in out
        assert "odatix-gui" in out and "odatix-explorer" in out
        assert odatix_main.GLOSSARY_URL in out

    def test_the_program_is_called_odatix(self):
        parse()
        assert odatix_main.ArgParser.parser.prog == "odatix"


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
        # The explorer takes its result directory from the workspace settings
        # file ("-c") when "-i" does not give one.
        assert args.input == (None if add_arguments is odatix_explorer.add_arguments else "results")
        assert args.network is False
        assert args.nobrowser is False
        assert args.safe_mode is False
        assert args.normal_term_mode is False
        assert args.theme is None
        # Unset, so that the launcher tells a port asked for (that one or an
        # error) from the default one (8052, or the next free port)
        assert args.port is None

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

    def test_generate_twice_changes_nothing(self, example_workspace):
        """Generating what is already there is a no-op, not an error."""
        generated = example_workspace / (
            "odatix_userconfig/architectures/Example_Config_Generation/01_Range/config_10.txt"
        )
        first = run_cli("generate", "-y", "-Q", cwd=str(example_workspace))
        assert first.returncode == 0
        before = generated.read_text()

        second = run_cli("generate", "-y", "-Q", cwd=str(example_workspace))
        assert second.returncode == 0
        assert generated.read_text() == before

    def test_generate_leaves_an_edited_configuration_alone(self, example_workspace):
        """An edit survives a second generation: that is what the manifest is for."""
        generated = example_workspace / (
            "odatix_userconfig/architectures/Example_Config_Generation/01_Range/config_10.txt"
        )
        assert run_cli("generate", "-y", "-Q", cwd=str(example_workspace)).returncode == 0
        generated.write_text("parameter VALUE = 42;\n")

        assert run_cli("generate", "-y", "-Q", cwd=str(example_workspace)).returncode == 0
        assert generated.read_text() == "parameter VALUE = 42;\n"

        assert run_cli("generate", "-y", "-Q", "-o", cwd=str(example_workspace)).returncode == 0
        assert "parameter VALUE = 10;" in generated.read_text()

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


######################################
# Exit codes (subprocess)
######################################

@pytest.mark.integration
class TestExitCodes:
    """Every command says by its exit code whether it did what it was asked."""

    def test_clean_succeeds(self, example_workspace):
        assert run_cli("clean", "-Q", cwd=str(example_workspace)).returncode == 0

    def test_clean_falls_back_to_the_default_settings(self, example_workspace):
        (example_workspace / "odatix_userconfig" / "clean_settings.yml").unlink()
        result = run_cli("clean", "-Q", cwd=str(example_workspace))
        assert result.returncode == 0, result.stdout + result.stderr

    def test_clean_fails_on_an_invalid_settings_file(self, example_workspace):
        (example_workspace / "bad.yml").write_text("remove_list: [\n")
        assert run_cli("clean", "-Q", "-i", "bad.yml", cwd=str(example_workspace)).returncode != 0

    @pytest.mark.parametrize("command", ["res_synth", "res_workflow", "res_simulation", "results"])
    def test_exporting_nothing_succeeds(self, example_workspace, command):
        (example_workspace / "empty_work").mkdir()
        result = run_cli(command, "-Q", "-w", "empty_work", "-r", "out", cwd=str(example_workspace))
        assert result.returncode == 0, result.stdout + result.stderr

    def test_res_synth_fails_without_work_directory(self, example_workspace):
        assert run_cli("res_synth", "-Q", "-w", "nowhere", "-r", "out", cwd=str(example_workspace)).returncode != 0

    @pytest.mark.parametrize("command", ["res_workflow", "res_simulation"])
    def test_a_results_file_that_cannot_be_written_fails(self, example_workspace, command):
        # A run to export: with none, nothing is written at all
        (example_workspace / "empty_work" / "a" / "b" / "c").mkdir(parents=True)
        (example_workspace / "a_file").write_text("")
        result = run_cli(command, "-Q", "-w", "empty_work", "-r", "a_file/out", cwd=str(example_workspace))
        assert result.returncode != 0

    def test_res_derived_without_definitions_succeeds(self, example_workspace):
        (example_workspace / "odatix_userconfig" / "derived_metrics.yml").unlink()
        assert run_cli("res_derived", "-Q", "-r", "out", cwd=str(example_workspace)).returncode == 0

    def test_res_derived_fails_on_a_named_file_that_does_not_exist(self, example_workspace):
        assert run_cli("res_derived", "-Q", "-r", "out", "-d", "none.yml", cwd=str(example_workspace)).returncode != 0

    def test_res_derived_fails_on_an_invalid_file(self, example_workspace):
        (example_workspace / "bad.yml").write_text("derived_metrics: [\n")
        result = run_cli("res_derived", "-Q", "-r", "out", "-d", "bad.yml", cwd=str(example_workspace))
        assert result.returncode != 0

    def test_ls_without_any_matching_session_succeeds(self, example_workspace):
        assert run_cli("ps", "-S", "odatix-test-no-such-session", cwd=str(example_workspace)).returncode == 0

    @pytest.mark.parametrize("command", ["stop", "monitor"])
    def test_reaching_a_session_that_does_not_exist_fails(self, example_workspace, command):
        assert run_cli(command, "-S", "odatix-test-no-such-session", cwd=str(example_workspace)).returncode != 0

    def test_replace_fails_when_the_delimiters_match_nothing(self, tmp_path):
        base = tmp_path / "top.v"
        base.write_text("module m();\nendmodule\n")
        replacement = tmp_path / "params.txt"
        replacement.write_text("parameter W = 32\n")
        result = run_cli(
            "replace", "-Q", "-s", "#(", "-S", ")(",
            "-i", str(base), "-o", str(tmp_path / "out.v"), "-r", str(replacement),
            cwd=str(tmp_path),
        )
        assert result.returncode != 0

    def test_a_run_outside_of_a_workspace_fails(self, tmp_path):
        assert run_cli("fmax", "-Q", "-y", cwd=str(tmp_path)).returncode != 0


######################################
# Exit codes (in process)
######################################

def run_main(*argv):
    """The exit code odatix_main.main() stops with, for this command line."""
    with pytest.raises(SystemExit) as stop:
        odatix_main.main(parse(*argv))
    return stop.value.code


class TestDaemonCommandStatus:
    """The daemon commands need a daemon to succeed: theirs is replaced."""

    def test_monitor(self, monkeypatch):
        monkeypatch.setattr(odatix_main.daemon_control, "attach_monitor", lambda **kwargs: None)
        assert run_main("monitor", "-S", "session") == 0

        def fail(**kwargs):
            raise RuntimeError("no session")

        monkeypatch.setattr(odatix_main.daemon_control, "attach_monitor", fail)
        assert run_main("monitor", "-S", "session") != 0

    def test_stop(self, monkeypatch):
        monkeypatch.setattr(odatix_main.daemon_control, "stop_daemon", lambda **kwargs: True)
        assert run_main("stop", "-S", "session") == 0
        monkeypatch.setattr(odatix_main.daemon_control, "stop_daemon", lambda **kwargs: False)
        assert run_main("stop", "-S", "session") != 0

    def test_stop_zombies(self, monkeypatch):
        monkeypatch.setattr(
            odatix_main.daemon_control, "kill_zombie_daemons",
            lambda session=None, **kwargs: {"total": 1, "killed": 1, "failed": []},
        )
        assert run_main("stop", "-z") == 0
        monkeypatch.setattr(
            odatix_main.daemon_control, "kill_zombie_daemons",
            lambda session=None, **kwargs: {"total": 1, "killed": 0, "failed": [{}]},
        )
        monkeypatch.setattr(odatix_main.daemon_control, "format_daemons_table", lambda *args, **kwargs: "")
        assert run_main("stop", "-z") != 0

    def test_ps(self, monkeypatch):
        monkeypatch.setattr(odatix_main.daemon_control, "list_daemons", lambda **kwargs: [])
        assert run_main("ps") == 0

        def fail(**kwargs):
            raise RuntimeError("unreachable")

        monkeypatch.setattr(odatix_main.daemon_control, "list_daemons", fail)
        assert run_main("ps") != 0


class TestResultsStatus:
    def test_a_results_file_that_cannot_be_written_is_a_failure(self, tmp_path, monkeypatch):
        import odatix.components.export_results as export_results

        def fail(*args, **kwargs):
            raise OSError("read-only")

        monkeypatch.setattr(export_results.results_cache, "store", fail)
        assert export_results.export_results(
            input=str(tmp_path), output=str(tmp_path / "out"), tools=["vivado"],
            result_types={"fmax_synthesis": {"key": "fmax_synthesis", "path": "fmax_synthesis"}},
        ) is False

    def test_results_fails_when_deriving_fails(self, example_workspace, monkeypatch):
        import odatix.components.export_derived_metrics as exp_derived

        (example_workspace / "work").mkdir(exist_ok=True)
        monkeypatch.setattr(exp_derived, "run", lambda **kwargs: False)
        assert run_main("results", "-Q") != 0


######################################
# What the run commands are told
######################################

RUN_COMMANDS = ["fmax", "synth", "pnr", "analyze", "sim", "workflow"]


class TestRunOptionsFromCommandLine:
    @pytest.mark.parametrize("command", RUN_COMMANDS)
    def test_noexport_is_an_empty_result_path(self, command):
        from odatix.run.options import RunOptions

        assert RunOptions.from_namespace(parse(command, "-e")).result_path == ""
        # Unset: the run exports to the workspace result directory.
        assert RunOptions.from_namespace(parse(command)).result_path is None

    def test_options_land_in_the_settings_of_the_same_name(self):
        from odatix.run.options import RunOptions

        options = RunOptions.from_namespace(parse(
            "fmax", "-j", "4", "--archpath", "archs", "-i", "run.yml", "-w", "work", "-T", "-E",
            "--logsize", "50", "--from", "10", "--to", "20", "-y", "-d", "-S", "night",
        ))
        assert options.nb_jobs == "4"
        assert options.arch_path == "archs"
        assert options.settings_file == "run.yml"
        assert options.work_path == "work"
        assert options.check_eda_tool is False
        assert options.exit_when_done is True
        assert options.log_size_limit == 50
        assert (options.lower_bound, options.upper_bound) == (10, 20)
        assert options.noask is True and options.detach is True
        assert options.session == "night"

    def test_a_command_asks_and_attaches_unless_told_otherwise(self):
        from odatix.run.options import RunOptions

        options = RunOptions.from_namespace(parse("sim"))
        assert options.noask is False
        assert options.detach is False


class TestNoExport:
    """"-e" goes all the way down: the jobs are not told to export anything."""

    def _run_fmax(self, monkeypatch, *argv):
        import odatix.components.run_fmax_synthesis as fmax

        class Handler:
            process_group = True

        exports = {}
        monkeypatch.setattr(
            fmax, "check_settings",
            lambda **kwargs: (["arch"], "prepare", [], "tool.yml", Handler(), True, 42, 3, "plan"),
        )
        monkeypatch.setattr(fmax, "prepare_synthesis_jobs", lambda **kwargs: "jobs")
        monkeypatch.setattr(fmax.exp_res, "configure_synthesis_job_exports", lambda **kwargs: exports.update(job=kwargs))
        monkeypatch.setattr(fmax.exp_derived, "configure_post_batch_derivation", lambda *args: exports.update(batch=args))
        monkeypatch.setattr(fmax, "start_parallel_jobs", lambda jobs, **kwargs: None)
        assert run_main("fmax", "-Q", "-y", *argv) == 0
        return exports

    def test_fmax_exports_by_default(self, example_workspace, monkeypatch):
        exports = self._run_fmax(monkeypatch)
        # The workspace root is absolute (a run changes directory), so is its result path.
        results = os.path.join(os.path.realpath(str(example_workspace)), "results")
        assert os.path.realpath(exports["job"]["output_dir"]) == results
        jobs, output_dir = exports["batch"]
        assert jobs == "jobs" and os.path.realpath(output_dir) == results

    def test_fmax_noexport_exports_nothing(self, example_workspace, monkeypatch):
        assert self._run_fmax(monkeypatch, "-e") == {}

    # The analysis: see tests/test_analysis.py (TestCommands).


######################################
# Every option is read
######################################

def _subparsers(parser):
    return next(action for action in parser._actions if isinstance(action, argparse._SubParsersAction)).choices


def subcommand_parsers():
    """Every command parser of odatix, by command line: "fmax", "results synth"..."""
    parse()
    parsers = {}
    for name, parser in _subparsers(odatix_main.ArgParser.parser).items():
        if name == "results":
            for result_type, type_parser in _subparsers(parser).items():
                parsers["results " + result_type] = type_parser
        else:
            parsers[name] = parser
    return parsers


#: Every command line a parser reads.
COMMAND_LINES = sorted(
    [name for name in odatix_main.COMMANDS if name != "results"]
    + ["results " + result_type for result_type in odatix_main.RESULT_TYPES]
)


def _reads(source, dest):
    import re

    # Read as an attribute, or by name ("for name in ("tools", "flows")").
    return re.search(r"args\." + dest + r"\b|[\"']" + dest + r"[\"']", source) is not None


def _readers(command):
    """The code that reads the options of a command."""
    import inspect

    import odatix.components.clean as cln
    import odatix.components.export_analysis as exp_analysis
    import odatix.components.export_derived_metrics as exp_derived
    import odatix.components.export_results as exp_res
    import odatix.components.export_simulation_results as exp_sim_res
    import odatix.components.export_workflow_results as exp_workflow_res
    import odatix.components.generate_configs as gen_configs
    import odatix.components.migrate as migrate_cmd
    import odatix.components.replace_params as replace_params
    import odatix.components.run_analysis as run_analysis
    import odatix.components.run_fixed_freq_synthesis as run_fixed_freq_synthesis
    import odatix.components.run_dse as run_dse
    import odatix.components.run_fmax_synthesis as run_fmax_synthesis
    import odatix.components.run_pnr as run_pnr
    import odatix.components.run_simulations as run_simulations
    import odatix.components.run_workflow as run_workflow

    readers = {
        "init": [odatix_main.init_directory],
        "migrate": [migrate_cmd.main],
        "generate": [gen_configs.main],
        "replace": [replace_params.main],
        "fmax": [run_fmax_synthesis.main],
        "synth": [run_fixed_freq_synthesis.main],
        "pnr": [run_pnr.main],
        "analyze": [run_analysis.main],
        "sim": [run_simulations.main],
        "workflow": [run_workflow.main],
        "dse": [run_dse.main, run_dse.apply_arguments, run_dse.apply_campaign_arguments],
        "monitor": [odatix_main.monitor_daemon],
        "stop": [odatix_main.stop_daemon, odatix_main.kill_zombie_sessions],
        "ps": [odatix_main.list_daemons],
        "ls": [odatix_main.ls_command.main],
        "results all": [odatix_main.export_all_results, odatix_main.export_results_command],
        "results synth": [exp_res.main],
        "results workflow": [exp_workflow_res.main],
        "results sim": [exp_sim_res.main],
        "results analysis": [exp_analysis.main],
        "results derived": [exp_derived.main],
        "clean": [cln.main],
    }[command]
    return "\n".join(inspect.getsource(reader) for reader in readers)


def _run_api_source():
    import inspect

    import odatix.run.flows as flows
    import odatix.run.run as run

    return inspect.getsource(flows) + inspect.getsource(run)


#: Read by odatix_main.main() itself, whatever the command.
GLOBAL_DESTS = {"help", "version", "command", "result_type", "nobanner"}


class TestEveryOptionIsRead:
    """An option nothing reads is a lie the help tells: there must be none."""

    def test_every_command_is_dispatched(self):
        assert sorted(subcommand_parsers()) == COMMAND_LINES
        assert sorted(odatix_main.RESULT_COMMANDS) == sorted(odatix_main.RESULT_TYPES)

    @pytest.mark.parametrize("command", COMMAND_LINES)
    def test_every_destination_is_read(self, command):
        from odatix.run.options import RunOptions

        parser = subcommand_parsers()[command]
        source = _readers(command)
        is_run_command = command in RUN_COMMANDS
        run_api = _run_api_source()

        for action in parser._actions:
            dest = action.dest
            if dest in GLOBAL_DESTS or isinstance(action, argparse._HelpAction):
                continue
            if _reads(source, dest):
                continue
            assert is_run_command, "{0}: {1} is never read".format(command, dest)
            if dest == "noexport":
                continue  # the empty result path of RunOptions.from_namespace
            # Copied into the run options, which must then be used.
            assert RunOptions.spec(dest) is not None, "{0}: {1} is never read".format(command, dest)
            assert (
                "options." + dest in run_api or "options." + dest in source
                or '"' + dest + '"' in run_api or "run." + dest in run_api
            ), "{0}: run option {1} is never used".format(command, dest)

    def test_a_shared_option_keeps_its_destination(self):
        from odatix.components.cli_options import OPTIONS

        destinations = {}
        for name, (flags, keywords) in OPTIONS.items():
            for flag in flags:
                if flag.startswith("--"):
                    destinations[flag] = keywords.get("dest", name)

        # Where a long option knowingly means something else.
        exceptions = {
            # A generic text tool, with letters of its own.
            ("replace", "--input"),
            # Repeatable: the exploration chooses among them.
            ("dse", "--tool"), ("dse", "--flow"),
            # The exploration's own settings file, not a run settings file.
            ("dse", "--input"),
            # The whole work tree a place & route reads its sources from.
            ("pnr", "--work"),
        }
        for command, parser in subcommand_parsers().items():
            for action in parser._actions:
                for flag in action.option_strings:
                    if flag in destinations and (command, flag) not in exceptions:
                        assert action.dest == destinations[flag], "{0} {1}".format(command, flag)
