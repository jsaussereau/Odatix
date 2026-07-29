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
import sys
import yaml

from odatix.lib.get_from_dict import get_from_dict, Key, KeyNotInDictError, BadValueInDictError
import odatix.lib.printc as printc

script_name = os.path.basename(__file__)

def read_tool_settings(tool, tool_settings_file, synth_type='fmax_synthesis', flow=None):
  """
  Reads the settings for a given EDA tool from a YAML configuration file.

  When the tool is defined both in the built-in and in the user tools directory,
  the two tool.yml files are merged (see eda_tools.load_tool_settings), so users
  can add flows to a built-in tool without copying its whole definition.

  Args:
    tool (str): The name of the EDA tool.
    tool_settings_file (str): The path to the YAML configuration file.
    synth_type (str, optional): The job type to run.
                                One of 'fmax_synthesis', 'custom_freq_synthesis'
                                or 'analysis'. Defaults to 'fmax_synthesis'.
    flow (str, optional): The flow to run the job type with. Defaults to the
                          tool's default flow.

  Returns:
    tuple: A tuple containing:
      - process_group (bool): Whether the process grouping is enabled.
      - report_path (str): Path of the report directory.
      - synthesis_command (list): The command for the selected job type and flow.
      - tool_test_command (list): The command to check if the tool is installed.
      - default_metrics_file (str): Path to the metrics file of the flow.
      - flow_name (str): The name of the flow that was resolved.
      - steps (list | None): The ordered steps of the flow ({"name", "command"}),
        or None when the flow runs the job type in one shot.

  Raises:
    SystemExit: If the settings file does not exist, is invalid, or if the requested tool,
                job type or flow is not supported.
  """
  import odatix.lib.eda_tools as eda_tools

  # Unknown job types keep the historical fallback to custom frequency synthesis.
  if synth_type not in eda_tools.JOB_TYPE_COMMAND_KEYS:
    synth_type = "custom_freq_synthesis"

  if not os.path.isfile(tool_settings_file):
    printc.error(
      f'Settings file "{tool_settings_file}", for the selected EDA tool "{tool}" does not exist', script_name
    )
    sys.exit(-1)

  settings_data = eda_tools.load_tool_settings(tool)
  if not settings_data:
    # The tool could not be resolved by name (e.g. an out-of-tree settings
    # file): fall back to reading the given file alone.
    with open(tool_settings_file, "r") as f:
      try:
        settings_data = yaml.load(f, Loader=yaml.loader.SafeLoader)
      except Exception as e:
        printc.error(f'Settings file "{tool_settings_file}", for the selected EDA tool "{tool}" is not a valid YAML file', script_name)
        printc.cyan("Error details: ", end="", script_name=script_name)
        print(str(e))
        sys.exit(-1)

  # Retrieve global settings
  process_group, _ = get_from_dict("process_group", settings_data, tool_settings_file, default_value=True, script_name=script_name)
  report_path, _ = get_from_dict("report_path", settings_data, tool_settings_file, default_value="report", silent=True, script_name=script_name)
  default_metrics_file, _ = get_from_dict("default_metrics_file", settings_data, tool_settings_file, behavior=Key.MANTADORY, script_name=script_name)

  # Determine the current platform (Unix or Windows)
  platform_key = "windows" if sys.platform == 'win32' else "unix"

  # Ensure the corresponding section exists in the configuration file
  if platform_key not in settings_data:
    printc.error(f'The selected EDA tool "{tool}" does not support {platform_key}', script_name)
    sys.exit(-1)

  platform_settings = settings_data[platform_key]

  # Retrieve tool test command
  tool_test_command, tool_test_supported = get_from_dict("tool_test_command", platform_settings, tool_settings_file, silent=True, script_name=script_name)

  if not tool_test_supported:
    printc.error(f'The selected EDA tool "{tool}" is not supported on {platform_key} (tool_test_command is missing)', script_name)
    sys.exit(-1)

  # Retrieve the command of the requested job type, for the requested flow.
  # The flow defaults to the tool's default flow (the commands declared directly
  # in the platform section of tool.yml).
  available_flows = eda_tools.list_flows(tool, settings=settings_data)
  runnable_flows = eda_tools.list_flows(tool, job_type=synth_type, settings=settings_data)
  job_type_label = synth_type.replace("_", " ").capitalize()

  if not runnable_flows:
    printc.error(f'{job_type_label} is not supported with the selected EDA tool "{tool}" on {platform_key}', script_name)
    sys.exit(-1)

  if flow is None or str(flow).strip() == "":
    flow_name = next((name for name, item in runnable_flows.items() if item["is_default"]), None)
    if flow_name is None:
      flow_name = next(iter(runnable_flows))
  else:
    flow_name = str(flow).strip()
    if flow_name not in runnable_flows:
      if flow_name in available_flows:
        printc.error(f'The flow "{flow_name}" of the EDA tool "{tool}" cannot run {job_type_label.lower()}', script_name)
      else:
        printc.error(f'The EDA tool "{tool}" has no flow named "{flow_name}"', script_name)
      printc.note(f'Flows of "{tool}" able to run {job_type_label.lower()}: ' + ", ".join(runnable_flows), script_name)
      sys.exit(-1)

  selected_flow = runnable_flows[flow_name]

  # A flow running a different binary (e.g. dcnxt_shell instead of dc_shell)
  # declares its own installation check.
  if selected_flow["tool_test_command"] is not None:
    tool_test_command = selected_flow["tool_test_command"]

  # A flow either runs the job type in one shot ("<job_type>_command") or as an
  # ordered list of steps ("<job_type>_steps") that can be run partially and
  # resumed.
  steps_key = eda_tools.JOB_TYPE_STEPS_KEYS[synth_type]
  steps = selected_flow["steps"].get(steps_key)
  synthesis_key = eda_tools.JOB_TYPE_COMMAND_KEYS[synth_type]
  synthesis_command = selected_flow["commands"].get(synthesis_key)
  if steps:
    # The pipeline is built from the steps; the last one stands in for the
    # single command wherever one is still expected.
    synthesis_command = steps[-1]["command"]

  # A flow can ship its own metrics definition file (e.g. a place & route flow
  # reporting metrics a synthesis-only flow does not have).
  if selected_flow["metrics_file"]:
    default_metrics_file = selected_flow["metrics_file"]

  return process_group, report_path, synthesis_command, tool_test_command, default_metrics_file, flow_name, steps
