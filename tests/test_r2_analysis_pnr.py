"""Non-regression tests of the 2nd new-user campaign, analysis and pnr (AP-*)."""
import os

import yaml

import odatix.lib.analysis as analysis
import odatix.lib.run_report as run_report
import odatix.components.export_analysis as export_analysis

ROOT = os.path.join(os.path.dirname(__file__), "..", "sources", "odatix_eda_tools")


class _Job(object):
  pass


def test_job_status_says_whether_the_tool_ran():  # AP-02
  for status, failed in ((analysis.STATUS_FAILED, False), (analysis.STATUS_PASSED, False),
                         (analysis.STATUS_UNSUPPORTED, False), (analysis.STATUS_TOOL_FAILURE, True),
                         (analysis.STATUS_INCOMPLETE, True)):
    job = _Job()
    export_analysis.settle_job_status(job, analysis.AnalysisResult("t", "a", status=status))
    assert job._failed_before_export is failed


def test_verilator_makefile_keeps_exit_code():  # AP-02
  text = open(os.path.join(ROOT, "verilator", "makefile.mk"), encoding="utf-8").read()
  assert "pipefail" in text and "SHELL := /bin/bash" in text


def test_long_detail_is_kept_with_omitted_count(tmp_path):  # AP-04
  log = tmp_path / "a.log"
  log.write_text("%Error-MODMISSING: rtl/top.sv:2:2: Cannot find file containing module: 'x'\n"
                 + "".join("   line %d\n" % i for i in range(20)))
  definition = analysis.load_definition("verilator")
  reader = analysis.LogReader(definition)
  reader.read(str(log), "a.log")
  finding = reader.results()[0]
  assert len(finding.detail) == analysis.MAX_DETAIL_LINES + 1
  assert finding.detail[-1] == "[4 more lines in the log]"


def test_finding_detail_is_monospaced():  # AP-04
  css = open(os.path.join(os.path.dirname(__file__), "..", "sources", "odatix", "gui", "assets", "explorer.css"), encoding="utf-8").read()
  block = css.split(".xpa-finding-detail {", 1)[1].split("}", 1)[0]
  assert "monospace" in block


def test_pnr_metrics_match_synthesis_names():  # AP-06
  for tool in ("innovus",):
    path = os.path.join(ROOT, tool, "metrics.yml")
    metrics = yaml.safe_load(open(path, encoding="utf-8"))["pnr_metrics"]
    assert "Cell_Area" in metrics and "Total_Power" in metrics
    assert "Total_area" not in metrics and "Total_power" not in metrics
    for spec in metrics.values():
      assert spec.get("unit", "") in ("", "um^2", "mW", "ns")


def test_plan_labels_and_steps():  # AP-07, AP-14
  assert run_report.meta(run_report.Category.RESUME)["label"] == "Resume"
  assert run_report.meta(run_report.Category.OVERWRITE)["label"] == "Overwrite"
  assert run_report.meta(run_report.Category.RESUME)["glyph"] != "▸"
  assert "settings," not in run_report.category_description(run_report.Category.ERROR)
  assert run_report.steps_text({"steps": ["synthesis", "pnr"]}) == "synthesis → pnr"
  assert run_report.steps_text({"steps": ["bitstream"]}) == "bitstream"
  assert run_report.steps_text({}) == ""


def test_read_results(tmp_path):  # AP-13
  result = analysis.AnalysisResult("verilator", "Counter", "08bits", status=analysis.STATUS_FAILED)
  export_analysis.export_analysis_results([result], str(tmp_path), quiet=True)
  import odatix.lib.results_cache as results_cache
  results_cache.flush()
  read = analysis.read_results(str(tmp_path), designs=["Counter/*"])
  assert [(r.tool, r.name, r.status) for r in read] == [("verilator", "Counter/08bits", "failed")]
  assert analysis.read_results(str(tmp_path), tools=["vivado"]) == []
  assert analysis.count_by_status(read)["failed"] == 1
