"""
Regressions of the RTL analysis and place & route runs, as a new user meets
them: a missing tool, a finished analysis run again, a flow given to several
tools, the place & route sources a fresh workspace selects, and what a run says
when its selection or its tools cannot work.
"""

import os

import pytest
import yaml

import odatix.lib.analysis as analysis
import odatix.lib.hard_settings as hard_settings
import odatix.lib.pnr_handler as pnr_handler
import odatix.lib.pnr_source as pnr_source
import odatix.lib.printc as printc
from odatix.lib.run_report import Category
from odatix.lib.settings import OdatixSettings
from odatix.run import Run, RunError
from odatix.workspace import Workspace

from test_analysis import make_job, result_of


def collected(action):
    """Run action(), returning [(level, message)] of what it printed, and its SystemExit code if any."""
    messages = []
    code = None
    with printc.collect(lambda level, message, _script: messages.append((level, message))):
        try:
            action()
        except SystemExit as stop:
            code = stop.code
    return messages, code


######################################
# A tool that is not there
######################################

class TestMissingTool:
    @pytest.mark.parametrize("tool,log,console", [
        # What the environment script of a tool says (quartus_env.sh)
        ("quartus", None, "error: quartus_sh not found\nnote: put the Quartus executables in your PATH\n"),
        # What a shell says, the command line being written to the tool's own log
        ("verilator", "/bin/sh: line 1: verilator: command not found\n", None),
        ("verilator", "sh: 1: verilator: not found\n", None),
        ("vivado", None, "zsh: command not found: vivado\n"),
    ])
    def test_is_a_tool_failure(self, tmp_path, tool, log, console):
        job = make_job(tmp_path, "D", log, complete=log is not None)
        if console is not None:
            with open(os.path.join(job, "log", hard_settings.console_log_filename), "w", encoding="utf-8") as f:
                f.write(console)
        result = result_of(tool, job)
        assert result.status == analysis.STATUS_TOOL_FAILURE
        assert result.main_finding.category == "tool_setup"
        assert "not found" in result.main_finding.message

    def test_a_module_not_found_is_still_a_design_error(self, tmp_path):
        result = result_of("vivado", make_job(tmp_path, "D", "ERROR: [Synth 8-439] module 'sub' not found\n"))
        assert result.status == analysis.STATUS_FAILED


class TestVerilatorSyntaxError:
    def test_cannot_continue_is_no_finding_of_its_own(self, tmp_path):
        log = "%Error: rtl/top.sv:3:1: syntax error, unexpected endmodule\n%Error: Cannot continue\n"
        result = result_of("verilator", make_job(tmp_path, "D", log))
        assert result.status == analysis.STATUS_FAILED
        assert [finding.category for finding in result.findings] == ["syntax"]


######################################
# --flow with several tools
######################################

class TestFlowSelection:
    def test_a_bare_flow_applies_to_the_tools_that_have_it(self):
        from odatix.components.run_analysis import parse_flow_selection

        flows = {}
        messages, code = collected(lambda: flows.update(parse_flow_selection(["runtime"], ["vivado", "verilator"])))
        assert code is None
        assert flows == {"vivado": "runtime", "verilator": None}
        assert any("verilator" in message and "default flow" in message for _level, message in messages)

    def test_a_flow_no_tool_has_is_still_reported(self):
        from odatix.components.run_analysis import parse_flow_selection

        assert parse_flow_selection(["no_such_flow"], ["vivado", "verilator"]) == {
            "vivado": "no_such_flow", "verilator": "no_such_flow",
        }

    def test_a_prefixed_flow_only_applies_to_its_tool(self):
        from odatix.components.run_analysis import parse_flow_selection

        assert parse_flow_selection(["vivado:runtime"], ["vivado", "verilator"]) == {"vivado": "runtime", "verilator": None}


######################################
# A finished analysis
######################################

def analysis_job_dir(workspace, tool, architecture, configuration):
    return workspace / "work" / "analysis" / tool / hard_settings.default_analysis_target / architecture / configuration


class TestFinishedAnalysis:
    def plan(self, **options):
        run = Run(Workspace.open(), "analysis", tool=["verilator"], architectures=["Example_Counter_sv/08bits"],
                  check_eda_tool=False, **options)
        return run.check()

    def finish(self, workspace):
        job = analysis_job_dir(workspace, "verilator", "Example_Counter_sv", "08bits")
        (job / "log").mkdir(parents=True)
        (job / "log" / hard_settings.synth_status_filename).write_text(hard_settings.valid_status + "\n", encoding="utf-8")

    def test_a_new_analysis_runs(self, example_workspace):
        assert self.plan().counts().get(Category.NEW) == 1

    def test_is_not_run_again_without_overwrite(self, example_workspace):
        self.finish(example_workspace)
        with pytest.raises(RunError) as error:
            self.plan()
        assert "Nothing to run" in str(error.value)

    def test_runs_again_with_overwrite(self, example_workspace):
        self.finish(example_workspace)
        assert self.plan(overwrite=True).counts().get(Category.OVERWRITE) == 1

    def test_an_unfinished_one_runs_again(self, example_workspace):
        job = analysis_job_dir(example_workspace, "verilator", "Example_Counter_sv", "08bits")
        (job / "log").mkdir(parents=True)
        (job / "log" / hard_settings.synth_status_filename).write_text("Running\n", encoding="utf-8")
        assert self.plan().counts().get(Category.INCOMPLETE) == 1


