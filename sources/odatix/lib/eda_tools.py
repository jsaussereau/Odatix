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
Discovery and resolution of EDA tools and their flows.

An EDA tool is a directory containing a "tool.yml" file (and usually a
"metrics.yml" and tcl/makefile scripts). Tools are looked up in two locations,
in order of precedence:

  1. the user tools directory (OdatixSettings.user_tools_path, defaulting to
     "odatix_userconfig/tools"), so users can add or override tools;
  2. the built-in tools directory shipped with Odatix
     (OdatixSettings.odatix_eda_tools_path).

There is no hard-coded list of supported tools: the list is discovered by
scanning these directories.

A tool can be defined in both locations at once: the tool.yml files are then
merged, the user one taking precedence key by key. This is what lets a user add
a flow to a built-in tool without copying its whole definition. The built-in
flows themselves stay read-only: what a user tool.yml says about them is dropped
(see strip_builtin_overrides), so a built-in tool always runs what Odatix says it
runs. Duplicating the tool gives a tool of its own, with nothing read-only left.

Two distinct notions must not be confused:

  * a *job type* is what Odatix runs: "fmax_synthesis", "custom_freq_synthesis"
    or "analysis". It is chosen by the command being run (odatix fmax, ...).
  * a *flow* is a way of running a tool: a different script, different options,
    sometimes a different binary — Vivado timing oriented versus power oriented
    with clock gating, Design Compiler with dc_shell versus dcnxt_shell. It is
    chosen with "--flow" (or on the GUI's flow page).

Flows are declared in the "flows" section of tool.yml. The commands declared
directly in the tool's "unix"/"windows" section belong to the tool's default
flow, whose name is given by the optional top-level "default_flow" key
(DEFAULT_FLOW_NAME otherwise):

    default_flow: standard

    unix:
      tool_test_command: [...]
      fmax_synthesis_command: [...]          # commands of the "standard" flow
      custom_freq_synthesis_command: [...]

    flows:
      standard:                              # metadata for the default flow
        label: "Standard"
      power_opt:                             # an additional flow
        label: "Power optimized"
        unix:
          custom_freq_synthesis_command: [...]

Being split into steps is a property of a flow, not a flow of its own: a flow
declares "<job_type>_steps" (an ordered list of named commands) instead of
"<job_type>_command", and every flow of the tool can be stepped.

A step either declares the whole "command" it runs — it is then a process of its
own — or only the "args" it adds to a session of the tool:

    unix:
      custom_freq_synthesis_session:
        command: [vivado, -mode tcl, -log $log_path/synthesis.log]
        end:     [-source $script_path/exit.tcl]
      custom_freq_synthesis_steps:
        - name: synthesis
          args: [-source $script_path/step_synthesis.tcl]
        - name: pnr
          args: [-source $script_path/step_pnr.tcl]

The steps of a run that share a session are then run by a *single* process: the
tool is opened once, sources what each step adds, and exits — instead of being
opened and closed once per step. What a run covers still starts at the first
step left to do and stops where it was told to, so a session covers exactly the
steps of that run.

A flow starts from the default flow's declaration for each job type and changes
only what it says:

  * declaring "<job_type>_command" replaces the default flow's command *and* its
    steps for that job type: the flow runs it in one shot.
  * declaring "<job_type>_steps" merges into the default flow's steps **by step
    name**: a step of the same name is replaced, the order of the inherited
    steps is kept, and steps the default flow does not have are appended. A flow
    changing only how the design is synthesized therefore declares that one
    step and inherits the rest.
  * declaring "<job_type>_session" merges into the default flow's session **key
    by key**: a flow changing what every session of a job type does (an extra
    script to source, another log file) says that much and keeps the steps as
    they are.
  * declaring none of them means running the default flow's command (or steps)
    for that job type.

A flow supports a job type when, after that merge, it has a command or steps for
it — which, since the default flow's declaration is inherited, is the case for
every flow of a tool unless a job type is missing from the tool itself. The
"tool_test_command" is inherited the same way, and only a flow running a
different binary needs to override it.

Flows of the same tool are alternatives meant to be compared, so each one runs
in its own work directory (see tool_work_dirname).
"""

import copy
import os
import sys

import odatix.lib.hard_settings as hard_settings
import odatix.lib.yaml_loader as yaml_loader

script_name = os.path.basename(__file__)

# Name of the implicit flow holding the commands declared directly in the
# "unix"/"windows" section of a tool.yml that does not set "default_flow".
DEFAULT_FLOW_NAME = "default"

# Separator between the tool name and the flow name in work directory names
# ("vivado@power_opt"). Two flows of the same tool are alternatives to compare,
# so they must not share a work directory.
#
# "@" rather than "#": openlane and verilator pass the work directory into a
# makefile (WORK_DIR=$work_path), and "#" starts a comment there, which would
# truncate the path. "@" is safe in makefiles, shells, Tcl and Windows paths.
WORK_DIR_FLOW_SEPARATOR = "@"


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


def _own_tool_dirs(tool):
  """
  The directories defining the tool itself, lowest precedence first, leaving
  out the tool it extends.
  """
  dirs = []
  for search_path in reversed(get_search_paths()):
    candidate = os.path.join(search_path, tool)
    if os.path.isfile(os.path.join(candidate, hard_settings.tool_settings_filename)):
      dirs.append(candidate)
  return dirs


def get_base_tool(tool):
  """
  The tool this one extends ("extends" in its tool.yml), or None.

  A tool extending another is that tool run differently: Design Compiler NXT is
  Design Compiler with another binary. It inherits everything the other one
  declares -- its scripts, its metrics, its flows, its log formatting -- and its
  own tool.yml only says what changes, usually a parameter or two (see
  "parameters" in list_flows). The two remain separate tools: each one has its
  own work directory and its own results file, and a search can compare them.
  """
  base = None
  for tool_dir in _own_tool_dirs(tool):
    declared = _read_yaml(os.path.join(tool_dir, hard_settings.tool_settings_filename)).get("extends")
    if isinstance(declared, str) and declared.strip():
      base = declared.strip()
  return base


def tool_lineage(tool):
  """
  The tool and those it extends, the most basic one first: ["design_compiler",
  "dc_nxt"] for a tool "dc_nxt" extending "design_compiler". A tool extending
  nothing is its own lineage. A cycle, or a tool extending one that does not
  exist, stops the lineage where it breaks.
  """
  lineage = [tool]
  base = get_base_tool(tool)
  while base is not None and base not in lineage and _own_tool_dirs(base):
    lineage.insert(0, base)
    base = get_base_tool(base)
  return lineage


def get_tool_dirs(tool):
  """
  Return every directory defining the tool, lowest precedence first (built-in
  directory, then user directory). A tool defined in both places yields two
  directories: their tool.yml files are merged (see load_tool_settings) and
  their tcl scripts are both copied to the work directory, the user ones last.

  The directories of the tool it extends, if any, come before its own: a tool
  extending another one gets that one's scripts, and overrides those it ships
  under the same name.
  """
  dirs = []
  for name in tool_lineage(tool):
    dirs.extend(_own_tool_dirs(name))
  return dirs


def get_tool_dir(tool):
  """
  Return the resolved directory of a tool (the first search path containing
  "<tool>/tool.yml"), or None if the tool is not found in any location. When the
  tool is defined in several locations, the highest precedence one (the user
  directory) is returned; use get_tool_dirs to get them all, those of the tool it
  extends included.
  """
  dirs = _own_tool_dirs(tool)
  return dirs[-1] if dirs else None


def get_tool_settings_file(tool):
  """
  Return the path to the "tool.yml" file of a tool, or None if the tool is not
  found.
  """
  tool_dir = get_tool_dir(tool)
  if tool_dir is None:
    return None
  return os.path.realpath(os.path.join(tool_dir, hard_settings.tool_settings_filename))


def get_format_settings_file(tool):
  """
  Return the tool.yml holding the log formatting rules of a tool: the highest
  precedence one declaring a "format" section, so a user tool.yml that only adds
  flows does not silently drop the built-in formatting. Falls back to the
  highest precedence tool.yml.
  """
  for tool_dir in reversed(get_tool_dirs(tool)):
    path = os.path.join(tool_dir, hard_settings.tool_settings_filename)
    if "format" in _read_yaml(path):
      return os.path.realpath(path)
  return get_tool_settings_file(tool)


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


def _read_yaml(path):
  """Load a YAML file into a dict, or {} on any error."""
  import yaml

  try:
    with open(path, "r") as f:
      data = yaml.load(f, Loader=yaml_loader.SafeLoader)
  except Exception:
    return {}
  return data if isinstance(data, dict) else {}


def _deep_merge(base, override):
  """
  Merge `override` into `base` (returning a new dict): nested dicts are merged
  key by key, any other value (including lists, i.e. commands) is replaced.
  """
  merged = dict(base)
  for key, value in override.items():
    if isinstance(value, dict) and isinstance(merged.get(key), dict):
      merged[key] = _deep_merge(merged[key], value)
    else:
      merged[key] = copy.deepcopy(value)
  return merged


# Keys of a tool.yml declaring the tool's default flow: the commands of the
# platform sections, and the name the flow is known under.
DEFAULT_FLOW_KEYS = ("unix", "windows")

# Paths of the user tool.yml files already warned about, so a rejected override
# is reported once per run rather than on every settings load.
_reported_builtin_overrides = set()


def get_builtin_tool_dir(tool):
  """
  Return the directory of the built-in tool of that name (the one shipped with
  Odatix), or None when the tool is not a built-in one.
  """
  from odatix.lib.settings import OdatixSettings

  candidate = os.path.join(OdatixSettings.odatix_eda_tools_path, tool)
  if os.path.isfile(os.path.join(candidate, hard_settings.tool_settings_filename)):
    return candidate
  return None


def strip_builtin_overrides(builtin, override, tool="", source=""):
  """
  Return the part of a user tool.yml (`override`) that may be applied on top of
  a built-in one (`builtin`).

  The built-in flows belong to Odatix: their commands are what makes a built-in
  tool work, and a workspace silently redefining them would leave Odatix running
  something else than what it reports (and than what the GUI shows, where those
  flows are read-only). So a user tool.yml may add flows and override the rest of
  the settings, but whatever it says about the built-in flows is dropped:

    * the platform sections ("unix"/"windows"), which hold the commands of the
      built-in default flow, and "default_flow", which names it;
    * the entries of "flows" the built-in tool already declares.

  Everything the built-in definition does not declare goes through untouched: a
  flow of its own, a "format" section, a "label"... Dropped keys are reported
  once per file, so a hand-written override does not fail silently.

  `tool` and `source` are only used for that message.
  """
  import odatix.lib.printc as printc

  if not isinstance(builtin, dict) or not builtin or not isinstance(override, dict):
    return override if isinstance(override, dict) else {}

  builtin_flows = builtin.get("flows") if isinstance(builtin.get("flows"), dict) else {}
  # A built-in tool declaring commands has a default flow, whether or not it
  # names it: renaming it is redefining it.
  has_default_flow = any(key in builtin for key in DEFAULT_FLOW_KEYS)

  kept = {}
  rejected = []
  for key, value in override.items():
    if key in DEFAULT_FLOW_KEYS and key in builtin:
      rejected.append('the "%s" commands of the built-in default flow' % key)
      continue
    if key == "default_flow" and has_default_flow:
      rejected.append('"default_flow"')
      continue
    if key == "flows" and isinstance(value, dict):
      added = {name: spec for name, spec in value.items() if str(name) not in builtin_flows}
      rejected.extend('the built-in flow "%s"' % name for name in value if str(name) in builtin_flows)
      if added:
        kept[key] = added
      continue
    kept[key] = value

  if rejected and source not in _reported_builtin_overrides:
    _reported_builtin_overrides.add(source)
    printc.warning(
      "Ignoring what '%s' says about %s: the built-in flows of tool '%s' are read-only."
      % (source, ", ".join(rejected), tool),
      script_name=script_name,
    )
    printc.note(
      "Duplicate the tool to start from what it does, or add a flow of your own instead.",
      script_name=script_name,
    )

  return kept


def load_tool_settings(tool):
  """
  Load the settings of a tool, merging the tool.yml files of every directory
  defining it (built-in first, user last). Returns {} if the tool is unknown.

  Merging is done key by key, so a user tool.yml holding only a "flows" section
  adds its flows to the built-in tool without having to repeat the rest of its
  definition. What a user tool.yml says about the built-in flows is dropped
  first (see strip_builtin_overrides): those belong to Odatix.

  A tool extending another one (see get_base_tool) starts from that one's
  settings, merged the same way, and its own are merged on top.
  """
  settings = {}
  for name in tool_lineage(tool):
    settings = _deep_merge(settings, _load_own_tool_settings(name))
  return settings


def _load_own_tool_settings(tool):
  """The settings a tool declares itself, without those of the tool it extends."""
  settings = {}
  builtin_dir = get_builtin_tool_dir(tool)
  builtin = {}
  for tool_dir in _own_tool_dirs(tool):
    path = os.path.join(tool_dir, hard_settings.tool_settings_filename)
    data = _read_yaml(path)
    if builtin_dir is not None and os.path.realpath(tool_dir) == os.path.realpath(builtin_dir):
      builtin = data
    else:
      data = strip_builtin_overrides(builtin, data, tool=tool, source=path)
    settings = _deep_merge(settings, data)
  return settings


def _load_tool_yml(tool):
  """Backward-compatible alias of load_tool_settings."""
  return load_tool_settings(tool)


# Mapping from a job type to the tool.yml key that declares its command.
JOB_TYPE_COMMAND_KEYS = {
  "fmax_synthesis": "fmax_synthesis_command",
  "custom_freq_synthesis": "custom_freq_synthesis_command",
  "analysis": "analysis_command",
  "analyze": "analysis_command",
  # Place & route of a design another tool has already synthesized: the job
  # starts from that synthesis job's netlist rather than from the RTL.
  "pnr": "pnr_command",
}

# Deprecated alias, kept so external tool scripts importing it keep working.
FLOW_COMMAND_KEYS = JOB_TYPE_COMMAND_KEYS

# Mapping from a job type to the tool.yml key that declares its ordered steps.
# A flow declares either "<job_type>_command" (one shot) or "<job_type>_steps"
# (an ordered list of steps that can be run partially and resumed).
JOB_TYPE_STEPS_KEYS = {
  "fmax_synthesis": "fmax_synthesis_steps",
  "custom_freq_synthesis": "custom_freq_synthesis_steps",
  "analysis": "analysis_steps",
  "analyze": "analysis_steps",
  "pnr": "pnr_steps",
}

# Mapping from a job type to the tool.yml key that declares how to open a
# session of the tool for it: the command launching the tool, and the arguments
# framing whatever the steps add to it. Steps declaring "args" rather than a
# whole "command" are fragments of such a session, which is what lets the steps
# of a single run share one process (see _resolve_steps).
JOB_TYPE_SESSION_KEYS = {
  "fmax_synthesis": "fmax_synthesis_session",
  "custom_freq_synthesis": "custom_freq_synthesis_session",
  "analysis": "analysis_session",
  "analyze": "analysis_session",
  "pnr": "pnr_session",
}


def platform_key():
  """The tool.yml section holding the commands of the current platform."""
  return "windows" if sys.platform == "win32" else "unix"


def get_tool_label(tool):
  """
  Return a human-readable label for a tool. Uses the optional "label" key of
  tool.yml, falling back to the tool name.
  """
  data = load_tool_settings(tool)
  label = data.get("label")
  if isinstance(label, str) and label.strip():
    return label.strip()
  return tool


######################################
# Flows
######################################


def _flow_commands(section):
  """Extract the {job_type_command_key: command} pairs of a platform section."""
  if not isinstance(section, dict):
    return {}
  command_keys = set(JOB_TYPE_COMMAND_KEYS.values())
  return {key: value for key, value in section.items() if key in command_keys}


def _as_command_list(value):
  """A command (or command fragment) as a list of words, or None when empty."""
  if value is None or value == "":
    return None
  if isinstance(value, list):
    parts = [str(item) for item in value if item is not None and str(item) != ""]
    return parts if parts else None
  return [str(value)]


def _flow_steps(section):
  """
  Extract the {job_type_steps_key: [step, ...]} pairs of a platform section.

  A step is a dict with a "name", a "default" flag, and what it runs: either a
  whole "command" (the step is a process of its own) or "args" (the step is a
  fragment of a session, see _flow_sessions). Entries declaring neither are
  ignored, so a malformed declaration never turns into a silently truncated
  pipeline.

  A step marked "default: true" is where a run stops when it is not told where to
  (see get_default_step): a flow can declare every step it knows how to run and
  still stop before the expensive ones by default.
  """
  if not isinstance(section, dict):
    return {}
  steps = {}
  for key in set(JOB_TYPE_STEPS_KEYS.values()):
    declared = section.get(key)
    if not isinstance(declared, list):
      continue
    parsed = []
    for entry in declared:
      if not isinstance(entry, dict):
        continue
      name = entry.get("name")
      command = entry.get("command")
      args = _as_command_list(entry.get("args"))
      if not isinstance(name, str) or name.strip() == "":
        continue
      if command in (None, "") and args is None:
        continue
      parsed.append({
        "name": name.strip(),
        "command": command if command not in (None, "") else None,
        "args": args,
        "default": bool(entry.get("default", False)),
      })
    if parsed:
      steps[key] = parsed
  return steps


def _flow_sessions(section):
  """
  Extract the {job_type_session_key: session} pairs of a platform section.

  A session declares how to open the tool once for a job type:

      custom_freq_synthesis_session:
        command: [vivado, -mode tcl, -log $log_path/synthesis.log]
        begin:   [-source $script_path/setup.tcl]   # optional
        end:     [-source $script_path/exit.tcl]    # optional

  What the steps of a run add to it goes between "begin" and "end", so the
  steps of one run share a single process instead of opening and closing the
  tool once per step.

  Only the keys a section declares are kept, so a flow overriding a session says
  just what it changes and inherits the rest (see _merge_session). A session left
  without a "command" once merged is not runnable and is ignored.
  """
  if not isinstance(section, dict):
    return {}
  sessions = {}
  for key in set(JOB_TYPE_SESSION_KEYS.values()):
    declared = section.get(key)
    if not isinstance(declared, dict):
      continue
    session = {}
    for part in ("command", "begin", "end"):
      if part in declared:
        session[part] = _as_command_list(declared.get(part)) or []
    if session:
      sessions[key] = session
  return sessions


def _job_type_keys():
  """
  The (command key, steps key, session key) triple of every job type, without
  duplicates.
  """
  keys = []
  for job_type, command_key in JOB_TYPE_COMMAND_KEYS.items():
    entry = (command_key, JOB_TYPE_STEPS_KEYS.get(job_type), JOB_TYPE_SESSION_KEYS.get(job_type))
    if entry not in keys:
      keys.append(entry)
  return keys


def _merge_steps(base, override):
  """
  Merge a flow's steps into the ones it inherits, by step name.

  The inherited order is what the tool decided, so it is kept: a step the flow
  redefines is replaced where it already was, and steps the flow adds are
  appended. This is what lets a flow change only how the design is synthesized
  and inherit place & route and bitstream generation unchanged.
  """
  redefined = {step["name"]: step for step in override}
  merged = [redefined.get(step["name"], step) for step in base]
  known = {step["name"] for step in base}
  merged.extend(step for step in override if step["name"] not in known)
  return merged


def _merge_session(base, override):
  """
  Merge a flow's session into the one it inherits, key by key: a flow changing
  only where the log goes, or adding a script every session must source, says
  that much and inherits the rest.
  """
  if base is None:
    return dict(override)
  merged = dict(base)
  merged.update(override)
  return merged


def _inherit_execution(base_commands, base_steps, base_sessions, commands, steps, sessions):
  """
  Resolve what a flow runs for each job type, starting from the default flow's
  declaration (`base_*`) and applying the flow's own (`commands` / `steps` /
  `sessions`).

  A flow that declares nothing for a job type runs the default flow's; one that
  declares a command runs it in one shot even if the default flow is stepped;
  one that declares steps merges them into the inherited ones by name; one that
  declares a session merges it into the inherited one key by key, which is how a
  flow changes what every session of a job type does without touching its steps.
  """
  merged_commands = {}
  merged_steps = {}
  merged_sessions = {}

  for command_key, steps_key, session_key in _job_type_keys():
    if command_key in commands:
      # An explicit one shot command replaces an inherited split into steps.
      merged_commands[command_key] = commands[command_key]
      continue

    if session_key is not None:
      if session_key in sessions:
        merged_sessions[session_key] = _merge_session(base_sessions.get(session_key), sessions[session_key])
      elif session_key in base_sessions:
        merged_sessions[session_key] = dict(base_sessions[session_key])

    if steps_key is not None and steps_key in steps:
      inherited = base_steps.get(steps_key, [])
      merged_steps[steps_key] = _merge_steps(inherited, steps[steps_key])
      continue

    if command_key in base_commands:
      merged_commands[command_key] = base_commands[command_key]
    if steps_key is not None and steps_key in base_steps:
      merged_steps[steps_key] = list(base_steps[steps_key])

  return merged_commands, merged_steps, merged_sessions


def _flow_parameters(spec):
  """The "parameters" a tool.yml section declares, as a dict ({} when none)."""
  declared = spec.get("parameters") if isinstance(spec, dict) else None
  if not isinstance(declared, dict):
    return {}
  return dict((str(name), value) for name, value in declared.items() if str(name).strip() != "")


def parameter_as_text(value):
  """A parameter the way it reads in a command: a list is its words."""
  if value is None:
    return ""
  if isinstance(value, bool):
    return "true" if value else "false"
  if isinstance(value, (list, tuple)):
    return " ".join(parameter_as_text(item) for item in value)
  return str(value)


def substitute_parameters(value, parameters):
  """
  Replace "$<name>" by the value of a parameter in a command, a step or a
  session (recursively). A name only matches as a whole word, so a parameter
  "work" leaves "$work_path" alone.
  """
  import re

  if not parameters:
    return value
  if isinstance(value, str):
    if "$" not in value:
      return value
    # Longest names first: "$shell_args" is not "$shell" followed by "_args".
    for name in sorted(parameters, key=len, reverse=True):
      value = re.sub(r"\$" + re.escape(name) + r"(?![A-Za-z0-9_])", lambda m, n=name: parameter_as_text(parameters[n]), value)
    return value
  if isinstance(value, list):
    return [substitute_parameters(item, parameters) for item in value]
  if isinstance(value, dict):
    return dict((key, substitute_parameters(item, parameters)) for key, item in value.items())
  return value


def _apply_parameters(flow):
  """Substitute a flow's parameters into everything it runs."""
  parameters = flow.get("parameters") or {}
  if not parameters:
    return flow
  for key in ("commands", "steps", "sessions", "tool_test_command"):
    flow[key] = substitute_parameters(flow[key], parameters)
  return flow


