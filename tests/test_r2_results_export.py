"""
Exporting results, derived metrics and clean: the findings of the second "new
user" campaign (XR-02, XR-06, XR-07, XR-10, XR-11, XR-12, SIM-104, TF-04,
GS-18, and the exit status of "odatix results", C-17/F-18).
"""

import argparse
import json
import os

import pytest

import odatix.lib.printc as printc
import odatix.lib.results_cache as results_cache
import odatix.lib.results_schema as results_schema
import odatix.lib.derived_metrics as derived_metrics
from odatix.components import export_common
from odatix.components import export_results as exp_res
from odatix.components import export_simulation_results as exp_sim_res
from odatix.components import export_derived_metrics as exp_derived
from odatix.components import results_command
from odatix.components import clean as cln


class Collected(object):
    """Every diagnostic printc emits while it is in use, by level."""

    def __init__(self):
        self.messages = []

    def __call__(self, level, message, _script_name):
        self.messages.append((level, message))

    def of(self, level):
        return [message for kind, message in self.messages if kind == level]


@pytest.fixture
def collected():
    sink = Collected()
    with printc.collect(sink):
        yield sink


def synthesis_record(configuration, metrics, frequency=100):
    return results_schema.make_record(
        {
            results_schema.META_TYPE: results_schema.TYPE_CUSTOM_FREQ,
            results_schema.META_TOOL: "vivado",
            results_schema.META_TARGET: "xc7a100t",
            results_schema.META_ARCHITECTURE: "Counter",
            results_schema.META_CONFIGURATION: configuration,
            results_schema.META_FREQUENCY: frequency,
        },
        metrics,
    )


######################################
# SIM-104: a null value is not a missing key
######################################

class TestNullIsNotMissing:
    def test_yaml_null_value_is_no_error(self, tmp_path, collected):
        report = tmp_path / "sim_report.yml"
        report.write_text("cycles: null\nstatus: failed\n", encoding="utf-8")
        assert export_common.parse_yaml(str(report), "cycles") is None
        assert collected.of("error") == []

    def test_yaml_missing_key_is_still_an_error(self, tmp_path, collected):
        report = tmp_path / "sim_report.yml"
        report.write_text("status: failed\n", encoding="utf-8")
        assert export_common.parse_yaml(str(report), "cycles") is None
        assert len(collected.of("error")) == 1 and '"cycles"' in collected.of("error")[0]

    def test_json_null_value_is_no_error(self, tmp_path, collected):
        report = tmp_path / "report.json"
        report.write_text(json.dumps({"cycles": None}), encoding="utf-8")
        assert export_common.parse_json(str(report), "cycles") is None
        assert collected.of("error") == []
        report.write_text(json.dumps({}), encoding="utf-8")
        export_common.parse_json(str(report), "cycles")
        assert len(collected.of("error")) == 1


######################################
# TF-04: the metric that could not be read is named
######################################

def test_a_metric_that_does_not_match_is_named(tmp_path, collected):
    job = tmp_path / "job"
    (job / "report").mkdir(parents=True)
    (job / "report" / "stat.txt").write_text("   42 cells\n", encoding="utf-8")
    metrics_data = {
        "metrics": {
            "Cells": {"type": "regex", "settings": {"file": "report/stat.txt", "pattern": "^ +([0-9]+) +cellz$", "group_id": 1}},
            "Logic_depth": {"type": "regex", "settings": {"file": "report/ltpx.txt", "pattern": "x", "group_id": 0}},
        }
    }
    exp_res._reset_banned_lists()
    exp_res.extract_metrics(metrics_data, "metrics.yml", str(job), "Counter[08bits]", "generic/Counter/08bits")
    errors = collected.of("error")
    assert any('metric "Cells"' in error and "No match" in error for error in errors)
    assert any('metric "Logic_depth"' in error and "does not exist" in error for error in errors)


def test_a_shared_report_is_reported_once_per_job(tmp_path, collected):
    # Every step of a job reads the same report: the job says it once.
    job = tmp_path / "job"
    (job / "report").mkdir(parents=True)
    (job / "report" / "stat.txt").write_text("nothing\n", encoding="utf-8")
    metrics_data = {"metrics": {"Cells": {"type": "regex", "settings": {"file": "report/stat.txt", "pattern": "cells", "group_id": 0}}}}
    exp_res._reset_banned_lists()
    exp_res.extract_metrics(metrics_data, "metrics.yml", str(job), "A", "A", step="synthesis", report_shared=False)
    assert collected.of("error") == []
    exp_res.extract_metrics(metrics_data, "metrics.yml", str(job), "A", "A", step="pnr", report_shared=True)
    assert len(collected.of("error")) == 1


######################################
# XR-06: an operation that cannot work is said
######################################

