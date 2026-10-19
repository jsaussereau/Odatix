"""
Tools, targets and flows of your own: what a tool needs to run and export, and
what the API and the GUI write for it.

Non-regression tests of the "new user" review of the tools, targets and flows:
a tool writing no status file loses no result, a non-tcl tool gets its
frequency and constraint files, a new tool or target file runs as written, a
copied built-in tool is the whole tool.
"""

import os
import textwrap
import types

import dash
import pytest

from odatix.lib.settings import OdatixSettings
from odatix.workspace import Workspace
from odatix.workspace.errors import NotFoundError
from odatix.workspace.yaml_io import read_yaml


@pytest.fixture
def workspace(example_workspace, monkeypatch):
    tools_dir = str(example_workspace / "odatix_userconfig" / "tools")
    os.makedirs(tools_dir, exist_ok=True)
    monkeypatch.setattr(OdatixSettings, "user_tools_path", tools_dir)
    return Workspace.open(str(example_workspace))


def write(path, content):
    directory = os.path.dirname(str(path))
    if directory and not os.path.isdir(directory):
        os.makedirs(directory)
    with open(str(path), "w", encoding="utf-8") as handle:
        handle.write(textwrap.dedent(content))


@pytest.fixture(scope="module")
def pages():
    # dash.register_page (called at page-module import) requires an app
    dash.Dash(__name__, use_pages=True, pages_folder="")
    import odatix.gui.pages.tool_editor as tool_editor
    import odatix.gui.pages.metric_editor as metric_editor
    import odatix.gui.pages.select_targets as select_targets
    import odatix.gui.pages.choose_eda_tool as choose_eda_tool
    import odatix.gui.pages.tools as tools_page

    return types.SimpleNamespace(
        tool_editor=tool_editor, metric_editor=metric_editor, select_targets=select_targets,
        choose_eda_tool=choose_eda_tool, tools=tools_page,
    )


######################################
# F-01: exported on exit code 0, status file or not
######################################

class TestCompletionMarker(object):

    def _job(self, tmp_path):
        job_dir = tmp_path / "work" / "mytool" / "generic" / "Arch" / "cfg" / "100MHz"
        (job_dir / "log").mkdir(parents=True)
        write(job_dir / "report" / "cells.rep", "Cells: 42\n")
        return job_dir

    def test_a_successful_job_without_status_file_is_marked_done(self, tmp_path):
        from odatix.components.export_results import mark_job_done, is_marked_done, find_status_log

        job_dir = self._job(tmp_path)
        assert not is_marked_done(find_status_log(str(job_dir), "custom_freq_synthesis"))
        assert mark_job_done(str(job_dir), "custom_freq_synthesis")
        assert (job_dir / "log" / "synth_status.log").read_text(encoding="utf-8").strip() == "Done: 100%"
        # Idempotent: a marker already there is not written twice.
        mark_job_done(str(job_dir), "custom_freq_synthesis")
        assert (job_dir / "log" / "synth_status.log").read_text(encoding="utf-8").count("Done: 100%") == 1

    def test_an_fmax_job_is_marked_in_its_own_status_file(self, tmp_path):
        from odatix.components.export_results import mark_job_done

        job_dir = tmp_path / "job"
        mark_job_done(str(job_dir), "fmax_synthesis")
        assert "Done: 100%" in (job_dir / "log" / "status.log").read_text(encoding="utf-8")

    def test_the_per_job_export_keeps_the_results_of_a_tool_writing_no_status(self, tmp_path, monkeypatch):
        import odatix.components.export_results as export_results

        job_dir = self._job(tmp_path)
        metrics = {"metrics": {"Cells": {"type": "regex", "settings": {
            "file": "report/cells.rep", "pattern": "Cells: ([0-9]+)", "group_id": 1}}}}
        monkeypatch.setattr(export_results, "_load_metrics_for_tool",
                            lambda tool, custom_metrics_file=None, flow=None: (metrics, "metrics.yml"))
        config = {
            "kind": "synthesis", "result_type": "custom_freq_synthesis", "tool": "mytool",
            "input_tool_path": str(tmp_path / "work" / "mytool"), "output_dir": str(tmp_path / "results"),
            "target": "generic", "architecture": "Arch", "configuration": "cfg", "frequency": "100MHz",
        }
        assert export_results.export_single_job_result(None, export_config=config)
        export_results.results_cache.flush()
        data = read_yaml(str(tmp_path / "results" / "results_mytool.yml"))
        assert str(data["results"][0]["metrics"]["Cells"]) == "42"
        # A full re-export (odatix results) now agrees.
        units = {}
        records = export_results.process_configuration(
            str(tmp_path / "work" / "mytool"), "generic", "Arch", "cfg", "100MHz",
            "custom_freq_synthesis", "custom_freq_synthesis", units, metrics, "metrics.yml", tool="mytool",
        )
        assert records and str(records[0]["metrics"]["Cells"]) == "42"

    def test_an_unfinished_job_says_which_file_and_marker(self, tmp_path, capsys):
        import odatix.components.export_results as export_results

        job_dir = self._job(tmp_path)
        write(job_dir / "log" / "synth_status.log", "In progress: 50%\n")
        records = export_results.process_configuration(
            str(tmp_path / "work" / "mytool"), "generic", "Arch", "cfg", "100MHz",
            "custom_freq_synthesis", "custom_freq_synthesis", {}, {}, "metrics.yml", tool="mytool",
        )
        assert records is None
        out = capsys.readouterr().out
        assert os.path.join("mytool", "generic", "Arch", "cfg", "100MHz") in out
        assert os.path.join("log", "synth_status.log") + ' does not contain "Done: 100%"' in out


