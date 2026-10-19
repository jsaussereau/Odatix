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

import sys
import os
import re

import odatix.lib.constraint_files as constraint_files
import odatix.lib.wsl as wsl

# The constraint file of a job when its target file names none.
DEFAULT_CONSTRAINT_FILE = "constraints.sdc"


def _normalize_path(path, tool=None, resolve=True):
  """
  Normalise a path for Windows/Unix compatibility inside a tcl script: "/"
  separators (tcl reads a backslash as an escape), and the path as WSL sees it
  for a tool that runs in WSL (see odatix.lib.wsl).
  """
  if resolve:
    path = os.path.realpath(path)
  if sys.platform == "win32":
    if tool is not None and wsl.runs_in_wsl(tool):
      return wsl.linux_path(path)
    path = path.replace("\\", "/")
  return path


def _apply_replacements(config_file, replacements):
  """Rewrite the "set <name> <value>" lines of a tcl settings file."""
  with open(config_file, 'r', encoding='utf-8') as f:
    cf_content = f.read()

  for pattern, replacement in replacements.items():
    cf_content = re.sub(pattern, replacement, cf_content, flags=re.MULTILINE)

  # "\n" line endings on every system: a tool run in WSL reads them as written
  with open(config_file, 'w', encoding='utf-8', newline='\n') as f:
    f.write(cf_content)


def tcl_word(value):
  """
  A value as one tcl word: a boolean is 1 or 0, a list a tcl list of its items,
  anything else its text, braced so that nothing in it is substituted.
  """
  if isinstance(value, bool):
    return "1" if value else "0"
  if value is None:
    return "{}"
  if isinstance(value, (list, tuple)):
    return "[list " + " ".join(tcl_word(item) for item in value) + "]" if value else "[list]"
  text = str(value)
  depth = 0
  for char in text:
    depth += 1 if char == "{" else -1 if char == "}" else 0
    if depth < 0:
      break
  if depth == 0 and not text.endswith("\\"):
    return "{" + text + "}"
  # Braces that do not pair up cannot be braced: escape every special char.
  return "".join("\\" + char if char in '{}[]$"\\; ' else char for char in text)


def tcl_flow_parameters(parameters):
  """The parameters of a flow as a tcl dict literal (see odatix_flow_param)."""
  if not parameters:
    return "[dict create]"
  return "[dict create " + " ".join(
    tcl_word(str(name)) + " " + tcl_word(value) for name, value in parameters.items()
  ) + "]"


def edit_config_file(arch, config_file, flow_parameters=None, tool=None):
  """
  Replace settings in tcl config file.

  `flow_parameters` are the parameters of the flow the job runs with (see
  "parameters" in tool.yml), written as the dict odatix_flow_param reads.
  `tool` is the tool the job runs with, whose paths may be those of WSL.
  """

  tmp_path = _normalize_path(arch.tmp_dir, tool)
  constraints_file = "$tmp_path" + "/" + arch.constraint_filename

  def safe_replace(value):
    if value is None:
      return ""
    return value

  def tcl_constraint_list(scope):
    """
    The constraint files a stage reads, as a tcl list literal.

    The paths are relative to the work directory and written through $tmp_path,
    which settings.tcl sets before these lines: a job directory stays valid
    wherever it is moved to, exactly like the other paths of that file.
    """
    destinations = constraint_files.for_scope(getattr(arch, "constraint_files", []), scope)
    if not destinations:
      return "[list]"
    quoted = ['"$tmp_path/' + destination + '"' for destination in destinations]
    return "[list " + " ".join(quoted) + "]"

  # Replace rules definition
  replacements = {
    r"(set top_level_module\s+).*":   lambda m: f"{m.group(1)}{safe_replace(arch.top_level_module)}",
    r"(set top_level_file\s+).*":     lambda m: f"{m.group(1)}{safe_replace(arch.top_level_filename)}",
    r"(set clock_signal\s+).*":       lambda m: f"{m.group(1)}{safe_replace(arch.clock_signal)}",
    r"(set reset_signal\s+).*":       lambda m: f"{m.group(1)}{safe_replace(arch.reset_signal)}",
    r"(set local_rtl_path\s+).*":     lambda m: f"{m.group(1)}{safe_replace(arch.local_rtl_path)}",
    r"(set tmp_path\s+).*":           lambda m: f"{m.group(1)}{safe_replace(tmp_path)}",
    r"(set source_rtl_path\s+).*":    lambda m: f"{m.group(1)}{safe_replace(arch.rtl_path)}",
    r"(set source_arch_path\s+).*":   lambda m: f"{m.group(1)}{safe_replace(arch.arch_path and _normalize_path(arch.arch_path, tool, resolve=False))}",
    r"(set constraints_file\s+).*":   lambda m: f"{m.group(1)}{safe_replace(constraints_file)}",
    r"(set user_constraints_synthesis\s+).*": lambda m: f"{m.group(1)}{tcl_constraint_list('synthesis')}",
    r"(set user_constraints_pnr\s+).*":       lambda m: f"{m.group(1)}{tcl_constraint_list('pnr')}",
    r"(set target_frequency\s+).*":   lambda m: f"{m.group(1)}{arch.target_frequency}",
    r"(set fmax_lower_bound\s+).*":   lambda m: f"{m.group(1)}{arch.fmax_lower_bound}",
    r"(set fmax_upper_bound\s+).*":   lambda m: f"{m.group(1)}{arch.fmax_upper_bound}",
    r"(set lib_name\s+).*":           lambda m: f"{m.group(1)}{safe_replace(arch.lib_name)}",
    r"(set continue_on_error\s+).*":  lambda m: f"{m.group(1)}" + ("1" if arch.continue_on_error else "0"),
    r"(set single_thread\s+).*":      lambda m: f"{m.group(1)}" + ("1" if arch.force_single_thread else "0"),
    r"(set ::odatix_flow_parameters\s+).*": lambda m: f"{m.group(1)}{tcl_flow_parameters(flow_parameters)}",
  }

  _apply_replacements(config_file, replacements)


