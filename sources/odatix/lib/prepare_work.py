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

def edit_config_file(arch, config_file):
  """Replace settings in tcl config file"""

  # Read tcl settings file
  with open(config_file, 'r', encoding='utf-8') as f:
    cf_content = f.read()

  # Normalise path for Windows/Unix compatibility
  tmp_path = os.path.realpath(arch.tmp_dir)
  if sys.platform == "win32":
    tmp_path = tmp_path.replace("\\", "/") 
  
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

  # Replace
  for pattern, replacement in replacements.items():
    cf_content = re.sub(pattern, replacement, cf_content, flags=re.MULTILINE)

  # Write tcl settings file
  with open(config_file, 'w', encoding='utf-8') as f:
    f.write(cf_content)