######################################
# F-02 / F-10: what a job directory holds, the variables of its command
######################################

class TestJobFiles(object):

    def _arch(self, tmp_path, frequency=100, constraint="constraints.sdc"):
        return types.SimpleNamespace(
            tmp_dir=str(tmp_path), target_frequency=frequency, constraint_filename=constraint,
            clock_signal="clk",
        )

    def test_frequency_and_constraint_files_are_written(self, tmp_path):
        from odatix.lib.prepare_work import write_frequency_files

        write_frequency_files(self._arch(tmp_path))
        assert (tmp_path / "frequency.txt").read_text(encoding="utf-8") == "100 MHz\n"
        assert (tmp_path / "constraints.sdc").read_text(encoding="utf-8") == "create_clock -period 10 [get_ports clk]\n"

    def test_files_already_there_are_kept(self, tmp_path):
        # A job resuming after a completed step keeps what its tool wrote.
        from odatix.lib.prepare_work import write_frequency_files

        write(tmp_path / "constraints.sdc", "100\n")
        write_frequency_files(self._arch(tmp_path))
        assert (tmp_path / "constraints.sdc").read_text(encoding="utf-8") == "100\n"

    def test_an_fmax_search_gets_none(self, tmp_path):
        from odatix.lib.prepare_work import write_frequency_files

        write_frequency_files(self._arch(tmp_path, frequency=0))
        assert os.listdir(str(tmp_path)) == []

    def test_architecture_is_one_word_and_empty_install_path_stays_empty(self, tmp_path):
        from odatix.components.synthesis_common import build_job_variables

        arch = types.SimpleNamespace(
            tmp_dir=str(tmp_path), install_path="", clock_signal="clk", top_level_module="top",
            lib_name="WORK", arch_name="Counter/08bits", arch_display_name="Counter/08bits @ 100 MHz",
            target="generic",
        )
        variables = build_job_variables(arch, "vivado")
        from odatix.lib.variables import replace_variables

        assert replace_variables("[$architecture] [$tool_install_path]", variables) == "[Counter/08bits] []"


######################################
# F-03: a tool's metrics file
######################################