def edit_pnr_config_file(arch, source, config_file, tool=None):
  """
  Add to a tcl config file what a place & route job needs on top of what
  edit_config_file already wrote: where the synthesis it continues ran, and the
  handoff files it left there.

  The constraints are re-pointed at the source's sdc: a place & route job writes
  no constraint file of its own, so the one edit_config_file named does not
  exist.
  """
  def quoted(value):
    # Always quoted: a flow name is empty for a tool's default flow, and
    # "set source_flow" with nothing after it is a variable *read* in tcl, not an
    # assignment to the empty string. Quoting also survives a path with spaces.
    if value is None:
      value = ""
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"') + '"'

  def path(value):
    return _normalize_path(value, tool)

  replacements = {
    r"(set source_work_path\s+).*":  lambda m: f"{m.group(1)}{quoted(path(source.job_dir))}",
    r"(set source_tool\s+).*":       lambda m: f"{m.group(1)}{quoted(source.tool)}",
    r"(set source_flow\s+).*":       lambda m: f"{m.group(1)}{quoted(source.flow)}",
    r"(set source_type\s+).*":       lambda m: f"{m.group(1)}{quoted(source.job_type)}",
    r"(set source_netlist\s+).*":    lambda m: f"{m.group(1)}{quoted(path(source.netlist))}",
    r"(set source_sdc\s+).*":        lambda m: f"{m.group(1)}{quoted(path(source.sdc))}",
    r"(set source_sdf\s+).*":        lambda m: f"{m.group(1)}{quoted(path(source.sdf))}",
    r"(set constraints_file\s+).*":  lambda m: f"{m.group(1)}{quoted(path(source.sdc))}",
  }

  _apply_replacements(config_file, replacements)


def clock_constraint(frequency, clock_signal):
  """
  A clock constraint in SDC, the format most timing tools read: one clock on
  the clock port, at the given frequency (MHz).
  """
  period = 1000.0 / float(frequency)
  return "create_clock -period " + ("%g" % period) + " [get_ports " + str(clock_signal or "clk") + "]\n"


def write_frequency_files(arch):
  """
  Write in a custom frequency synthesis job directory what says which frequency
  it targets: "frequency.txt" ("<f> MHz") and the constraint file the target
  file names, holding a clock constraint in SDC.

  Written before the job runs, so a tool that does not source
  _common/init_script.tcl (a Python script, a Makefile) finds them too. A tool
  that does source it rewrites the constraint file in its own format (see the
  update_freq.tcl of each tool), which is why this one is only a default.

  An fmax search (no target frequency) gets neither: its frequency changes at
  each iteration, and the tool writes it.
  """
  frequency = getattr(arch, "target_frequency", 0)
  try:
    frequency = float(frequency)
  except (TypeError, ValueError):
    return
  if frequency <= 0:
    return
  shown = int(frequency) if frequency == int(frequency) else frequency
  # Never over what is already there: a job resuming after a completed step
  # keeps the files its first run wrote, in its tool's own format.
  frequency_file = os.path.join(arch.tmp_dir, "frequency.txt")
  if not os.path.exists(frequency_file):
    with open(frequency_file, "w", encoding="utf-8", newline="\n") as f:
      f.write(str(shown) + " MHz\n")
  constraint_filename = getattr(arch, "constraint_filename", "") or ""
  if constraint_filename:
    path = os.path.join(arch.tmp_dir, constraint_filename)
    if os.path.exists(path):
      return
    directory = os.path.dirname(path)
    if directory and not os.path.isdir(directory):
      os.makedirs(directory)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
      f.write(clock_constraint(frequency, getattr(arch, "clock_signal", None)))