def _make_flow(name, label=None, description=None, icon=None, icon_filter=False, commands=None, steps=None, sessions=None, metrics_file=None, tool_test_command=None, is_default=False, parameters=None):
  return {
    "name": name,
    "label": label if isinstance(label, str) and label.strip() else name,
    "description": description if isinstance(description, str) else "",
    "icon": icon if isinstance(icon, str) and icon.strip() else None,
    "icon_filter": bool(icon_filter),
    "commands": commands if commands else {},
    "steps": steps if steps else {},
    "sessions": sessions if sessions else {},
    "metrics_file": metrics_file if isinstance(metrics_file, str) and metrics_file.strip() else None,
    # Unlike the job commands, this one is inherited from the tool: only a flow
    # running a different binary needs to override it.
    "tool_test_command": tool_test_command,
    "is_default": is_default,
    # What the flow tunes rather than runs: the strategy its scripts follow
    # (which compile command, which directives...). Written into the job's
    # settings.tcl, readable with odatix_flow_param, and substituted into the
    # commands as "$<name>".
    "parameters": dict(parameters) if parameters else {},
  }


def list_flows(tool, job_type=None, settings=None):
  """
  Discover the flows of a tool as an ordered dict {flow_name: flow}, the default
  flow first. A flow is a dict with the keys "name", "label", "description",
  "icon", "icon_filter", "commands" (command key -> command), "metrics_file" and "is_default".

  Args:
      tool (str): tool name.
      job_type (str, optional): when given, only the flows able to run this job
          type are returned.
      settings (dict, optional): already loaded tool settings, to avoid
          re-reading tool.yml.
  """
  data = load_tool_settings(tool) if settings is None else settings
  section = platform_key()

  default_name = data.get("default_flow")
  default_name = default_name.strip() if isinstance(default_name, str) and default_name.strip() else DEFAULT_FLOW_NAME

  flows = {}

  # The commands declared directly in the platform section belong to the
  # tool's default flow.
  base_section = data.get(section) if isinstance(data.get(section), dict) else {}
  base_test_command = base_section.get("tool_test_command")
  base_commands = _flow_commands(base_section)
  base_steps = _flow_steps(base_section)
  base_sessions = _flow_sessions(base_section)
  # Parameters declared at the top level are those of the default flow, and
  # every other flow starts from them (merged key by key).
  base_parameters = _flow_parameters(data)
  if base_commands or base_steps:
    flows[default_name] = _make_flow(
      default_name,
      commands=base_commands,
      steps=base_steps,
      sessions=base_sessions,
      metrics_file=data.get("default_metrics_file"),
      tool_test_command=base_test_command,
      is_default=True,
      parameters=base_parameters,
    )

  declared_flows = data.get("flows")
  if isinstance(declared_flows, dict):
    for name, spec in declared_flows.items():
      name = str(name)
      if not isinstance(spec, dict):
        continue
      # A flow name becomes a work directory name: reject the ones that could
      # not round-trip (see tool_work_dirname).
      if not check_flow_name(name):
        continue
      flow_section = spec.get(section) if isinstance(spec.get(section), dict) else {}
      commands = _flow_commands(flow_section)
      steps = _flow_steps(flow_section)
      sessions = _flow_sessions(flow_section)
      # A flow running a different binary declares how to check for it;
      # otherwise the tool's own check applies.
      test_command = flow_section.get("tool_test_command", base_test_command)
      existing = flows.get(name)
      if existing is not None:
        # Metadata (and extra commands) for the tool's default flow.
        existing["label"] = spec.get("label") if isinstance(spec.get("label"), str) and spec.get("label").strip() else existing["label"]
        existing["description"] = spec.get("description") if isinstance(spec.get("description"), str) else existing["description"]
        existing["icon"] = spec.get("icon") if isinstance(spec.get("icon"), str) and spec.get("icon").strip() else existing["icon"]
        if "icon_filter" in spec:
          existing["icon_filter"] = bool(spec.get("icon_filter"))
        existing["commands"], existing["steps"], existing["sessions"] = _inherit_execution(
          existing["commands"], existing["steps"], existing["sessions"], commands, steps, sessions
        )
        if flow_section.get("tool_test_command") is not None:
          existing["tool_test_command"] = flow_section.get("tool_test_command")
        if isinstance(spec.get("metrics_file"), str) and spec.get("metrics_file").strip():
          existing["metrics_file"] = spec.get("metrics_file").strip()
        existing["parameters"].update(_flow_parameters(spec))
      else:
        # A flow changes what the tool's default flow does: it starts from that
        # declaration and overrides only what it says.
        flow_commands, flow_steps, flow_sessions = _inherit_execution(
          base_commands, base_steps, base_sessions, commands, steps, sessions
        )
        flows[name] = _make_flow(
          name,
          label=spec.get("label"),
          description=spec.get("description"),
          icon=spec.get("icon"),
          icon_filter=spec.get("icon_filter", False),
          commands=flow_commands,
          steps=flow_steps,
          sessions=flow_sessions,
          metrics_file=spec.get("metrics_file") or data.get("default_metrics_file"),
          tool_test_command=test_command,
          is_default=(name == default_name),
          parameters=_deep_merge(base_parameters, _flow_parameters(spec)),
        )

  for flow in flows.values():
    _apply_parameters(flow)

  if job_type is not None:
    command_key = JOB_TYPE_COMMAND_KEYS.get(job_type)
    steps_key = JOB_TYPE_STEPS_KEYS.get(job_type)
    flows = {
      name: flow
      for name, flow in flows.items()
      if (command_key is not None and command_key in flow["commands"])
      or (steps_key is not None and steps_key in flow["steps"])
    }

  # The default flow always comes first, the others keep their declaration order.
  return dict(sorted(flows.items(), key=lambda item: 0 if item[1]["is_default"] else 1))