######################################
# What a fresh workspace ships
######################################

def shipped(*path):
    return os.path.join(*path)


class TestShippedSettings:
    @pytest.mark.parametrize("root", [OdatixSettings.odatix_init_path, OdatixSettings.odatix_examples_path])
    def test_place_and_route_takes_every_completed_synthesis(self, root):
        with open(shipped(root, "odatix_userconfig", "pnr_settings.yml"), encoding="utf-8") as f:
            sources = yaml.safe_load(f)["sources"]
        assert "custom_freq_synthesis/*/*/*/*" in sources
        assert "fmax_synthesis/*/*/*/*" in sources

    def test_the_analysis_of_a_bare_workspace_names_no_design_it_lacks(self):
        with open(shipped(OdatixSettings.odatix_init_path, "odatix_userconfig", "analyze_settings.yml"), encoding="utf-8") as f:
            assert not yaml.safe_load(f)["architectures"]

    def test_the_example_analysis_names_existing_designs(self):
        root = OdatixSettings.odatix_examples_path
        with open(shipped(root, "odatix_userconfig", "analyze_settings.yml"), encoding="utf-8") as f:
            text = f.read()
        architectures = os.listdir(shipped(root, "odatix_userconfig", "architectures"))
        named = [line.split("-", 1)[1].strip().split("/")[0] for line in text.splitlines()
                 if line.strip().lstrip("#").strip().startswith("- Example_")]
        assert named and all(name in architectures for name in named), named


######################################
# Place & route: what the run says
######################################

def completed_source(work_root, tool="design_compiler", target="AMS_c35_1V8"):
    job_dir = work_root / "custom_freq_synthesis" / tool / target / "counter" / "8bits" / "100MHz"
    (job_dir / hard_settings.work_result_path).mkdir(parents=True)
    (job_dir / hard_settings.work_log_path).mkdir(parents=True)
    (job_dir / hard_settings.work_log_path / hard_settings.synth_status_filename).write_text(hard_settings.valid_status, encoding="utf-8")
    for filename in (hard_settings.pnr_netlist_filename, hard_settings.pnr_sdc_filename, hard_settings.pnr_sdf_filename):
        (job_dir / hard_settings.work_result_path / filename).write_text("handoff", encoding="utf-8")
    return job_dir


class TestPnrSelection:
    def handler(self, tmp_path):
        return pnr_handler.PnrJobHandler(
            work_path=str(tmp_path / "pnr"), source_work_root=str(tmp_path), script_path="scripts",
            work_rtl_path="rtl", work_script_path="scripts", work_log_path="logs", work_report_path="reports",
            process_group=True, command="run-pnr", eda_target_filename=str(tmp_path / "none.yml"), overwrite=False,
        )

    def test_a_selection_matching_nothing_lists_the_sources(self, tmp_path):
        completed_source(tmp_path)
        handler = self.handler(tmp_path)
        jobs = []
        messages, _ = collected(lambda: jobs.extend(handler.get_pnr_jobs(["custom_freq_synthesis/genus/*/*/*"])))
        assert jobs == []
        assert any(level == "error" for level, _message in messages)
        assert any("custom_freq_synthesis/design_compiler/AMS_c35_1V8/counter/8bits@100MHz" in message
                   for _level, message in messages)

    def test_a_wildcard_matching_nothing_is_no_warning(self, tmp_path):
        completed_source(tmp_path)
        sources = pnr_source.discover_sources(str(tmp_path))
        messages, _ = collected(lambda: pnr_source.match_sources(sources, ["custom_freq_synthesis/*/*/*/*", "fmax_synthesis/*/*/*/*"]))
        assert not any(level in ("warning", "error") for level, _message in messages)


class TestPnrOptions:
    def test_an_unknown_source_flow_is_refused(self):
        from odatix.components.run_pnr import _restrict_selectors

        messages, code = collected(lambda: _restrict_selectors(["custom_freq_synthesis/*/*/*/*"], None, "genus", "fast"))
        assert code not in (None, 0)
        assert any('"fast"' in message for _level, message in messages)
        assert any("timing" in message for _level, message in messages)

    def test_a_source_flow_without_its_tool_names_the_settings(self):
        from odatix.components.run_pnr import _restrict_selectors

        messages, code = collected(lambda: _restrict_selectors(["custom_freq_synthesis/*/*/*/*"], None, None, "timing"))
        assert code not in (None, 0)
        error = [message for level, message in messages if level == "error"][0]
        assert "from_flow" in error and "from_tool" in error

    def test_a_known_source_flow_narrows_the_selection(self):
        from odatix.components.run_pnr import _restrict_selectors

        assert _restrict_selectors(["custom_freq_synthesis/*/*/*/*"], None, "genus", "timing") == [
            "custom_freq_synthesis/genus@timing/*/*/*",
        ]

    def test_a_tool_without_place_and_route_is_said_first(self, example_workspace):
        # The shipped settings file is fine, the tool is not: say so, and which can.
        with pytest.raises(RunError) as error:
            Run(Workspace.open(), "pnr", tool="vivado", check_eda_tool=False).check()
        assert "vivado" in str(error.value) and "place & route" in str(error.value)
        assert any("innovus" in text for _level, text in error.value.messages)
