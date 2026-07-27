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
Discovery and resolution of EDA tools.

An EDA tool is a directory containing a "tool.yml" file (and usually a
"metrics.yml" and tcl/makefile scripts). Tools are looked up in two locations,
in order of precedence:

  1. the user tools directory (OdatixSettings.user_tools_path, defaulting to
     "odatix_userconfig/tools"), so users can add or override tools;
  2. the built-in tools directory shipped with Odatix
     (OdatixSettings.odatix_eda_tools_path).

There is no hard-coded list of supported tools: the list is discovered by
scanning these directories. A tool found in the user directory shadows a
built-in tool with the same name.
"""

import os

import odatix.lib.hard_settings as hard_settings

script_name = os.path.basename(__file__)


def get_search_paths():
  """
  Return the ordered list of directories to search for tools, highest
  precedence first (user tools directory, then the built-in one). Only
  existing directories are returned.
  """
  from odatix.lib.settings import OdatixSettings

  paths = []
  user_tools_path = OdatixSettings.user_tools_path
  if user_tools_path is None:
    # No settings file has been read yet: fall back to the default location,
    # relative to the current working directory.
    user_tools_path = os.path.realpath(OdatixSettings.DEFAULT_TOOLS_PATH)
  if os.path.isdir(user_tools_path):
    paths.append(user_tools_path)
  if os.path.isdir(OdatixSettings.odatix_eda_tools_path):
    paths.append(OdatixSettings.odatix_eda_tools_path)
  return paths


def get_tool_dir(tool):
  """
  Return the resolved directory of a tool (the first search path containing
  "<tool>/tool.yml"), or None if the tool is not found in any location.
  """
  for search_path in get_search_paths():
    candidate = os.path.join(search_path, tool)
    if os.path.isfile(os.path.join(candidate, hard_settings.tool_settings_filename)):
      return candidate
  return None


def get_tool_settings_file(tool):
  """
  Return the path to the "tool.yml" file of a tool, or None if the tool is not
  found.
  """
  tool_dir = get_tool_dir(tool)
  if tool_dir is None:
    return None
  return os.path.realpath(os.path.join(tool_dir, hard_settings.tool_settings_filename))


def is_supported(tool):
  """True if the tool can be resolved to a directory with a tool.yml."""
  return get_tool_dir(tool) is not None


def list_tools():
  """
  Discover all available tools. Return an ordered dict {tool_name: tool_dir}.
  The built-in tools are listed first, then user tools; a user tool with the
  same name as a built-in one overrides its directory but keeps the built-in
  ordering.
  """
  from odatix.lib.settings import OdatixSettings

  tools = {}
  # Built-in first (defines the base ordering), then user tools override.
  ordered_paths = []
  if os.path.isdir(OdatixSettings.odatix_eda_tools_path):
    ordered_paths.append(OdatixSettings.odatix_eda_tools_path)
  for search_path in reversed(get_search_paths()):
    if search_path not in ordered_paths:
      ordered_paths.append(search_path)

  for search_path in ordered_paths:
    try:
      entries = sorted(os.listdir(search_path))
    except OSError:
      continue
    for name in entries:
      # Ignore shared/private directories (e.g. "_common").
      if name.startswith("_") or name.startswith("."):
        continue
      tool_dir = os.path.join(search_path, name)
      if os.path.isfile(os.path.join(tool_dir, hard_settings.tool_settings_filename)):
        tools[name] = tool_dir
  return tools


def get_supported_tools():
  """Return the sorted list of discovered tool names."""
  return list(list_tools().keys())


def _load_tool_yml(tool):
  """Load and return the parsed tool.yml of a tool, or {} on any error."""
  import yaml

  settings_file = get_tool_settings_file(tool)
  if settings_file is None or not os.path.isfile(settings_file):
    return {}
  try:
    with open(settings_file, "r") as f:
      data = yaml.load(f, Loader=yaml.loader.SafeLoader)
  except Exception:
    return {}
  return data if isinstance(data, dict) else {}


# Mapping from a flow/job type to the tool.yml key that declares its command.
FLOW_COMMAND_KEYS = {
  "fmax_synthesis": "fmax_synthesis_command",
  "custom_freq_synthesis": "custom_freq_synthesis_command",
  "analysis": "analysis_command",
  "analyze": "analysis_command",
}


def get_tool_label(tool):
  """
  Return a human-readable label for a tool. Uses the optional "label" key of
  tool.yml, falling back to the tool name.
  """
  data = _load_tool_yml(tool)
  label = data.get("label")
  if isinstance(label, str) and label.strip():
    return label.strip()
  return tool


def tool_supports(tool, flow):
  """
  Return True if the tool declares a command for the given flow (one of the
  keys of FLOW_COMMAND_KEYS). The presence of the corresponding command key in
  the current platform section of tool.yml is used as the capability signal.
  """
  import sys

  command_key = FLOW_COMMAND_KEYS.get(flow)
  if command_key is None:
    return False
  data = _load_tool_yml(tool)
  platform_key = "windows" if sys.platform == "win32" else "unix"
  platform_settings = data.get(platform_key)
  if not isinstance(platform_settings, dict):
    return False
  return command_key in platform_settings


def tools_supporting(flow):
  """Return the list of discovered tool names that support the given flow."""
  return [tool for tool in list_tools() if tool_supports(tool, flow)]


def get_target_filename(tool):
  """
  Return the target definition file name of a tool: the optional "target_file"
  key of tool.yml, falling back to the default "target_<tool>.yml".
  """
  data = _load_tool_yml(tool)
  name = data.get("target_file")
  if isinstance(name, str) and name.strip():
    return name.strip()
  return "target_" + tool + ".yml"


def resolve_target_file(tool, target_path, fallback_dir=None):
  """
  Resolve the target definition file of a tool. The file name comes from the
  tool's tool.yml (see get_target_filename). It is looked up first in
  `target_path`, then in `fallback_dir` (the userconfig root by default), so
  target files kept at the old default location still resolve.

  Returns the path of the first existing candidate, or the primary
  (`target_path`) path when none exists (for error reporting / new files).
  """
  from odatix.lib.settings import OdatixSettings

  filename = get_target_filename(tool)
  if fallback_dir is None:
    fallback_dir = OdatixSettings.DEFAULT_TARGET_FALLBACK_PATH

  primary = os.path.join(target_path, filename)
  candidates = [primary]
  fallback = os.path.join(fallback_dir, filename)
  if os.path.realpath(fallback) != os.path.realpath(primary):
    candidates.append(fallback)

  for candidate in candidates:
    if os.path.isfile(candidate):
      return os.path.realpath(candidate)
  return os.path.realpath(primary)