def get_flow_names(tool, job_type=None):
  """Return the names of the flows of a tool, the default one first."""
  return list(list_flows(tool, job_type=job_type).keys())


def get_default_flow(tool, job_type=None):
  """
  Return the name of the flow used when none is requested: the tool's default
  flow when it can run the job type, otherwise the first flow that can. Returns
  None when the tool cannot run the job type at all.
  """
  flows = list_flows(tool, job_type=job_type)
  for name, flow in flows.items():
    if flow["is_default"]:
      return name
  return next(iter(flows), None)


def get_flow(tool, flow=None, job_type=None):
  """
  Resolve a flow of a tool. `flow` may be None (the default flow is used).
  Returns the flow dict, or None when the tool has no such flow (or when the
  flow cannot run the requested job type).
  """
  flows = list_flows(tool, job_type=job_type)
  if flow is None or str(flow).strip() == "":
    name = get_default_flow(tool, job_type=job_type)
    return flows.get(name) if name is not None else None
  return flows.get(str(flow).strip())


def get_flow_parameters(tool, flow=None):
  """
  The parameters of a flow (see "parameters" in list_flows), {} when it sets
  none or does not exist.
  """
  resolved = get_flow(tool, flow=flow)
  return dict(resolved["parameters"]) if resolved is not None else {}


