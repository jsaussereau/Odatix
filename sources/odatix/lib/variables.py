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

import os
import odatix.lib.printc as printc

script_name = os.path.basename(__file__)

class Variables:
  def __init__(
    self,
    odatix_path = None,
    odatix_eda_tools_path = None,
    tool_path = None,
    work_path = None,
    tool_install_path = None,
    script_path = None,
    log_path = None,
    rtl_path = None,
    report_path = None,
    result_path = None,
    clock_signal = None,
    top_level_module = None,
    lib_name = None,
    architecture = None,
    target = None,
    tool = None,
    source_work_path = None,
    source_tool = None,
  ):
    self.odatix_path = odatix_path
    self.odatix_eda_tools_path = odatix_eda_tools_path
    self.tool_path = tool_path
    self.work_path = work_path
    self.tool_install_path = tool_install_path
    self.script_path = script_path
    self.log_path = log_path
    self.rtl_path = rtl_path
    self.report_path = report_path
    self.result_path = result_path
    self.architecture = architecture
    self.target = target
    self.tool = tool
    self.clock_signal = clock_signal
    self.top_level_module = top_level_module
    self.lib_name = lib_name
    # Place & route jobs only: the synthesis job this one starts from.
    # $work_path is already taken and means *this* job's directory.
    self.source_work_path = source_work_path
    self.source_tool = source_tool

def replace_variables(command, variables):
  if variables is None:
    return command
  try:
    command_out = command
    replacements = {
      "$odatix_path": variables.odatix_path,
      "$eda_tools_path": variables.odatix_eda_tools_path,
      "$tool_path": variables.tool_path,
      "$work_path": variables.work_path,
      "$tool_install_path": variables.tool_install_path,
      "$script_path": variables.script_path,
      "$log_path": variables.log_path,
      "$rtl_path": variables.rtl_path,
      "$report_path": variables.report_path,
      "$result_path": variables.result_path,
      "$clock_signal": variables.clock_signal,
      "$top_level_module": variables.top_level_module,
      "$lib_name": variables.lib_name,
      "$architecture": variables.architecture,
      "$target": variables.target,
      "$tool": variables.tool,
      "$source_work_path": variables.source_work_path,
      "$source_tool": variables.source_tool,
    }
    # Longest name first: a plain replace of "$tool" would otherwise eat the
    # beginning of "$tool_path" and "$tool_install_path".
    for key, value in sorted(replacements.items(), key=lambda item: -len(item[0])):
      if value is not None:
        command_out = command_out.replace(key, value)
  except Exception as e:
    printc.error(f'Failed replacing variable "{key}" by {value}', script_name=script_name)
    printc.cyan("error details: ", end="", script_name=script_name)
    print(str(e))
    return command

  return command_out