def _config(tmp_path, text):
    path = tmp_path / "derived_metrics.yml"
    path.write_text(text, encoding="utf-8")
    return derived_metrics.load_derived_metrics(str(path))


class TestOperationErrors:
    def test_a_syntax_error_is_reported_with_the_metric(self, tmp_path, collected):
        config = _config(tmp_path, 'derived_metrics:\n  Bad_syntax: {type: operation, op: "LUT_count / / 2"}\n')
        assert config.names == []
        errors = collected.of("error")
        assert len(errors) == 1 and "Bad_syntax" in errors[0] and "LUT_count / / 2" in errors[0]

    def test_a_name_no_record_has_is_a_warning(self, tmp_path, collected):
        config = _config(tmp_path, 'derived_metrics:\n  Typo_metric: {type: operation, op: "LUT_cnt / 2"}\n')
        records = [synthesis_record("08bits", {"LUT_count": 10}), synthesis_record("16bits", {"LUT_count": 20})]
        derived_metrics.apply_derived_metrics(config, records)
        warnings = collected.of("warning")
        assert len(warnings) == 1
        assert '"LUT_cnt"' in warnings[0] and '"Typo_metric"' in warnings[0]

    def test_an_unknown_meta_key_is_named(self, tmp_path, collected):
        config = _config(tmp_path, 'derived_metrics:\n  Per_volt: {type: operation, op: "LUT_count / meta.voltage"}\n')
        derived_metrics.apply_derived_metrics(config, [synthesis_record("08bits", {"LUT_count": 10})])
        assert any('"meta.voltage"' in warning for warning in collected.of("warning"))

    def test_a_name_only_some_records_have_is_silent(self, tmp_path, collected):
        # The documented behaviour: a record without the metric is skipped.
        config = _config(tmp_path, 'derived_metrics:\n  Half: {type: operation, op: "Power / 2"}\n')
        records = [synthesis_record("08bits", {"Power": 4}), synthesis_record("16bits", {"LUT_count": 20})]
        derived_metrics.apply_derived_metrics(config, records)
        assert records[0]["metrics"]["Half"] == 2
        assert "Half" not in records[1]["metrics"]
        assert collected.of("warning") == []

    def test_an_optional_operation_does_not_warn(self, tmp_path, collected):
        config = _config(tmp_path, 'derived_metrics:\n  Maybe: {type: operation, op: "Nothing / 2", optional: true}\n')
        derived_metrics.apply_derived_metrics(config, [synthesis_record("08bits", {"LUT_count": 10})])
        assert collected.of("warning") == []

    def test_a_failing_operation_is_reported_once(self, tmp_path, collected):
        config = _config(tmp_path, 'derived_metrics:\n  Ratio: {type: operation, op: "LUT_count / Zero"}\n')
        records = [synthesis_record(c, {"LUT_count": 10, "Zero": 0}) for c in ("08bits", "16bits")]
        derived_metrics.apply_derived_metrics(config, records)
        warnings = collected.of("warning")
        assert len(warnings) == 1 and "2 records" in warnings[0] and "ZeroDivisionError" in warnings[0]


######################################
# XR-02 and C-17/F-18: re-derive after an export, fail on a reported error
######################################

class TestResultsCommand:
    def test_every_rewriting_export_derives_again(self, monkeypatch):
        for kind in results_command.REDERIVED_KINDS:
            calls = []
            monkeypatch.setattr(exp_res, "main", lambda args: calls.append("synth"))
            monkeypatch.setattr(exp_sim_res, "main", lambda args: calls.append("sim"))
            monkeypatch.setattr(results_command, "_export_workflow", lambda args, on_exception=None: calls.append("workflow") or True)
            results_command._EXPORTERS["workflow"] = results_command._export_workflow
            monkeypatch.setattr(exp_derived, "run", lambda **kwargs: calls.append("derived") or True)
            args = argparse.Namespace(config="odatix.yml", result_path=None)
            success, errors = results_command.export(kind, args)
            assert success and errors == []
            assert calls == [kind, "derived"], kind

    def test_derived_and_analysis_do_not_derive_twice(self, monkeypatch):
        calls = []
        monkeypatch.setattr(exp_derived, "main", lambda args: calls.append("derived main"))
        monkeypatch.setattr(exp_derived, "run", lambda **kwargs: calls.append("derived run") or True)
        results_command.export("derived", argparse.Namespace(config="odatix.yml", result_path=None, derived=None))
        assert calls == ["derived main"]

    def test_a_reported_error_fails_the_export(self, monkeypatch):
        def main(args):
            printc.error("metric \"Cells\": No match", "test")
        monkeypatch.setattr(exp_res, "main", main)
        monkeypatch.setattr(exp_derived, "run", lambda **kwargs: True)
        success, errors = results_command.export("synth", argparse.Namespace(config="odatix.yml", result_path=None))
        assert not success and len(errors) == 1

    def test_the_command_line_exits_with_1(self, monkeypatch, capsys):
        import odatix.odatix_main as odatix_main

        monkeypatch.setattr(exp_res, "main", lambda args: printc.error("broken", "test"))
        monkeypatch.setattr(exp_derived, "run", lambda **kwargs: True)
        args = odatix_main.ArgParser.parse_arguments(["results", "synth"])
        assert odatix_main.export_results_command(args) is False
        assert "1 error reported above" in capsys.readouterr().out