def get_flow_label(tool, flow=None, job_type=None):
  """Human-readable label of a flow, falling back to its name."""
  resolved = get_flow(tool, flow=flow, job_type=job_type)
  if resolved is None:
    return str(flow) if flow else ""
  return resolved["label"]


def get_flow_command(tool, flow=None, job_type="fmax_synthesis"):
  """
  Return the command a tool runs for a job type with a given flow, or None when
  the flow is unknown or does not support the job type.
  """
  resolved = get_flow(tool, flow=flow, job_type=job_type)
  if resolved is None:
    return None
  command_key = JOB_TYPE_COMMAND_KEYS.get(job_type)
  return resolved["commands"].get(command_key) if command_key is not None else None


def resolve_steps(flow, job_type):
  """
  The steps of an already resolved flow for a job type, each one carrying the
  full command it runs on its own, plus the session it belongs to when it is a
  fragment of one.

  A step declaring "args" runs inside the job type's session: its own command is
  the session's ("command" + "begin" + its args + "end"), and consecutive steps
  of a run sharing that session are run by a single process (see
  odatix.components.synthesis_common.build_job_command). A step declaring a
  whole "command" is a process of its own, whether the job type has a session or
  not.

  A step declaring "args" for a job type that has no session cannot be built
  into anything runnable and is dropped.

  Returns None when the flow runs the job type in one shot.
  """
  if flow is None:
    return None
  steps_key = JOB_TYPE_STEPS_KEYS.get(job_type)
  if steps_key is None:
    return None
  steps = flow["steps"].get(steps_key)
  if not steps:
    return None

  session_key = JOB_TYPE_SESSION_KEYS.get(job_type)
  session = flow.get("sessions", {}).get(session_key) if session_key is not None else None
  if session is not None and not session.get("command"):
    # Nothing to open the tool with: not a session anything can run in.
    session = None

  resolved = []
  for step in steps:
    item = dict(step)
    if item.get("command") is None:
      if session is None:
        continue
      item["session"] = session
      item["command"] = (
        list(session["command"]) + list(session.get("begin") or []) + list(item["args"]) + list(session.get("end") or [])
      )
    else:
      # A step declaring its whole command opens a session of its own, even
      # when the job type declares one.
      item["session"] = None
    resolved.append(item)

  return resolved if resolved else None


