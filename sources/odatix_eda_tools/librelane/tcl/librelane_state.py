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
Read what a LibreLane run left behind, for the tcl scripts of this tool.

LibreLane hands a design from one step to the next through a JSON state
("state_out.json" in each step directory): the paths of the views the step
produced, and every metric measured so far. tclsh has no JSON parser, so the
scripts call this instead:

  librelane_state.py collect <run_dir> <report_dir> [<state_copy>]
      Write the metrics of the last step that completed in <run_dir> to
      <report_dir>: "librelane_metrics.json" (as LibreLane names them),
      "metrics.json" (as Odatix names them, see METRICS) and "timing.rep" (the
      worst slacks, read by is_slack_met.tcl). Also copies that state to
      <state_copy>, the state the next step of the flow starts from.

  librelane_state.py view <state> <format>
      Print the path of a view of a state ("nl" for the netlist), nothing when
      the state has none.

Runs with any python 3, LibreLane's or the system's: standard library only.
"""

import os
import re
import sys
import json
import math
import shutil

# Odatix name: (LibreLane metric, scale). Power is in watts in LibreLane, in
# milliwatts in the results of the other ASIC tools of Odatix.
METRICS = {
  "Total_Cell_Area":      ("design__instance__area", 1),
  "Total_Cell_count":     ("design__instance__count", 1),
  "Die_area":             ("design__die__area", 1),
  "Core_area":            ("design__core__area", 1),
  "Core_utilization":     ("design__instance__utilization", 1),
  "Total_Power":          ("power__total", 1000),
  "Internal_Power":       ("power__internal__total", 1000),
  "Switching_Power":      ("power__switching__total", 1000),
  "Leakage_Power":        ("power__leakage__total", 1000),
  "Worst_Slack":          ("timing__setup__ws", 1),
  "Setup_TNS":            ("timing__setup__tns", 1),
  "Setup_violations":     ("timing__setup_vio__count", 1),
  "Hold_Slack":           ("timing__hold__ws", 1),
  "Hold_violations":      ("timing__hold_vio__count", 1),
  "Clock_skew":           ("clock__skew__worst_setup", 1),
  "Wire_length":          ("route__wirelength", 1),
  "Vias":                 ("route__vias", 1),
  "DRC_errors":           ("route__drc_errors", 1),
  "Antenna_violations":   ("antenna__violating__nets", 1),
  "Max_slew_violations":  ("design__max_slew_violation__count", 1),
  "Max_cap_violations":   ("design__max_cap_violation__count", 1),
  "Max_fanout_violations":("design__max_fanout_violation__count", 1),
  "Magic_DRC_errors":     ("magic__drc_error__count", 1),
  "KLayout_DRC_errors":   ("klayout__drc_error__count", 1),
  "LVS_errors":           ("design__lvs_error__count", 1),
  "Lint_errors":          ("design__lint_error__count", 1),
  "Lint_warnings":        ("design__lint_warning__count", 1),
  "Inferred_latches":     ("design__inferred_latch__count", 1),
}

# Cells the flow adds to fill the rows rather than to implement the design: from
# placement on, they make up a good part of the instance area. Cell_Area and
# Cell_count leave them out, so that they compare from one step to the next,
# and with the area other synthesis tools report.
PHYSICAL_ONLY_CLASSES = ("fill_cell", "tap_cell", "endcap_cell", "welltap_cell", "decap_cell", "antenna_cell")

STEP_DIR = re.compile(r"^([0-9]+)-")


def step_dirs(run_dir):
  """The step directories of a run, in the order they ran."""
  dirs = []
  if not os.path.isdir(run_dir):
    return dirs
  for name in os.listdir(run_dir):
    match = STEP_DIR.match(name)
    path = os.path.join(run_dir, name)
    if match and os.path.isdir(path):
      dirs.append((int(match.group(1)), path))
  return [path for _, path in sorted(dirs)]


def last_state(run_dir):
  """The state_out.json of the last step that completed in a run, or None."""
  for path in reversed(step_dirs(run_dir)):
    state = os.path.join(path, "state_out.json")
    if os.path.isfile(state):
      return state
  return None


def finite(value):
  """A metric as a number, None when it is not one (or not a finite one)."""
  if isinstance(value, bool) or not isinstance(value, (int, float)):
    try:
      value = float(value)
    except (TypeError, ValueError):
      return None
  if isinstance(value, float) and (math.isinf(value) or math.isnan(value)):
    return None
  return value


def write_json(path, data):
  with open(path, "w") as f:
    json.dump(data, f, indent=2, sort_keys=True)
    f.write("\n")


def collect(run_dir, report_dir, state_copy=None):
  state_path = last_state(run_dir)
  if state_path is None:
    sys.stderr.write("error: no step of \"" + run_dir + "\" completed\n")
    return 1

  with open(state_path) as f:
    state = json.load(f)
  raw = state.get("metrics", {}) or {}

  os.makedirs(report_dir, exist_ok=True)
  write_json(os.path.join(report_dir, "librelane_metrics.json"), raw)

  metrics = {}
  for name, (key, scale) in METRICS.items():
    value = finite(raw.get(key))
    if value is not None:
      metrics[name] = value * scale
  # The sum of the classes of cells that implement the design, rather than the
  # total minus the others: the total and the classes are not always measured
  # by the same step (after the floorplan, they do not add up), while the
  # classes always are, together. A state without classes (after synthesis)
  # has nothing but the design's own cells: its total is the answer.
  for name, total_key, class_prefix in (
    ("Cell_Area", "design__instance__area", "design__instance__area__class:"),
    ("Cell_count", "design__instance__count", "design__instance__count__class:"),
  ):
    classes = {
      key[len(class_prefix):]: finite(value)
      for key, value in raw.items()
      if key.startswith(class_prefix) and finite(value) is not None
    }
    if classes:
      metrics[name] = sum(value for cls, value in classes.items() if cls not in PHYSICAL_ONLY_CLASSES)
    elif finite(raw.get(total_key)) is not None:
      metrics[name] = finite(raw.get(total_key))
  write_json(os.path.join(report_dir, "metrics.json"), metrics)

  # Read by is_slack_met.tcl. "inf" when nothing is constrained: a design
  # without a single timed path has no slack to meet, and the fmax search
  # then stops instead of raising the frequency forever.
  with open(os.path.join(report_dir, "timing.rep"), "w") as f:
    f.write("state: " + state_path + "\n")
    for label, key in (("setup_ws", "timing__setup__ws"), ("setup_tns", "timing__setup__tns"), ("hold_ws", "timing__hold__ws")):
      value = raw.get(key)
      if value is None:
        continue
      number = finite(value)
      f.write(label + ": " + ("inf" if number is None else repr(number)) + "\n")

  if state_copy:
    os.makedirs(os.path.dirname(os.path.abspath(state_copy)), exist_ok=True)
    shutil.copyfile(state_path, state_copy)

  print(state_path)
  return 0


def view(state_path, design_format):
  if not os.path.isfile(state_path):
    return 1
  with open(state_path) as f:
    state = json.load(f)
  value = state.get(design_format)
  # A view a step produced for several corners is a dict of paths
  if isinstance(value, dict):
    value = next(iter(value.values()), None)
  if isinstance(value, list):
    value = value[0] if value else None
  if value:
    print(value)
  return 0


def main(argv):
  if len(argv) >= 3 and argv[0] == "collect":
    return collect(argv[1], argv[2], argv[3] if len(argv) > 3 else None)
  if len(argv) == 3 and argv[0] == "view":
    return view(argv[1], argv[2])
  sys.stderr.write(__doc__)
  return 2


if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
