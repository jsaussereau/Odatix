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


def _normalize_path(path):
  """Normalise a path for Windows/Unix compatibility inside a tcl script."""
  path = os.path.realpath(path)
  if sys.platform == "win32":
    path = path.replace("\\", "/")
  return path


def _apply_replacements(config_file, replacements):
  """Rewrite the "set <name> <value>" lines of a tcl settings file."""
  with open(config_file, 'r', encoding='utf-8') as f:
    cf_content = f.read()

  for pattern, replacement in replacements.items():
    cf_content = re.sub(pattern, replacement, cf_content, flags=re.MULTILINE)

  with open(config_file, 'w', encoding='utf-8') as f:
    f.write(cf_content)


def edit_config_file(arch, config_file):
  """Replace settings in tcl config file"""

  tmp_path = _normalize_path(arch.tmp_dir)
  constraints_file = "$tmp_path" + "/" + arch.constraint_filename

  def safe_replace(value):
    if value is None:
      return ""
    return value

  # Replace rules definition
  replacements = {
    r"(set top_level_module\s+).*":   lambda m: f"{m.group(1)}{safe_replace(arch.top_level_module)}",
    r"(set top_level_file\s+).*":     lambda m: f"{m.group(1)}{safe_replace(arch.top_level_filename)}",
    r"(set clock_signal\s+).*":       lambda m: f"{m.group(1)}{safe_replace(arch.clock_signal)}",
    r"(set reset_signal\s+).*":       lambda m: f"{m.group(1)}{safe_replace(arch.reset_signal)}",
    r"(set local_rtl_path\s+).*":     lambda m: f"{m.group(1)}{safe_replace(arch.local_rtl_path)}",
    r"(set tmp_path\s+).*":           lambda m: f"{m.group(1)}{safe_replace(tmp_path)}",
    r"(set source_rtl_path\s+).*":    lambda m: f"{m.group(1)}{safe_replace(arch.rtl_path)}",
    r"(set source_arch_path\s+).*":   lambda m: f"{m.group(1)}{safe_replace(arch.arch_path)}",
    r"(set constraints_file\s+).*":   lambda m: f"{m.group(1)}{safe_replace(constraints_file)}",
    r"(set target_frequency\s+).*":   lambda m: f"{m.group(1)}{arch.target_frequency}",
    r"(set fmax_lower_bound\s+).*":   lambda m: f"{m.group(1)}{arch.fmax_lower_bound}",
    r"(set fmax_upper_bound\s+).*":   lambda m: f"{m.group(1)}{arch.fmax_upper_bound}",
    r"(set lib_name\s+).*":           lambda m: f"{m.group(1)}{safe_replace(arch.lib_name)}",
    r"(set continue_on_error\s+).*":  lambda m: f"{m.group(1)}" + ("1" if arch.continue_on_error else "0"),
    r"(set single_thread\s+).*":      lambda m: f"{m.group(1)}" + ("1" if arch.force_single_thread else "0"),
  }

  _apply_replacements(config_file, replacements)


def edit_pnr_config_file(arch, source, config_file):
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

  replacements = {
    r"(set source_work_path\s+).*":  lambda m: f"{m.group(1)}{quoted(_normalize_path(source.job_dir))}",
    r"(set source_tool\s+).*":       lambda m: f"{m.group(1)}{quoted(source.tool)}",
    r"(set source_flow\s+).*":       lambda m: f"{m.group(1)}{quoted(source.flow)}",
    r"(set source_type\s+).*":       lambda m: f"{m.group(1)}{quoted(source.job_type)}",
    r"(set source_netlist\s+).*":    lambda m: f"{m.group(1)}{quoted(_normalize_path(source.netlist))}",
    r"(set source_sdc\s+).*":        lambda m: f"{m.group(1)}{quoted(_normalize_path(source.sdc))}",
    r"(set source_sdf\s+).*":        lambda m: f"{m.group(1)}{quoted(_normalize_path(source.sdf))}",
    r"(set constraints_file\s+).*":  lambda m: f"{m.group(1)}{quoted(_normalize_path(source.sdc))}",
  }

  _apply_replacements(config_file, replacements)