class TestMetricsFile(object):

    def test_a_tool_keeping_metrics_next_to_its_tool_yml_needs_no_key(self, workspace):
        import odatix.lib.metrics as metrics_lib

        tool_dir = workspace.tools.entry("mytool").path
        write(os.path.join(tool_dir, "tool.yml"), "unix:\n  tool_test_command: 'true'\n")
        write(os.path.join(tool_dir, "metrics.yml"), "metrics:\n  Cells: {type: regex}\n")
        assert metrics_lib.metrics_file_template("mytool") == "$tool_path/metrics.yml"
        data, _source = metrics_lib.load_metrics("mytool")
        assert "Cells" in data["metrics"]

    def test_a_new_tool_in_the_editor_declares_its_metrics_file(self, pages, workspace):
        settings, _builtin, overlay, _params = pages.tool_editor.load_editor_settings(workspace.tools, "new_tool1")
        assert not overlay
        assert settings["default_metrics_file"] == "$tool_path/metrics.yml"
        assert pages.tool_editor.load_editor_settings(workspace.tools, "")[0]["default_metrics_file"]

    def test_api_created_tool_declares_it_too(self, workspace):
        tool = workspace.tools.create("mytool")
        assert read_yaml(tool.settings_path)["default_metrics_file"] == "$tool_path/metrics.yml"


######################################
# F-04: target files of a new tool
######################################

class TestTargetFiles(object):

    def test_a_new_target_file_runs_as_written(self, workspace):
        target_file = workspace.targets["mytool"]
        target_file.add("generic")
        data = read_yaml(target_file.path)
        assert data["targets"] == ["generic"]
        assert data["constraint_file"] == "constraints.sdc"
        assert data["tool_install_path"] == ""
        assert data["force_single_thread"] is False
        assert data["script_copy_enable"] is False

    def test_tool_settings_are_editable(self, workspace):
        target_file = workspace.targets["mytool"]
        target_file.add("generic")
        target_file.update(constraint_file="timing.sdc", tool_install_path="/opt/mytool", force_single_thread=True)
        reloaded = workspace.targets["mytool"]
        assert reloaded.constraint_file == "timing.sdc"
        assert reloaded.tool_install_path == "/opt/mytool"
        assert reloaded.force_single_thread is True
        assert reloaded.names() == ["generic"]
        with pytest.raises(ValueError):
            reloaded.update(nonsense=1)

    def test_an_existing_file_keeps_its_comments(self, workspace):
        target_file = workspace.targets["vivado"]
        before = open(target_file.path, encoding="utf-8").read()
        target_file.update(tool_install_path="/opt/Xilinx")
        after = open(target_file.path, encoding="utf-8").read()
        assert "/opt/Xilinx" in after
        assert after.count("\n#") >= before.count("\n#") - 1

    def test_select_targets_shows_what_a_new_file_will_hold(self, pages, workspace):
        values = pages.select_targets.tool_settings_values("?tool=mytool", {})
        assert values == {"constraint_file": "constraints.sdc", "tool_install_path": "", "force_single_thread": False}
        assert not pages.select_targets.tool_settings_changed("constraints.sdc", "", [], values)
        assert pages.select_targets.tool_settings_changed("constraints.sdc", "/opt", [], values)

    def test_constraint_file_is_optional(self, workspace):
        # read by the run flows (see synthesis_common), defaulting to SDC
        from odatix.lib.prepare_work import DEFAULT_CONSTRAINT_FILE

        assert workspace.targets["mytool"].constraint_file == DEFAULT_CONSTRAINT_FILE


######################################
# F-06 / F-19: copying a built-in tool, its read-only flows
######################################

