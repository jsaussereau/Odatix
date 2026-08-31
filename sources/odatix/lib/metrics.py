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
Layered resolution of the metrics definitions of an eda tool.

The metrics of a tool (how each value is extracted from its reports, see
odatix.components.export_results.extract_metrics) are not read from a single
file anymore: they are the merge of every metrics file defining that tool,
lowest precedence first:

  1. the metrics file shipped with the built-in tool ("default_metrics_file" of
     its tool.yml, or the "metrics_file" of the flow being exported);
  2. the same file in the workspace tools directory, when the workspace defines
     a tool of that name;
  3. "<tools_path>/<tool>/metrics.yml" in the workspace, which needs no tool.yml
     next to it: dropping that single file into the workspace is all it takes to
     complete or override the metrics of a built-in tool.

Merging happens metric by metric, inside each section
("fmax_synthesis_metrics", "custom_freq_synthesis_metrics", "pnr_metrics", "metrics"):

  * a metric the workspace defines and the built-in file does not is added;
  * a metric of the same name replaces the built-in one entirely (the whole
    definition, not key by key: a half-overridden regex would be a trap);
  * a metric mapped to nothing (``LUT_percent:``, i.e. YAML null) removes the
    built-in one from the export.

The same resolution is used everywhere metrics are read: the export run right
after a job, "odatix results", and the GUI metrics editor.
"""

import os

import odatix.lib.eda_tools as eda_tools
import odatix.lib.printc as printc
from odatix.lib.settings import OdatixSettings
from odatix.lib.variables import replace_variables, Variables
import odatix.lib.yaml_loader as yaml_loader

script_name = os.path.basename(__file__)

# Name of the metrics file a workspace tool directory may hold to complete or
# override the metrics of the built-in tool of the same name.
METRICS_FILENAME = "metrics.yml"

# The sections of a metrics file, i.e. the keys holding {metric name: definition}
# mappings. Anything else in the file is merged as a plain key.
METRIC_SECTION_KEYS = ("fmax_synthesis_metrics", "custom_freq_synthesis_metrics", "pnr_metrics", "metrics")


def user_tools_path(tools_path=None):
  """
  The workspace tools directory. `tools_path` overrides it (the GUI knows it
  from the workspace settings it holds); otherwise it falls back to the settings
  read at startup, then to the default location relative to the current
  directory, like eda_tools.get_search_paths does.
  """
  if isinstance(tools_path, str) and tools_path.strip():
    return tools_path
  path = OdatixSettings.user_tools_path
  if path is None:
    path = os.path.realpath(OdatixSettings.DEFAULT_TOOLS_PATH)
  return path


def workspace_metrics_file(tool, tools_path=None):
  """
  Path of the workspace metrics file of a tool ("<tools_path>/<tool>/metrics.yml"),
  whether or not it exists.
  """
  return os.path.join(user_tools_path(tools_path), tool, METRICS_FILENAME)


def merge_metrics_data(base, override):
  """
  Merge an overriding metrics file over a base one, and return a new dict.

  Sections are merged metric by metric; a metric whose definition is None is
  removed. Any other key is replaced.
  """
  merged = dict(base) if isinstance(base, dict) else {}
  if not isinstance(override, dict):
    return merged

  for key, value in override.items():
    if key not in METRIC_SECTION_KEYS or not isinstance(value, dict):
      merged[key] = value
      continue

    section = dict(merged.get(key)) if isinstance(merged.get(key), dict) else {}
    for metric_name, definition in value.items():
      if definition is None:
        section.pop(metric_name, None)
      else:
        section[metric_name] = definition
    merged[key] = section

  return merged


def _read_yaml(path):
  """Load a metrics file into a dict. Returns None when it cannot be parsed."""
  import yaml

  with open(path, "r") as file:
    try:
      data = yaml_loader.safe_load(file)
    except yaml.YAMLError as e:
      printc.error('Error in metrics definition file "' + path + '": ' + str(e), script_name)
      return None
  if data is None:
    return {}
  if not isinstance(data, dict):
    printc.error('Metrics definition file "' + path + '" must contain a YAML mapping at top level', script_name)
    return None
  return data


def metrics_file_template(tool, flow=None):
  """
  The metrics file declared for a tool run with a given flow, as written in
  tool.yml (still holding its "$tool_path" variable). Returns None when the tool
  declares none.
  """
  template = None
  if flow:
    flow_settings = eda_tools.get_flow(tool, flow=flow)
    if flow_settings is not None:
      template = flow_settings["metrics_file"]
  if not template:
    template = eda_tools.load_tool_settings(tool).get("default_metrics_file")
  if not isinstance(template, str) or template.strip() == "":
    return None
  return template


def metrics_files(tool, flow=None, missing_ok=False, tools_path=None):
  """
  Every existing metrics file defining a tool, lowest precedence first.

  Returns an empty list when the tool is unknown or declares no metrics file;
  when it declares one that exists nowhere, an error is printed (unless
  `missing_ok`) and an empty list is returned.
  """
  tool_dirs = eda_tools.get_tool_dirs(tool)  # lowest precedence first
  if not tool_dirs:
    return []

  template = metrics_file_template(tool, flow=flow)
  if template is None:
    printc.error('Cannot find key "default_metrics_file" for the eda tool "' + str(tool) + '"', script_name)
    return []

  # The workspace directory of the tool takes part in the resolution even
  # without a tool.yml in it: a lone metrics.yml is enough to override metrics.
  search_dirs = list(tool_dirs)
  overlay_dir = os.path.join(user_tools_path(tools_path), tool)
  if os.path.isdir(overlay_dir) and overlay_dir not in search_dirs:
    search_dirs.append(overlay_dir)

  files = []
  declared = []
  for tool_dir in search_dirs:
    resolved = replace_variables(
      template,
      Variables(
        odatix_path=OdatixSettings.odatix_path,
        odatix_eda_tools_path=OdatixSettings.odatix_eda_tools_path,
        tool_path=tool_dir,
      ),
    )
    if resolved in declared:
      continue
    declared.append(resolved)
    if os.path.isfile(resolved) and resolved not in files:
      files.append(resolved)

  # The workspace overlay file, when the tool (or its flow) declares a metrics
  # file under another name.
  overlay_file = workspace_metrics_file(tool, tools_path)
  if os.path.isfile(overlay_file) and overlay_file not in files:
    files.append(overlay_file)

  if not files and not missing_ok:
    printc.error('Metrics definition file "' + os.path.realpath(declared[0]) + '" does not exist', script_name)
  return files


def load_metrics(tool, custom_metrics_file=None, flow=None):
  """
  Load the metrics definitions of a tool, merging every file defining it.

  When `custom_metrics_file` is given (``odatix results --metrics``), it is used
  alone: an explicit file replaces the whole definition.

  Returns:
      tuple: (metrics_data, source) where `source` names the file(s) the
      definitions come from (for error messages), or (None, None) on error.
  """
  if custom_metrics_file is not None:
    if not os.path.isfile(custom_metrics_file):
      printc.error('Metrics definition file "' + os.path.realpath(custom_metrics_file) + '" does not exist', script_name)
      return None, None
    files = [custom_metrics_file]
  else:
    files = metrics_files(tool, flow=flow)
    if not files:
      return None, None

  metrics_data = {}
  for path in files:
    data = _read_yaml(path)
    if data is None:
      return None, None
    metrics_data = merge_metrics_data(metrics_data, data)

  return metrics_data, " + ".join(files)


def load_metrics_layers(tool, flow=None, tools_path=None):
  """
  Load the metrics of a tool as two layers, for the GUI: what Odatix (or another
  file the workspace does not own) defines, and what the workspace metrics.yml
  says about it.

  Returns:
      tuple: (builtin, workspace) where `builtin` is the merge of every metrics
      file but the workspace one ({section: {name: definition}}), and
      `workspace` is the raw content of "<tools_path>/<tool>/metrics.yml"
      (definitions, plus the None entries removing a built-in metric).
  """
  overlay_file = workspace_metrics_file(tool, tools_path)

  builtin = {}
  for path in metrics_files(tool, flow=flow, missing_ok=True, tools_path=tools_path):
    if os.path.realpath(path) == os.path.realpath(overlay_file):
      continue
    data = _read_yaml(path)
    if data is not None:
      builtin = merge_metrics_data(builtin, data)

  workspace = {}
  if os.path.isfile(overlay_file):
    data = _read_yaml(overlay_file)
    if data is not None:
      workspace = data

  def sections(data):
    return {key: (data.get(key) if isinstance(data.get(key), dict) else {}) for key in METRIC_SECTION_KEYS}

  return sections(builtin), sections(workspace)