def get_flow_steps(tool, flow=None, job_type="fmax_synthesis"):
  """
  Ordered steps a tool runs for a job type with a given flow, as a list of
  {"name", "command", "args", "session", "default"} dicts, or None when the flow
  runs the job type in one shot (a plain "<job_type>_command").

  A job can be resumed from the first step that has not completed yet (see
  odatix.lib.job_steps). Steps sharing a session and run together are run by a
  single process; the others are run one process each.
  """
  return resolve_steps(get_flow(tool, flow=flow, job_type=job_type), job_type)


def get_flow_session(tool, flow=None, job_type="fmax_synthesis"):
  """
  How a tool opens a session for a job type with a given flow, as a
  {"command", "begin", "end"} dict, or None when the flow declares none.
  """
  resolved = get_flow(tool, flow=flow, job_type=job_type)
  if resolved is None:
    return None
  session_key = JOB_TYPE_SESSION_KEYS.get(job_type)
  return resolved.get("sessions", {}).get(session_key) if session_key is not None else None


def get_flow_step_names(tool, flow=None, job_type="fmax_synthesis"):
  """Names of the steps of a flow, in order, or [] when it has none."""
  steps = get_flow_steps(tool, flow=flow, job_type=job_type)
  return [step["name"] for step in steps] if steps else []