class TestBuiltinCopies(object):

    def _overlay(self, workspace):
        vivado = workspace.tools["vivado"]
        flow = vivado.settings.add_flow("retiming", label="Retiming")
        flow.parameters = {"synth_options": ["-retiming"]}
        vivado.save()
        metrics = vivado.metrics
        metrics.set("Mine", {"type": "regex", "settings": {"file": "report/x.rep", "pattern": "(1)", "group_id": 1}})
        metrics.save()
        write(os.path.join(vivado.path, "tcl", "extra.tcl"), "# mine\n")

    def test_the_copy_is_the_whole_tool_with_the_overlay(self, workspace):
        self._overlay(workspace)
        copy = workspace.tools.import_builtin("vivado", "vivado_mine")
        settings = copy.settings
        assert "standard" in settings.flow_names() and "retiming" in settings.flow_names()
        assert settings.default_flow.steps("custom_freq_synthesis")
        assert settings.default_metrics_file == "$tool_path/metrics.yml"
        assert os.path.isfile(os.path.join(copy.path, "tcl", "extra.tcl"))
        assert os.path.isfile(os.path.join(copy.path, "tcl", "step_common.tcl"))
        assert "Mine" in copy.metrics.sections["metrics"]
        assert "LUT_count" in str(copy.metrics.sections)
        assert "$eda_tools_path/vivado/" not in open(copy.settings_path, encoding="utf-8").read()

    def test_the_copy_gets_the_targets(self, workspace):
        workspace.tools.import_builtin("vivado", "vivado_mine")
        assert workspace.targets["vivado_mine"].names() == workspace.targets["vivado"].names()

    def test_a_tool_sharing_a_target_file_keeps_sharing_it(self, workspace):
        copy = workspace.tools.import_builtin("dc_nxt", "dc_mine")
        assert copy.settings.target_file == "target_design_compiler.yml"
        assert not os.path.isfile(os.path.join(workspace.paths.target_path, "target_dc_mine.yml"))

    def test_duplicating_a_workspace_tool_copies_its_target_file(self, workspace):
        workspace.tools.create("mytool")
        workspace.targets["mytool"].add("generic")
        workspace.tools.duplicate("mytool", "mytool2")
        assert workspace.targets["mytool2"].names() == ["generic"]

    def test_changing_a_builtin_flow_is_refused(self, workspace):
        vivado = workspace.tools["vivado"]
        vivado.settings.flow("standard").parameters = {"x": 1}
        with pytest.raises(ValueError) as error:
            vivado.save()
        assert "standard" in str(error.value)

    def test_adding_a_flow_to_a_builtin_still_saves(self, workspace):
        self._overlay(workspace)
        assert "retiming" in workspace.tools["vivado"].settings.flow_names()


######################################
# F-16: job types
######################################

def test_set_command_names_the_valid_job_types():
    from odatix.workspace.tools import Flow

    flow = Flow("x")
    flow.set_command("tool_test", "mytool --version")
    assert flow.command("tool_test")
    with pytest.raises(NotFoundError) as error:
        flow.set_command("synthesis", "x")
    assert "custom_freq_synthesis" in str(error.value)


######################################
# GUI: F-12, F-13, F-22, F-23
######################################

class TestPages(object):

    def test_tool_metrics_have_a_place_and_route_section(self, pages, workspace):
        me = pages.metric_editor
        out = me.init_page("?tool=innovus", "/metric_editor", {})
        initial = out[8]
        assert "metric4" in initial["sections"]
        assert out[11] == {"display": "block"}          # innovus runs place & route
        assert "Add new metric" in str(out[6]) and "Add new metadata" not in str(out[6])
        out = me.init_page("?tool=verilator", "/metric_editor", {})
        assert out[11] == {"display": "none"}

    def test_add_text_says_metadata_only_for_workflows(self, pages):
        me = pages.metric_editor
        assert me.add_text_for(me.META_PREFIX, "workflow") == "Add new metadata"
        assert me.add_text_for(me.META_PREFIX, "tool") == "Add new metric"

    def test_tool_metrics_save_keeps_pnr_metrics(self, pages, workspace):
        me = pages.metric_editor
        assert ("metric4", "Place & route metrics", me.PNR_TOOLTIP, "pnr_metrics") in me.TOOL_SECTIONS

    def test_dc_nxt_flows_are_not_custom(self, pages, workspace):
        assert pages.choose_eda_tool.custom_flow_names("custom_freq_synthesis", "dc_nxt") == frozenset()

    def test_workspace_tool_card_shows_label_and_description(self, pages, workspace):
        tool = workspace.tools.create("mytool", label="My tool", description="Mine, all mine")
        card = str(pages.tools.workspace_tool_card(tool))
        assert "My tool" in card and "Mine, all mine" in card

    def test_log_level_placeholders_differ(self, pages):
        placeholders = [pages.tool_editor.LOG_PLACEHOLDERS[level] for level, _label in pages.tool_editor.LOG_LEVELS]
        assert len(set(placeholders)) == len(placeholders)

    def test_title_and_form_are_rendered_together(self, pages, workspace):
        # save_and_status reads both: rendered apart, Dash reports tool-extends
        # as a nonexistent object.
        out = pages.tool_editor.init_form("?tool=vivado", "/tool_editor", {})
        assert len(out) == 10
        assert "tool-title" in str(out[-1])
        assert "tool-extends" in str(out[0])
