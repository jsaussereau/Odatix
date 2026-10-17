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
The LibreLane tool (sources/odatix_eda_tools/librelane), without LibreLane.

Its scripts run in tclsh and read what LibreLane leaves in its run directory
through librelane_state.py: these tests feed them run directories and settings
the way LibreLane and Odatix write them. Running LibreLane itself is left to the
end-to-end runs (it needs its nix environment and a PDK).
"""

import json
import os
import re
import shutil
import subprocess
import sys

import pytest
import yaml

from odatix.lib.settings import OdatixSettings
from odatix.components.run_analysis import analysis_install_path

TOOL_DIR = os.path.join(OdatixSettings.odatix_eda_tools_path, "librelane")
TCL_DIR = os.path.join(TOOL_DIR, "tcl")
STATE_SCRIPT = os.path.join(TCL_DIR, "librelane_state.py")

needs_tclsh = pytest.mark.skipif(shutil.which("tclsh") is None, reason="tclsh not installed")


def write_step(run_dir, index, name, metrics, views=None):
  step_dir = run_dir / "{:02d}-{}".format(index, name)
  step_dir.mkdir(parents=True)
  state = dict(views or {})
  state["metrics"] = metrics
  (step_dir / "state_out.json").write_text(json.dumps(state))
  return step_dir


def run_state_script(*args):
  return subprocess.run(
    [sys.executable, STATE_SCRIPT] + [str(arg) for arg in args],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
  )


class TestCollect:

  def test_reads_the_last_step_that_completed(self, tmp_path):
    run_dir = tmp_path / "runs" / "custom"
    write_step(run_dir, 6, "yosys-synthesis", {"design__instance__area": 100.0})
    last = write_step(run_dir, 12, "openroad-staprepnr", {
      "design__instance__area": 544.272,
      "design__instance__count": 51,
      "power__total": 0.000155,
      "timing__setup__ws": -0.25,
      "timing__hold__ws": 0.11,
    })
    # A step killed before it wrote its state does not count
    (run_dir / "13-openroad-floorplan").mkdir()

    report = tmp_path / "report"
    state_copy = tmp_path / "state" / "synthesis.json"
    result = run_state_script("collect", run_dir, report, state_copy)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(last / "state_out.json")

    metrics = json.loads((report / "metrics.json").read_text())
    assert metrics["Cell_Area"] == 544.272
    assert metrics["Cell_count"] == 51
    # Power in mW, as the other ASIC tools of Odatix report it
    assert metrics["Total_Power"] == pytest.approx(0.155)
    assert metrics["Worst_Slack"] == -0.25
    assert "Die_area" not in metrics

    raw = json.loads((report / "librelane_metrics.json").read_text())
    assert raw["design__instance__count"] == 51
    assert json.loads(state_copy.read_text())["metrics"]["timing__setup__ws"] == -0.25
    assert "setup_ws: -0.25" in (report / "timing.rep").read_text()

  def test_cell_area_leaves_out_the_cells_filling_the_rows(self, tmp_path):
    run_dir = tmp_path / "run"
    # As LibreLane measures it after routing a 8-bit counter on sky130_fd_sc_hd
    write_step(run_dir, 55, "openroad-stapostpnr", {
      "design__instance__area": 1066.02,
      "design__instance__area__class:clock_buffer": 75.072,
      "design__instance__area__class:fill_cell": 307.795,
      "design__instance__area__class:inverter": 11.2608,
      "design__instance__area__class:multi_input_combinational_cell": 362.848,
      "design__instance__area__class:sequential_cell": 170.163,
      "design__instance__area__class:tap_cell": 17.5168,
      "design__instance__area__class:timing_repair_buffer": 121.366,
      "design__instance__count": 172,
      "design__instance__count__class:clock_buffer": 3,
      "design__instance__count__class:fill_cell": 91,
      "design__instance__count__class:inverter": 3,
      "design__instance__count__class:multi_input_combinational_cell": 40,
      "design__instance__count__class:sequential_cell": 8,
      "design__instance__count__class:tap_cell": 14,
      "design__instance__count__class:timing_repair_buffer": 13,
    })
    assert run_state_script("collect", run_dir, tmp_path / "report").returncode == 0
    metrics = json.loads((tmp_path / "report" / "metrics.json").read_text())
    assert metrics["Cell_Area"] == pytest.approx(740.7098)
    assert metrics["Cell_count"] == 67
    assert metrics["Total_Cell_Area"] == 1066.02
    assert metrics["Total_Cell_count"] == 172

  def test_steps_are_ordered_by_number_not_by_name(self, tmp_path):
    run_dir = tmp_path / "run"
    write_step(run_dir, 9, "late", {"timing__setup__ws": 1.0})
    write_step(run_dir, 10, "later", {"timing__setup__ws": 2.0})
    result = run_state_script("collect", run_dir, tmp_path / "report")
    assert result.returncode == 0
    assert "10-later" in result.stdout

  def test_an_unconstrained_design_has_an_infinite_slack(self, tmp_path):
    run_dir = tmp_path / "run"
    # json.dump writes an infinite float as "Infinity", as LibreLane does
    write_step(run_dir, 1, "sta", {"timing__setup__ws": float("inf")})
    result = run_state_script("collect", run_dir, tmp_path / "report")
    assert result.returncode == 0
    assert "setup_ws: inf" in (tmp_path / "report" / "timing.rep").read_text()
    # No value is better than an infinite one in the results
    assert "Worst_Slack" not in json.loads((tmp_path / "report" / "metrics.json").read_text())

  def test_a_run_without_any_completed_step_is_an_error(self, tmp_path):
    result = run_state_script("collect", tmp_path / "missing", tmp_path / "report")
    assert result.returncode == 1

  def test_view_prints_the_path_of_a_view(self, tmp_path):
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"nl": "/runs/x/counter.nl.v", "spef": {"nom_*": "/runs/x/nom.spef"}, "def": None}))
    assert run_state_script("view", state, "nl").stdout.strip() == "/runs/x/counter.nl.v"
    assert run_state_script("view", state, "spef").stdout.strip() == "/runs/x/nom.spef"
    assert run_state_script("view", state, "def").stdout.strip() == ""


def read_tcl_step_ranges():
  with open(os.path.join(TCL_DIR, "librelane_common.tcl")) as f:
    content = f.read()
  block = re.search(r"set librelane_step_ranges \[dict create(.*?)\n\]", content, re.S).group(1)
  ranges = re.findall(r"^\s*(\w+)\s+\[list\s+\"([^\"]*)\"\s+\"([^\"]*)\"\]", block, re.M)
  order = re.search(r"set librelane_step_order \[list ([^\]]*)\]", content).group(1).split()
  return ranges, order


class TestSteps:

  def test_every_custom_freq_step_has_a_range_in_the_classic_flow(self):
    with open(os.path.join(TOOL_DIR, "tool.yml")) as f:
      tool = yaml.safe_load(f)
    declared = [step["name"] for step in tool["unix"]["custom_freq_synthesis_steps"]]
    ranges, order = read_tcl_step_ranges()
    assert [name for name, _, _ in ranges] == declared
    assert order == declared

  def test_the_ranges_cover_the_flow_end_to_end(self):
    ranges, _ = read_tcl_step_ranges()
    # The first step starts at the start of the flow, the last one runs to its end
    assert ranges[0][1] == ""
    assert ranges[-1][2] == ""
    for name, start, end in ranges[1:-1]:
      assert start and end, name


@needs_tclsh
class TestTclScripts:

  def run_tcl(self, tmp_path, script):
    path = tmp_path / "test.tcl"
    path.write_text(script)
    result = subprocess.run(
      ["tclsh", str(path)], cwd=str(tmp_path),
      stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True,
    )
    assert result.returncode == 0, result.stdout
    return result.stdout

  def test_update_freq_writes_the_clock_period(self, tmp_path):
    output = self.run_tcl(tmp_path, (
      "source {%s}\n" % os.path.join(TCL_DIR, "update_freq.tcl")
      + "update_freq 250 period.json\n"
      + "update_freq 0 analysis.json\n"
      + "puts [read [open period.json]][read [open analysis.json]]\n"
    ))
    assert '{"CLOCK_PERIOD": 4.0}' in output
    # An analysis has no frequency, LibreLane needs a period all the same
    assert '{"CLOCK_PERIOD": 10.0}' in output

  @pytest.mark.parametrize("content, met, inf", [
    ("setup_ws: 0.0013\n", 1, 0),
    ("setup_ws: -0.2\nhold_ws: 0.1\n", 0, 0),
    ("setup_ws: inf\n", 0, 1),
    ("", 0, 0),
  ])
  def test_is_slack_met_reads_the_worst_setup_slack(self, tmp_path, content, met, inf):
    (tmp_path / "timing.rep").write_text(content)
    output = self.run_tcl(tmp_path, (
      "source {%s}\n" % os.path.join(TCL_DIR, "is_slack_met.tcl")
      + "puts \"[is_slack_met . timing.rep] [is_slack_inf . timing.rep]\"\n"
    ))
    assert output.strip() == "{} {}".format(met, inf)

  def test_flow_parameters_in_capitals_become_overrides(self, tmp_path):
    scripts = tmp_path / "scripts"
    shutil.copytree(TCL_DIR, str(scripts))
    shutil.copy(os.path.join(OdatixSettings.odatix_eda_tools_path, "_common", "settings.tcl"), str(scripts))
    (tmp_path / "period.json").write_text('{"CLOCK_PERIOD": 5.0}')
    output = self.run_tcl(tmp_path, (
      "source scripts/librelane_common.tcl\n"
      "set constraints_file period.json\n"
      "set ::odatix_flow_parameters [dict create flow {} extra_args [list] "
      "SYNTH_STRATEGY {DELAY 1} FP_CORE_UTIL {} RUN_POST_GRT_RESIZER_TIMING 1]\n"
      "puts [odatix_librelane_overrides]\n"
    ))
    assert output.strip() == "-c CLOCK_PERIOD=5.0 -c {SYNTH_STRATEGY=DELAY 1} -c RUN_POST_GRT_RESIZER_TIMING=1"


class TestAnalysisInstallPath:

  def test_reads_the_install_path_of_the_target_file(self, tmp_path):
    install = tmp_path / "librelane"
    install.mkdir()
    (tmp_path / "target_librelane.yml").write_text("tool_install_path: " + str(install) + "\n")
    assert analysis_install_path("librelane", str(tmp_path)) == os.path.realpath(str(install))

  def test_defaults_to_the_path(self, tmp_path, monkeypatch):
    monkeypatch.setattr(OdatixSettings, "DEFAULT_TARGET_FALLBACK_PATH", str(tmp_path / "nowhere"), raising=False)
    assert analysis_install_path("librelane", str(tmp_path)) == "/"
    (tmp_path / "target_librelane.yml").write_text("tool_install_path: " + str(tmp_path / "missing") + "\n")
    assert analysis_install_path("librelane", str(tmp_path)) == "/"
