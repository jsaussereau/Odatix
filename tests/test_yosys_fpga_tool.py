# ********************************************************************** #
#                                Odatix                                  #
# ********************************************************************** #
#
# Copyright (C) 2022 Jonathan Saussereau
#
# This file is part of Odatix.
# Odatix is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Odatix is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Odatix. If not, see <https://www.gnu.org/licenses/>.
#

"""
The Yosys + nextpnr tool (sources/odatix_eda_tools/yosys_fpga).

Its flow is one Python script, tcl/fpga_flow.py: these tests feed it the
reports Yosys and nextpnr write, and run it for real on a small design when
yosys and nextpnr-ecp5 are installed (the OSS CAD Suite).
"""

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap

import pytest
import yaml

import odatix.lib.eda_tools as eda_tools
from odatix.lib.settings import OdatixSettings

TOOL_DIR = os.path.join(OdatixSettings.odatix_eda_tools_path, "yosys_fpga")
SCRIPT = os.path.join(TOOL_DIR, "tcl", "fpga_flow.py")

needs_oss_cad_suite = pytest.mark.skipif(
  shutil.which("yosys") is None or shutil.which("nextpnr-ecp5") is None,
  reason="yosys and nextpnr-ecp5 not installed",
)


@pytest.fixture
def flow():
  spec = importlib.util.spec_from_file_location("fpga_flow", SCRIPT)
  module = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(module)
  return module


@pytest.fixture
def job_dir(tmp_path, monkeypatch):
  """A job directory, the way Odatix prepares it, as the working directory."""
  for directory in ("log", "report", "result", "scripts", "rtl"):
    (tmp_path / directory).mkdir()
  settings = {
    "top_level_module": "counter",
    "clock_signal": "clock",
    "target": "ecp5-25k-CABGA381-6",
    "fmax_lower_bound": "50",
    "fmax_upper_bound": "400",
    "target_frequency": 0,
  }
  (tmp_path / "settings.yml").write_text(yaml.safe_dump(settings), encoding="utf-8")
  monkeypatch.chdir(tmp_path)
  return tmp_path


def nextpnr_report(achieved, used=100):
  return {
    "fmax": {"$glbnet$clock$TRELLIS_IO_IN": {"achieved": achieved, "constraint": 50}},
    "utilization": {
      "TRELLIS_COMB": {"available": 24288, "used": used},
      "TRELLIS_FF": {"available": 24288, "used": 40},
      "DP16KD": {"available": 56, "used": 0},
      "MULT18X18D": {"available": 28, "used": 0},
      "TRELLIS_IO": {"available": 197, "used": 20},
    },
  }


class TestTargets:

  def test_an_ecp5_target_names_its_device_package_and_speed(self, flow):
    assert flow.parse_target("ecp5-25k-CABGA381-6") == ("ecp5", "25k", "CABGA381", "6")

  def test_an_ecp5_target_without_speed_takes_the_default(self, flow):
    assert flow.parse_target("ecp5-85k-CABGA756") == ("ecp5", "85k", "CABGA756", "6")

  def test_an_ice40_package_is_given_in_lower_case(self, flow):
    assert flow.parse_target("ice40-hx8k-CT256") == ("ice40", "hx8k", "ct256", None)

  @pytest.mark.parametrize("target", ["xc7a100t-csg324-1", "ecp5-25k", "generic"])
  def test_another_target_is_refused(self, flow, target):
    with pytest.raises(flow.FlowError):
      flow.parse_target(target)


class TestReports:

  def test_the_frequency_reached_is_that_of_the_slowest_clock(self, flow):
    report = {"fmax": {"a": {"achieved": 120.0}, "b": {"achieved": 90.5}}}
    assert flow.reached(report) == 90.5

  def test_a_design_without_clock_reaches_nothing(self, flow):
    assert flow.reached({"fmax": {}}) is None
    assert flow.reached(None) is None

  def test_the_metrics_are_named_as_for_the_other_fpga_tools(self, flow, job_dir):
    metrics = flow.write_metrics({}, "ecp5", nextpnr_report(200.0, used=2429), 100)
    assert metrics["LUT_count"] == 2429
    assert metrics["LUT_percent"] == pytest.approx(10.0, abs=0.01)
    assert metrics["Reg_count"] == 40
    assert metrics["IO_count"] == 20
    assert metrics["Achieved_frequency"] == 200.0
    # 10 ns asked, a 5 ns critical path
    assert metrics["Worst_Slack"] == pytest.approx(5.0)
    with open("report/metrics.json", encoding="utf-8") as f:
      assert json.load(f) == metrics

  def test_the_metrics_file_declares_what_the_script_writes(self, flow, job_dir):
    written = flow.write_metrics({}, "ecp5", nextpnr_report(200.0), 100)
    with open(os.path.join(TOOL_DIR, "metrics.yml"), encoding="utf-8") as f:
      declared = yaml.safe_load(f)["metrics"]
    json_keys = set(m["settings"]["key"] for m in declared.values() if m["type"] == "json")
    assert set(written) <= json_keys


