"""
Roadmap, lot B1: the plan before a run, the jobs left to a session, the steps a
resumed job runs, "odatix-explorer -c" and the expected findings written from
the GUI.
"""

import importlib
import os

import dash
import pytest

from odatix.components.run_common import run_overview
from odatix.lib.run_report import Category, JobPlan
from odatix.run.planner import JobPlanner

SOURCES = os.path.join(os.path.dirname(__file__), os.pardir, "sources", "odatix")


######################################
# The plan before a run (SE-16)
######################################

def test_overview_names_tool_target_flow_and_parallel_jobs():
    line = run_overview(2, tool="vivado", targets=["xc7a100t"], flow="standard", nb_jobs=4)
    assert line == "Total: 2 jobs | tool: vivado | target: xc7a100t | flow: standard | 2 in parallel"


def test_overview_leaves_out_what_it_does_not_know():
    assert run_overview(1) == "Total: 1 job"
    assert run_overview(3, targets=["a", "b"], nb_jobs="auto") == "Total: 3 jobs | targets: a, b"


######################################
# Jobs a session already has (SE-20)
######################################

def test_job_left_to_a_session_is_not_called_a_daemon_job():
    entry = {"session_id": "12.x", "status": "success"}
    message = JobPlanner.skipped_message('"slow2"', entry)
    assert message == 'Already in session 12.x (success): "slow2" skipped.'
    assert "daemon" not in JobPlanner.requeued_message('"slow2"', {"session_id": "12.x", "status": "failed"})


@pytest.mark.parametrize("path", ["run/planner.py", "lib/architecture_handler.py", "lib/simulation_handler.py"])
def test_no_note_repeats_the_checklist(path):
    """The checklist lists the jobs already done: no per-job note says it again (AP-14)."""
    with open(os.path.join(SOURCES, path), encoding="utf-8") as f:
        source = f.read()
    for text in ("Found existing daemon job", "previously failed/canceled daemon", "Found cached results",
                 "Every requested step is already done"):
        assert text not in source


######################################
# The steps a resumed job runs (AP-07)
######################################

def test_planner_records_the_steps_of_a_resumed_job(monkeypatch):
    import odatix.lib.job_steps as job_steps

    monkeypatch.setattr(job_steps, "resume_index", lambda tmp_dir, steps: 1)
    planner = JobPlanner(requested_steps=["synthesis", "pnr", "bitstream"])
    assert planner.record("Counter/8bits", "resume", tmp_dir="/w/job")
    assert planner.plan.entries[0]["details"] == {"steps": ["pnr", "bitstream"]}
    planner.record("Counter/16bits", "new", tmp_dir="/w/job2")
    assert planner.plan.entries[1]["details"] == {}


def test_run_popup_shows_the_steps():
    from odatix.gui.jobs_config import run_popup

    plan = JobPlan()
    plan.add("Counter/8bits (xc7)", Category.RESUME, steps=["pnr", "bitstream"])
    entries = run_popup._bucket_entries(plan, True)
    assert entries == [("Counter/8bits (xc7)", Category.RESUME, "pnr → bitstream")]
    card = run_popup._bucket_content(entries)[0]
    assert "steps: pnr → bitstream" in str(card)


######################################
# odatix-explorer -c
######################################

def test_explorer_reads_the_result_path_of_the_settings_file(tmp_path):
    from odatix.odatix_explorer import result_directory

    config = tmp_path / "odatix.yml"
    config.write_text("workspace: odatix\nresult_path: my_results\n", encoding="utf-8")
    assert result_directory(None, str(config)) == os.path.join(str(tmp_path), "my_results")
    assert result_directory("other", str(config)) == "other"
    assert result_directory(None, str(tmp_path / "missing.yml")) == "results"


######################################
# Expected findings written from the GUI (AP-09)
######################################

def _analysis_page():
    # dash.register_page (called at page-module import) requires an app
    dash.Dash(__name__, use_pages=True, pages_folder="")
    return importlib.import_module("odatix.explorer.pages.analysis")


FINDING = {
    "tool": "verilator", "design": "Example_ALU_sv/04bits", "category": "unused", "severity": "warning",
    "code": "UNUSEDSIGNAL", "subject": "i_sel_op", "message": "Bits of signal are not used: 'i_sel_op'[4]",
}


def test_expectation_from_a_finding_matches_it():
    import odatix.lib.analysis as analysis

    page = _analysis_page()
    conditions = page.expectation_from_finding(FINDING, scope="architecture", tool_only=True, reason="on purpose")
    assert conditions == {
        "category": "unused", "code": "UNUSEDSIGNAL", "subject": "i_sel_op",
        "tools": ["verilator"], "architectures": ["Example_ALU_sv"], "reason": "on purpose",
    }
    expectation = analysis.Expectation.from_settings("x", conditions)
    finding = analysis.Finding(category="unused", severity="warning", message=FINDING["message"],
                               code="UNUSEDSIGNAL", subject="i_sel_op")
    assert expectation.matches(finding, tool="verilator", design="Example_ALU_sv/16bits")
    assert not expectation.matches(finding, tool="vivado", design="Example_ALU_sv/16bits")


def test_expectation_without_subject_matches_the_message_literally():
    page = _analysis_page()
    finding = dict(FINDING, subject="", code="")
    conditions = page.expectation_from_finding(finding, scope="all", tool_only=False, reason="r")
    assert set(conditions) == {"category", "message", "reason"}
    import re
    assert re.search(conditions["message"], FINDING["message"])


def test_expected_name_is_unique():
    page = _analysis_page()
    assert page._expect_name(FINDING, {}) == "unused_i_sel_op"
    assert page._expect_name(FINDING, {"unused_i_sel_op": {}}) == "unused_i_sel_op_2"


def test_only_the_gui_can_write_expected_findings():
    page = _analysis_page()
    assert not page._can_edit({"result_path": "results"})
    assert page._can_edit({"result_path": "results", "analyze_settings_file": "a.yml"})


######################################
# Tool Editor, a new tool (TF-11)
######################################

def _tool_editor():
    dash.Dash(__name__, use_pages=True, pages_folder="")
    return importlib.import_module("odatix.gui.pages.tool_editor")


def test_a_new_tool_starts_unsaved():
    te = _tool_editor()
    assert "warning" in str(te.tool_title("new_tool1", new=True))
    assert "warning" not in str(te.tool_title("yosys"))


def test_the_saved_line_survives_the_new_address():
    te = _tool_editor()
    assert "success" in str(te.saved_feedback("?tool=x&saved=1", te.page_path))
    with pytest.raises(dash.exceptions.PreventUpdate):
        te.saved_feedback("?tool=x", te.page_path)


######################################
# Optional keys are not noted (TF-08)
######################################

def test_a_tool_without_format_is_not_noted(tmp_path, capsys):
    from odatix.lib.parallel_job_handler.job_output_formatter import JobOutputFormatter

    tool_file = tmp_path / "tool.yml"
    tool_file.write_text("label: x\n", encoding="utf-8")
    JobOutputFormatter(str(tool_file))
    assert "format" not in capsys.readouterr().out