def get_default_step(tool, flow=None, job_type="fmax_synthesis"):
  """
  Name of the step a run stops at when it is not told where to, i.e. the last
  step the flow marks with "default: true", or None when it marks none (the
  whole flow runs).

  Going all the way is not always what a flow is usually for: a flow declaring
  place & route and bitstream generation can still stop after synthesis by
  default, and leave the rest for the runs worth it. The last marked step wins,
  so a flow inheriting steps and marking a later one moves the stopping point
  instead of ending up with two.
  """
  steps = get_flow_steps(tool, flow=flow, job_type=job_type)
  if not steps:
    return None
  default = [step["name"] for step in steps if step.get("default")]
  return default[-1] if default else None


def flow_supports(tool, flow, job_type):
  """True if the given flow of the tool can run the job type."""
  return get_flow(tool, flow=flow, job_type=job_type) is not None


def tool_supports(tool, job_type):
  """
  Return True if at least one flow of the tool can run the given job type (one
  of the keys of JOB_TYPE_COMMAND_KEYS).
  """
  return len(list_flows(tool, job_type=job_type)) > 0


def tools_supporting(job_type):
  """Return the list of discovered tool names that support the given job type."""
  return [tool for tool in list_tools() if tool_supports(tool, job_type)]


######################################
# Work directory naming
######################################


