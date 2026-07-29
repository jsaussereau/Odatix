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
Per-job step tracking.

A flow can be split into ordered steps (see the "<job_type>_steps" key of
tool.yml): for Vivado, synthesis, then place & route, then bitstream. Each step
runs as its own process, so the tool has to hand its state over on disk
(write_checkpoint / read_checkpoint and their equivalents) — that part lives in
the tool's own scripts.

What lives here is the bookkeeping Odatix owns: which steps a job directory has
already completed, so that

  * asking again for something already done skips the job entirely,
  * asking for a further step resumes from the first step left to run instead of
    redoing everything (generate the bitstream only for the implementations
    worth it, or pick a job back up after a checkpoint).

The state is a small YAML file in the job's log directory:

    flow: standard
    completed:
      - name: synthesis
        timestamp: 2026-07-28_19-04-37
      - name: pnr
        timestamp: 2026-07-28_19-31-02

Only a *leading* run of completed steps counts as resumable: if the recorded
steps no longer match the flow (the tool.yml changed), the job restarts from the
first mismatch, which is the safe reading.
"""

import os

import yaml

import odatix.lib.hard_settings as hard_settings


def state_file(tmp_dir):
  """Path of the step state file of a job directory."""
  return os.path.join(str(tmp_dir), hard_settings.work_log_path, hard_settings.steps_filename)


def read_state(tmp_dir):
  """
  Load the step state of a job directory. Returns {"flow": str|None,
  "completed": [{"name", "timestamp"}]}, empty when there is none or it is
  unreadable.
  """
  path = state_file(tmp_dir)
  empty = {"flow": None, "completed": []}
  if not os.path.isfile(path):
    return empty
  try:
    with open(path, "r") as f:
      data = yaml.load(f, Loader=yaml.loader.SafeLoader)
  except Exception:
    return empty
  if not isinstance(data, dict):
    return empty

  completed = []
  for entry in data.get("completed") or []:
    if isinstance(entry, dict) and isinstance(entry.get("name"), str):
      completed.append({"name": entry["name"], "timestamp": entry.get("timestamp")})
    elif isinstance(entry, str):
      completed.append({"name": entry, "timestamp": None})
  flow = data.get("flow")
  return {"flow": flow if isinstance(flow, str) else None, "completed": completed}


def completed_step_names(tmp_dir):
  """Names of the steps a job directory has completed, in order."""
  return [entry["name"] for entry in read_state(tmp_dir)["completed"]]


def last_completed_step(tmp_dir):
  """Name of the last step a job directory completed, or None."""
  names = completed_step_names(tmp_dir)
  return names[-1] if names else None


def record_completed_step(tmp_dir, step_name, flow=None, timestamp=None):
  """
  Append a step to the state of a job directory. Re-running a step that is
  already recorded (a rerun) truncates the state after it, so the recorded list
  always matches what the directory actually holds.
  """
  from odatix.lib.utils import get_timestamp_string

  state = read_state(tmp_dir)
  completed = [entry for entry in state["completed"] if entry["name"] != step_name]
  # Everything recorded after a re-run step is stale.
  names = [entry["name"] for entry in state["completed"]]
  if step_name in names:
    completed = state["completed"][: names.index(step_name)]

  completed.append({"name": str(step_name), "timestamp": timestamp or get_timestamp_string()})

  path = state_file(tmp_dir)
  os.makedirs(os.path.dirname(path), exist_ok=True)
  with open(path, "w") as f:
    yaml.dump(
      {"flow": flow if flow is not None else state["flow"], "completed": completed},
      f,
      default_flow_style=False,
      sort_keys=False,
    )


def resume_index(tmp_dir, step_names):
  """
  Number of leading steps of `step_names` a job directory has already completed,
  i.e. the index the pipeline should start at.

  Only a leading run counts: a recorded step that does not match the flow stops
  the count, so a changed tool.yml re-runs from the first difference.
  """
  completed = completed_step_names(tmp_dir)
  index = 0
  for name in step_names:
    if index < len(completed) and completed[index] == name:
      index += 1
    else:
      break
  return index


def select_steps(steps, until=None, rerun_from=None):
  """
  Narrow an ordered step list to what a run should cover.

  Args:
      steps (list): the flow's steps ({"name", "command"} dicts).
      until (str, optional): last step to run, inclusive. Later steps are
          dropped, which is how "only implement, do not write the bitstream"
          is expressed.
      rerun_from (str, optional): earliest step allowed to be reused. Steps
          before it stay eligible for resume; this one and the following ones
          are re-run even when already recorded.

  Returns:
      tuple: (selected steps, index of rerun_from within them or 0, error
      message or None)
  """
  names = [step["name"] for step in steps]

  if until is not None and str(until).strip() != "":
    until = str(until).strip()
    if until not in names:
      return [], 0, 'no step named "' + until + '" (steps are: ' + ", ".join(names) + ")"
    steps = steps[: names.index(until) + 1]
    names = names[: names.index(until) + 1]

  rerun_index = len(steps)
  if rerun_from is not None and str(rerun_from).strip() != "":
    rerun_from = str(rerun_from).strip()
    if rerun_from not in names:
      return [], 0, 'no step named "' + rerun_from + '" to re-run from (steps are: ' + ", ".join(names) + ")"
    rerun_index = names.index(rerun_from)

  return steps, rerun_index, None


def start_index(tmp_dir, steps, rerun_index=None):
  """
  Index the pipeline of a job directory should start at: the steps already
  completed are skipped, but never past `rerun_index` (the step the user asked
  to re-run from).
  """
  index = resume_index(tmp_dir, [step["name"] for step in steps])
  if rerun_index is not None:
    index = min(index, rerun_index)
  return index