######################################
# XR-11: nothing to export writes nothing
######################################

class TestNothingToExport:
    def test_simulation_without_work_directory_fails_and_writes_nothing(self, tmp_path, collected):
        results = tmp_path / "results"
        ok = exp_sim_res.export_simulation_results(str(tmp_path / "work" / "simulations"), str(tmp_path / "sims"), str(results))
        assert ok is False
        assert not (results / exp_sim_res.DEFAULT_OUTPUT_FILENAME).exists()
        assert any("nothing written" in error for error in collected.of("error"))

    def test_simulation_without_run_writes_nothing(self, tmp_path, collected):
        (tmp_path / "work" / "simulations").mkdir(parents=True)
        results = tmp_path / "results"
        ok = exp_sim_res.export_simulation_results(str(tmp_path / "work" / "simulations"), str(tmp_path / "sims"), str(results))
        assert ok is True and collected.of("error") == []
        assert not (results / exp_sim_res.DEFAULT_OUTPUT_FILENAME).exists()

    def test_workflow_without_work_directory_fails_and_writes_nothing(self, tmp_path, collected):
        args = argparse.Namespace(work_path=str(tmp_path / "work" / "workflows"), result_path=str(tmp_path / "results"), output="results_workflow.yml", config="odatix.yml")
        assert results_command._export_workflow(args) is False
        assert not (tmp_path / "results").exists()
        assert any("No workflow work directory" in error for error in collected.of("error"))

    def test_workflow_without_run_writes_nothing(self, tmp_path, collected):
        (tmp_path / "work" / "workflows").mkdir(parents=True)
        args = argparse.Namespace(work_path=str(tmp_path / "work" / "workflows"), result_path=str(tmp_path / "results"), output="results_workflow.yml", config="odatix.yml")
        assert results_command._export_workflow(args) is True
        assert not (tmp_path / "results").exists() and collected.of("error") == []

    def test_a_named_derived_file_that_does_not_exist_is_an_error(self, tmp_path, collected):
        args = argparse.Namespace(config=str(tmp_path / "odatix.yml"), result_path=str(tmp_path), derived=str(tmp_path / "missing.yml"))
        assert exp_derived.main(args) is False
        assert any("missing.yml" in error for error in collected.of("error"))


######################################
# XR-07: the API exports and derives
######################################

DERIVED = (
    "derived_metrics:\n"
    "  LUT_per_MHz:\n"
    "    type: operation\n"
    "    op: \"LUT_count / meta.frequency\"\n"
    "    unit: LUT/MHz\n"
)


@pytest.fixture
def results_workspace(example_workspace):
    (example_workspace / "odatix_userconfig" / "derived_metrics.yml").write_text(DERIVED, encoding="utf-8")
    results = example_workspace / "results"
    results.mkdir(exist_ok=True)
    path = str(results / "results_vivado.yml")
    results_schema.dump_results_file(path, {"LUT_count": "LUT"}, [synthesis_record("08bits", {"LUT_count": 200})])
    results_cache.invalidate()
    return example_workspace


class TestExportApi:
    def test_derived_metrics_are_applied(self, results_workspace, tmp_path_factory, monkeypatch):
        from odatix.run import export_results
        from odatix.workspace import Workspace

        # From another directory: the workspace says where everything is.
        monkeypatch.chdir(str(tmp_path_factory.mktemp("elsewhere")))
        report = export_results(Workspace.open(str(results_workspace)), "derived", quiet=True)
        assert report and report.errors() == []
        assert report.summary() == "Derived metrics updated in 1 results file"
        data = results_schema.load_results_file(str(results_workspace / "results" / "results_vivado.yml"))
        assert data.records[0]["metrics"]["LUT_per_MHz"] == 2

    def test_a_reported_error_makes_the_report_false(self, results_workspace):
        from odatix.run import export_results
        from odatix.workspace import Workspace

        (results_workspace / "odatix_userconfig" / "derived_metrics.yml").write_text(
            'derived_metrics:\n  Bad: {type: operation, op: "a / / b"}\n'
        )
        report = export_results(Workspace.open(str(results_workspace)), "derived", quiet=True)
        assert not report and len(report.errors()) == 1

    def test_an_unknown_type_is_refused(self, results_workspace):
        from odatix.run import export_results
        from odatix.workspace import Workspace

        with pytest.raises(ValueError):
            export_results(Workspace.open(str(results_workspace)), "everything")