def tool_work_dirname(tool, flow=None, job_type=None):
  """
  Name of the work sub-directory holding the jobs of a tool run with a given
  flow: "<tool>" for the tool's default flow, "<tool>@<flow>" otherwise.

  Two flows of the same tool are alternatives meant to be compared, so they get
  separate work directories. The default flow keeps the bare tool name, so work
  directories produced before flows existed keep resolving.
  """
  flow = str(flow).strip() if flow is not None else ""
  if flow == "" or flow == get_default_flow(tool, job_type=job_type):
    return str(tool)
  return str(tool) + WORK_DIR_FLOW_SEPARATOR + flow


def split_tool_work_dirname(dirname):
  """
  Inverse of tool_work_dirname: split a work sub-directory name into its
  (tool, flow) pair. The flow is None for a directory holding the tool's
  default flow ("vivado" -> ("vivado", None)).
  """
  dirname = str(dirname)
  if WORK_DIR_FLOW_SEPARATOR not in dirname:
    return dirname, None
  tool, _, flow = dirname.partition(WORK_DIR_FLOW_SEPARATOR)
  return tool, (flow or None)


def check_flow_name(flow):
  """
  True if a flow name can be used in a work directory name. The separator is
  reserved, and a flow name is a single path segment.
  """
  flow = str(flow)
  return (
    flow != ""
    and WORK_DIR_FLOW_SEPARATOR not in flow
    and "/" not in flow
    and "\\" not in flow
    and flow not in (".", "..")
  )


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


