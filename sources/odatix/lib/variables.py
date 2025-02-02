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

import re

odatix_path_pattern = re.compile(r"\$odatix_path")
odatix_eda_tools_path_pattern = re.compile(r"\$eda_tools_path")
work_path_pattern = re.compile(r"\$work_path")
tool_install_path_pattern = re.compile(r"\$tool_install_path")
script_path_pattern = re.compile(r"\$script_path")
log_path_pattern = re.compile(r"\$log_path")
clock_signal_pattern = re.compile(r"\$clock_signal")
top_level_module_pattern = re.compile(r"\$top_level_module")
lib_name_pattern = re.compile(r"\$lib_name")

class Variables:
  def __init__(
    self,
    odatix_path = None,
    odatix_eda_tools_path = None,
    work_path = None,
    tool_install_path = None,
    script_path = None,
    log_path = None,
    clock_signal = None,
    top_level_module = None,
    lib_name = None,
  ):
    self.odatix_path = odatix_path
    self.odatix_eda_tools_path = odatix_eda_tools_path
    self.work_path = work_path
    self.tool_install_path = tool_install_path
    self.script_path = script_path
    self.log_path = log_path
    self.clock_signal = clock_signal
    self.top_level_module = top_level_module
    self.lib_name = lib_name

def replace_variables(command, variables):
  if variables is not None:
    if variables.odatix_path is not None:
      command = re.sub(odatix_path_pattern, variables.odatix_path, command)
    if variables.odatix_eda_tools_path is not None:
      command = re.sub(odatix_eda_tools_path_pattern, variables.odatix_eda_tools_path, command)
    if variables.work_path is not None:
      command = re.sub(work_path_pattern, variables.work_path, command)
    if variables.tool_install_path is not None:
      command = re.sub(tool_install_path_pattern, variables.tool_install_path, command)
    if variables.script_path is not None:
      command = re.sub(script_path_pattern, variables.script_path, command)
    if variables.log_path is not None:
      command = re.sub(log_path_pattern, variables.log_path, command)
    if variables.clock_signal is not None:
      command = re.sub(clock_signal_pattern, variables.clock_signal, command)
    if variables.top_level_module is not None:
      command = re.sub(top_level_module_pattern, variables.top_level_module, command)
    if variables.lib_name is not None:
      command = re.sub(lib_name_pattern, variables.lib_name, command)

  return command