######################################
# GS-18: odatix clean says what it did, with short paths
######################################

class TestCleanCommand:
    def test_nothing_to_clean_is_said(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(str(tmp_path))
        settings = tmp_path / "clean.yml"
        settings.write_text("remove_list:\n  - .Xil\n  - '*.jou'\n", encoding="utf-8")
        assert cln.clean(str(settings)) is True
        out = capsys.readouterr().out
        assert "Nothing to clean" in out and "2 patterns" in out

    def test_removed_paths_are_relative(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(str(tmp_path))
        (tmp_path / ".Xil").mkdir()
        settings = tmp_path / "clean.yml"
        settings.write_text("remove_list:\n  - .Xil\n", encoding="utf-8")
        cln.clean(str(settings))
        out = capsys.readouterr().out
        assert 'Removed ".Xil" (directory)' in out
        assert str(tmp_path) not in out and "Nothing to clean" not in out


######################################
# GUI pages: XR-07, XR-10, XR-12
######################################

@pytest.fixture(scope="module")
def pages():
    dash = pytest.importorskip("dash")
    dash.Dash(__name__, use_pages=True, pages_folder="")
    import odatix.gui.pages.derived_metrics as derived_page
    import odatix.gui.pages.clean as clean_page
    return derived_page, clean_page


class TestGuiPages:
    def test_a_clean_that_removed_nothing_does_not_claim_the_workspace_is_clean(self, pages):
        from odatix.workspace.clean import CleanResult

        _derived_page, clean_page = pages
        text = str(clean_page.result_view(CleanResult(), "."))
        assert "already clean" not in text and "work/" in text

    def test_untouched_definitions_are_written_as_the_file_holds_them(self, pages):
        derived_page, _clean_page = pages
        raw = {
            "LUT_count_after_synthesis": {"metric": "LUT_count", "from": "synthesis", "step": "synthesis"},
            "Ratio": {"type": "operation", "op": "a / b"},
        }
        current = derived_page.normalize_metrics(raw)
        current["New"] = derived_page.build_metric_definition(
            kind="operation", from_value=[], metric_value="", op_value="Cycles / meta.frequency", for_value="",
            apply_to_value=["synthesis"], unit_value="", pin_value="", ignore_value="", map_value="", on_value="",
            on_multiple_value="error", where_value="", source_where_value="", optional_value=False, overwrite_value=False,
        )
        current["Ratio"] = dict(current["Ratio"], op="a / c")
        written = derived_page.definitions_to_write(current, raw)
        assert written["LUT_count_after_synthesis"] is raw["LUT_count_after_synthesis"]
        assert "type" not in written["New"] and written["New"]["op"] == "Cycles / meta.frequency"
        # The file wrote "type" for this one: an edit keeps it
        assert written["Ratio"] == {"type": "operation", "op": "a / c"}

    def test_unchanged_groups_are_written_as_the_file_holds_them(self, pages):
        derived_page, _clean_page = pages
        raw = {"cpus": "Ibex/*"}
        assert derived_page.groups_to_write({"cpus": ["Ibex/*"]}, raw) is raw
        assert derived_page.groups_to_write({"cpus": ["A/*"]}, raw) == {"cpus": ["A/*"]}

    def test_the_operation_placeholder_follows_the_documentation(self, pages):
        derived_page, _clean_page = pages
        text = str(derived_page.metric_card("X", kind_value="operation"))
        assert "Cycles / meta.frequency" in text and "Cycles / Frequency'" not in text

    def test_saving_applies_the_derived_metrics(self, pages, results_workspace):
        from odatix.workspace import Workspace

        derived_page, _clean_page = pages
        feedback = derived_page.apply_feedback(Workspace.open(str(results_workspace)), saved=True)
        assert "success" in feedback.className
        assert feedback.children == "Saved. Derived metrics updated in 1 results file."

    def test_applying_lists_what_went_wrong(self, pages, results_workspace):
        from odatix.workspace import Workspace

        (results_workspace / "odatix_userconfig" / "derived_metrics.yml").write_text(
            'derived_metrics:\n  Typo: {type: operation, op: "LUT_cnt / 2"}\n'
        )
        derived_page, _clean_page = pages
        feedback = derived_page.apply_feedback(Workspace.open(str(results_workspace)))
        assert "error" in feedback.className
        assert "LUT_cnt" in str(feedback.children)