######################################
# Installation
######################################

#: How the commands of a tool name the directory it is installed in.
INSTALL_PATH_VARIABLE = "$tool_install_path"


def install_path_hint(tool):
  """
  What "tool_install_path" must point to for a tool, in a few words: the
  "tool_install_path_hint" of its tool.yml ("the directory holding qinit.sh"),
  or "" when the tool does not say.
  """
  hint = load_tool_settings(tool).get("tool_install_path_hint")
  return hint.strip() if isinstance(hint, str) else ""


def _mentions(value, text):
  """Whether a string somewhere in a tool.yml value contains the text."""
  if isinstance(value, str):
    return text in value
  if isinstance(value, dict):
    return any(_mentions(item, text) for item in value.values())
  if isinstance(value, (list, tuple)):
    return any(_mentions(item, text) for item in value)
  return False


def reads_install_path(tool):
  """
  Whether "tool_install_path" means anything to a tool.

  A built-in tool reads it when one of its commands passes it on
  ("$tool_install_path", as Quartus and LibreLane do); the others (Vivado,
  Design Compiler, Genus...) are found on the PATH only, so a path given to
  them would be silently ignored. A tool of the workspace always may read it:
  its own scripts find it in the settings.yml of their job.
  """
  if get_builtin_tool_dir(tool) is None:
    return True
  settings = load_tool_settings(tool)
  return bool(install_path_hint(tool)) or _mentions(settings, INSTALL_PATH_VARIABLE)


def tool_test_command(tool, tool_install_path="", flow=None):
  """
  The command checking that a tool can be launched ("tool_test_command" of its
  flow), its variables replaced the way a run replaces them, or None when the
  tool declares none.
  """
  from odatix.lib.settings import OdatixSettings
  from odatix.lib.variables import Variables, replace_variables

  resolved = get_flow(tool, flow=flow)
  command = resolved.get("tool_test_command") if resolved is not None else None
  if command is None:
    command = (load_tool_settings(tool).get(platform_key()) or {}).get("tool_test_command")
  if not command:
    return None
  if isinstance(command, list):
    command = " ".join(map(str, command))
  install_path = str(tool_install_path or "").strip()
  if install_path:
    install_path = os.path.realpath(os.path.expanduser(install_path))
  variables = Variables(
    tool_install_path=install_path,
    odatix_path=OdatixSettings.odatix_path,
    odatix_eda_tools_path=OdatixSettings.odatix_eda_tools_path,
    tool_path=get_tool_dir(tool),
  )
  return replace_variables(str(command), variables)