class TestFmax:

  def run_fmax(self, flow, monkeypatch, reached_at):
    """Run an fmax search where routing at f reaches reached_at(f)."""
    asked = []

    def place_and_route(target, frequency, seed, options, tag):
      asked.append(frequency)
      achieved = reached_at(frequency)
      if achieved is None:
        return None
      report = nextpnr_report(achieved)
      with open(os.path.join("report", "nextpnr_" + tag + ".json"), "w") as f:
        json.dump(report, f)
      open(os.path.join("log", "nextpnr_" + tag + ".log"), "w").close()
      return report

    monkeypatch.setattr(flow, "synthesize", lambda *args: None)
    monkeypatch.setattr(flow, "place_and_route", place_and_route)
    args = type("Args", (), {"passes": 3, "seed": "1", "synth_options": [], "nextpnr_options": []})
    flow.fmax(flow.read_settings(), flow.parse_target("ecp5-25k-CABGA381-6"), args)
    with open("log/frequency_search.log", encoding="utf-8") as f:
      return asked, f.read()

  def test_each_pass_asks_for_what_the_previous_one_reached(self, flow, job_dir, monkeypatch):
    asked, log = self.run_fmax(flow, monkeypatch, lambda f: {50: 180.4, 180.4: 190.7, 190.7: 185.0}[f])
    assert asked == [50, 180.4, 190.7]
    assert "Highest frequency with timing constraints being met: 190 MHz" in log
    with open("log/status.log", encoding="utf-8") as f:
      assert "Done: 100%" in f.read()

  def test_a_design_faster_than_the_upper_bound_has_no_fmax(self, flow, job_dir, monkeypatch):
    # As with the binary search of the other tools: the upper bound is not
    # recorded as the Fmax of a design that is faster
    with pytest.raises(flow.FlowError, match="raising the upper bound"):
      self.run_fmax(flow, monkeypatch, lambda f: 500.0)
    with open("log/frequency_search.log", encoding="utf-8") as f:
      assert "No timing violated! Try raising the upper bound (400 MHz)" in f.read()
    assert not os.path.exists("report/frequency.rep")

  def test_a_failed_pass_keeps_the_best_one_before(self, flow, job_dir, monkeypatch):
    asked, log = self.run_fmax(flow, monkeypatch, lambda f: 150.0 if f == 50 else None)
    assert "FAILED" in log
    assert "met: 150 MHz" in log

  def test_a_search_reaching_nothing_fails(self, flow, job_dir, monkeypatch):
    with pytest.raises(flow.FlowError):
      self.run_fmax(flow, monkeypatch, lambda f: None)


class TestDeclaration:

  def test_the_tool_declares_its_flows(self, tmp_path, monkeypatch):
    monkeypatch.setattr(OdatixSettings, "user_tools_path", str(tmp_path))
    monkeypatch.setattr(eda_tools, "platform_key", lambda *args, **kwargs: "unix")
    assert eda_tools.get_default_flow("yosys_fpga") == "standard"
    assert eda_tools.get_flow_parameters("yosys_fpga", "abc9")["synth_options"] == ["-abc9"]
    assert eda_tools.get_flow_parameters("yosys_fpga", "timing")["fmax_passes"] == 3

  def test_every_target_of_the_target_file_is_one_the_script_knows(self, flow):
    for package in ("odatix_init", "odatix_examples"):
      path = os.path.join(os.path.dirname(OdatixSettings.odatix_eda_tools_path), package,
                          "odatix_userconfig", "targets", "target_yosys_fpga.yml")
      with open(path, encoding="utf-8") as f:
        text = f.read()
      # The targets, those commented out included
      block = text.split("\ntargets:\n", 1)[1]
      targets = re.findall(r"^\s*#?\s*-\s+(\S+)", block, re.MULTILINE)
      assert targets
      for target in targets:
        flow.parse_target(target)


@needs_oss_cad_suite
def test_a_counter_is_synthesized_placed_and_routed(job_dir):
  (job_dir / "rtl" / "counter.v").write_text(textwrap.dedent("""\
    module counter (input clock, input reset, output reg [7:0] count);
      always @(posedge clock)
        if (reset) count <= 0; else count <= count + 1;
    endmodule
    """), encoding="utf-8")
  completed = subprocess.run([sys.executable, SCRIPT, "fmax", "--passes", "1"],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
  assert completed.returncode == 0, completed.stdout[-3000:]
  with open("log/frequency_search.log", encoding="utf-8") as f:
    assert "Highest frequency with timing constraints being met" in f.read()
  with open("report/metrics.json", encoding="utf-8") as f:
    metrics = json.load(f)
  assert metrics["Reg_count"] >= 8
  assert metrics["LUT_count"] > 0
