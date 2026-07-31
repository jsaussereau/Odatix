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

import io
import os
import re
import shutil
import copy
import yaml
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from datetime import datetime
from itertools import product
from functools import reduce
from natsort import natsorted
import operator

import odatix.components.motd as motd
import odatix.lib.hard_settings as hard_settings
from odatix.lib.utils import copytree
from typing import Optional


######################################
# Architectures and Simulations
######################################

def get_instances(path: str) -> list:
    """
    Get the list of architectures or simulations.
    """
    if not os.path.exists(path):
        return []
    return natsorted([
        d for d in os.listdir(path)
        if os.path.isdir(os.path.join(path, d))
    ])

def get_simulations(path: str) -> list:
    """
    Get the list of simulations.
    """
    return get_instances(path)

def get_architectures(path: str) -> list:
    """
    Get the list of architectures.
    """
    return get_instances(path)

def instance_exists(path, name) -> bool:
    """
    Check if a specific architecture or simulation exists.
    """
    path = os.path.join(path, name)
    return os.path.isdir(path)

def architecture_exists(path, name) -> bool:
    """
    Check if a specific architecture exists.
    """
    return instance_exists(path, name)

def simulation_exists(path, name) -> bool:
    """
    Check if a specific simulation exists.
    """
    return instance_exists(path, name)

def duplicate_instance(path, source_name, target_name) -> None:
    """
    Duplicate an architecture or simulation.
    """
    source_path = os.path.join(path, source_name)
    target_path = os.path.join(path, target_name)
    if not os.path.isdir(source_path):
        raise ValueError(f"Source instance '{source_name}' does not exist.")
    if os.path.exists(target_path):
        raise ValueError(f"Target instance '{target_name}' already exists.")
    copytree(source_path, target_path)

def delete_instance(path, name) -> None:
    """
    Delete an architecture or simulation.
    """
    path = os.path.join(path, name)
    if os.path.isdir(path):
        shutil.rmtree(path)
    else:
        os.remove(path)

def rename_instance(path, old_name, new_name) -> None:
    """
    Rename an architecture or simulation.
    """
    old_path = os.path.join(path, old_name)
    new_path = os.path.join(path, new_name)
    if not os.path.isdir(old_path):
        return
    if os.path.exists(new_path):
        return
    shutil.move(old_path, new_path)

def rename_architecture(path, old_name, new_name) -> None:
    """
    Rename an architecture.
    """
    rename_instance(path, old_name, new_name)

def rename_simulation(path, old_name, new_name) -> None:
    """
    Rename a simulation.
    """
    rename_instance(path, old_name, new_name)

def create_instance(path, name) -> None:
    """
    Create a new architecture or simulation.
    """
    instance_path = os.path.join(path, name)
    os.makedirs(instance_path, exist_ok=True)

def create_architecture(path, name) -> None:
    """
    Create a new architecture.
    """
    create_instance(path, name)

def create_simulation(path, name) -> None:
    """
    Create a new simulation.
    """
    create_instance(path, name)


######################################
# Simulation settings and metrics
######################################
#
# A simulation directory holds a "_settings.yml" (how the architecture
# parameters are replaced in the testbench, plus the optional workflow-style
# "tasks" and "progress" keys) and an optional "_metrics.yml" (what to extract
# from each run at export time, same format as a workflow's, see
# odatix.components.export_simulation_results).

SIMULATION_METRICS_FILENAME = "_metrics.yml"

def get_simulation_path(sim_path, sim_name) -> str:
    """
    Get the path of a specific simulation.
    """
    return os.path.join(sim_path, sim_name)

def get_simulation_settings_path(sim_path, sim_name) -> str:
    """
    Get the settings file path of a specific simulation.
    """
    return os.path.join(get_simulation_path(sim_path, sim_name), hard_settings.sim_settings_filename)

def load_simulation_settings(sim_path, sim_name) -> dict:
    """
    Load simulation settings.
    """
    return load_yaml_file(get_simulation_settings_path(sim_path, sim_name), default={})

def save_simulation_settings(sim_path, sim_name, settings) -> None:
    """
    Save simulation settings, preserving comments and any key the editor does
    not know about.
    """
    path = get_simulation_settings_path(sim_path, sim_name)
    yaml_obj = YAML()

    if os.path.exists(path):
        with open(path, "r") as f:
            data = yaml_obj.load(f)
        if data is None:
            data = CommentedMap()
    else:
        data = CommentedMap()

    for key, value in settings.items():
        data[key] = value

    save_yaml_file(path, data, yaml_obj=yaml_obj)

def get_simulation_metrics_path(sim_path, sim_name) -> str:
    """
    Get the metrics definition file path of a specific simulation.
    """
    return os.path.join(get_simulation_path(sim_path, sim_name), SIMULATION_METRICS_FILENAME)

def load_simulation_metrics(sim_path, sim_name) -> tuple:
    """
    Load the metrics definition of a simulation.

    Returns:
        tuple: (metrics, metadata), each a name -> definition dict. Both are
        empty when the file is missing or unparsable.
    """
    path = get_simulation_metrics_path(sim_path, sim_name)
    data = load_yaml_file(path, default={})
    if not isinstance(data, dict):
        return {}, {}

    if "metrics" in data:
        metrics = data.get("metrics") or {}
        metadata = data.get("metadata") or {}
    else:
        metrics = data
        metadata = {}

    if not isinstance(metrics, dict):
        metrics = {}
    if not isinstance(metadata, dict):
        metadata = {}
    return metrics, metadata

def save_simulation_metrics(sim_path, sim_name, metrics, metadata=None) -> None:
    """
    Save the metrics definition of a simulation, preserving comments and any
    other key of the file (same layout as workflow metrics).
    """
    path = get_simulation_metrics_path(sim_path, sim_name)
    yaml_obj = YAML()

    if os.path.exists(path):
        with open(path, "r") as f:
            data = yaml_obj.load(f)
        if data is None:
            data = CommentedMap()
    else:
        data = CommentedMap()

    # Migrate the legacy top-level layout (metrics defined at the root) to the
    # explicit "metrics" key on write.
    if "metrics" not in data:
        for key in list(data.keys()):
            if key != "metadata":
                del data[key]

    data["metrics"] = metrics if isinstance(metrics, dict) else {}
    if metadata:
        data["metadata"] = metadata
    else:
        data.pop("metadata", None)

    save_yaml_file(path, data, yaml_obj=yaml_obj)

def load_simulation_selection(path: str) -> dict:
    """
    Read the "simulations" key of a simulation settings file into a
    simulation name -> list of architecture entries mapping.

    The file holds it as a list of single-key mappings, which is what the
    "odatix sim" command reads:

        simulations:
          - TB_Example:
            - Example_Counter_vhdl/04bits
    """
    data = load_yaml_file(path, default={})
    if not isinstance(data, dict):
        return {}

    selection = {}
    simulations = data.get("simulations", [])
    if isinstance(simulations, dict):
        simulations = [{name: entries} for name, entries in simulations.items()]
    if not isinstance(simulations, (list, tuple)):
        return {}

    for item in simulations:
        if not isinstance(item, dict):
            continue
        for name, entries in item.items():
            if entries is None:
                entries = []
            if isinstance(entries, str):
                entries = [entries]
            if not isinstance(entries, (list, tuple)):
                continue
            selection.setdefault(str(name), []).extend([str(entry) for entry in entries if entry is not None])
    return selection

def create_simulation_selection_list(selection: dict) -> list:
    """
    Build the "simulations" value of a simulation settings file from a
    simulation name -> architecture entries mapping (the inverse of
    load_simulation_selection).
    """
    simulations = CommentedSeq()
    for name, entries in (selection or {}).items():
        if not name:
            continue
        entry_list = CommentedSeq([str(entry) for entry in (entries or []) if entry])
        simulations.append(CommentedMap({str(name): entry_list}))
    return simulations


######################################
# Workflows
######################################

def get_workflows(path: str) -> list:
    """
    Get the list of workflows.
    """
    return get_instances(path)

def workflow_exists(path, name) -> bool:
    """
    Check if a specific workflow exists.
    """
    return instance_exists(path, name)

def duplicate_workflow(path, source_name, target_name) -> None:
    """
    Duplicate a workflow.
    """
    duplicate_instance(path, source_name, target_name)

def delete_workflow(path, name) -> None:
    """
    Delete a workflow.
    """
    delete_instance(path, name)

def rename_workflow(path, old_name, new_name) -> None:
    """
    Rename a workflow.
    """
    rename_instance(path, old_name, new_name)

def create_workflow(path, name) -> None:
    """
    Create a new workflow.
    """
    create_instance(path, name)

def get_workflow_path(workflow_path, workflow_name) -> str:
    """
    Get the path of a specific workflow.
    """
    return os.path.join(workflow_path, workflow_name)

def get_workflow_settings_path(workflow_path, workflow_name, domain=hard_settings.main_parameter_domain) -> str:
    """
    Get the settings file path of a specific workflow (or one of its parameter domains).
    """
    return os.path.join(get_arch_domain_path(workflow_path, workflow_name, domain), hard_settings.param_settings_filename)

def load_workflow_settings(workflow_path, workflow_name, domain=hard_settings.main_parameter_domain) -> dict:
    """
    Load workflow settings.
    """
    path = get_workflow_settings_path(workflow_path, workflow_name, domain)
    return load_yaml_file(path, default={})

def update_workflow_settings(workflow_path, workflow_name, settings_to_update, domain=hard_settings.main_parameter_domain) -> None:
    """
    Update workflow settings while preserving comments and untouched keys.
    """
    path = get_workflow_settings_path(workflow_path, workflow_name, domain)
    yaml_obj = YAML()

    if os.path.exists(path):
        with open(path, "r") as f:
            settings = yaml_obj.load(f)
            if settings is None:
                settings = CommentedMap()
    else:
        settings = CommentedMap()

    for key, value in settings_to_update.items():
        if key == "generate_configurations_settings" and isinstance(value, dict):
            value = copy.deepcopy(value)
            _compact_list_variables_in_config_settings(value)
        settings[key] = value

    save_yaml_file(path, settings, yaml_obj=yaml_obj)

def save_workflow_settings(workflow_path, workflow_name, settings, domain=hard_settings.main_parameter_domain) -> None:
    """
    Save workflow settings.
    """
    update_workflow_settings(workflow_path, workflow_name, settings, domain)

######################################
# Workflow Metrics
######################################
#
# The metrics definition file ("_metrics.yml") lives in the workflow definition
# directory and describes how workflow results are extracted from each run at
# export time (see odatix.components.export_workflow_results). It can hold the
# metric definitions directly at top level, or under a "metrics" key with an
# optional sibling "metadata" mapping (extra meta dimensions).

WORKFLOW_METRICS_FILENAME = "_metrics.yml"

def get_workflow_metrics_path(workflow_path, workflow_name) -> str:
    """
    Get the metrics definition file path of a specific workflow.
    """
    return os.path.join(get_workflow_path(workflow_path, workflow_name), WORKFLOW_METRICS_FILENAME)

def load_workflow_metrics(workflow_path, workflow_name) -> tuple:
    """
    Load the metrics definition of a workflow.

    Returns:
        tuple: (metrics, metadata), each a name -> definition dict. Both are
        empty when the file is missing or unparsable.
    """
    path = get_workflow_metrics_path(workflow_path, workflow_name)
    data = load_yaml_file(path, default={})
    if not isinstance(data, dict):
        return {}, {}

    if "metrics" in data:
        metrics = data.get("metrics") or {}
        metadata = data.get("metadata") or {}
    else:
        metrics = data
        metadata = {}

    if not isinstance(metrics, dict):
        metrics = {}
    if not isinstance(metadata, dict):
        metadata = {}
    return metrics, metadata

def save_workflow_metrics(workflow_path, workflow_name, metrics, metadata=None) -> None:
    """
    Save the metrics definition of a workflow, preserving comments and any other
    key of the file. Metrics are always written under the "metrics" key (with an
    optional sibling "metadata" mapping) so both dimensions round-trip cleanly.
    """
    path = get_workflow_metrics_path(workflow_path, workflow_name)
    yaml_obj = YAML()

    if os.path.exists(path):
        with open(path, "r") as f:
            data = yaml_obj.load(f)
        if data is None:
            data = CommentedMap()
    else:
        data = CommentedMap()

    # If the file used the legacy top-level layout (metrics defined directly at
    # the root), migrate it to the explicit "metrics" key on write.
    if "metrics" not in data:
        for key in list(data.keys()):
            if key != "metadata":
                del data[key]

    data["metrics"] = metrics if isinstance(metrics, dict) else {}
    if metadata:
        data["metadata"] = metadata
    else:
        data.pop("metadata", None)

    save_yaml_file(path, data, yaml_obj=yaml_obj)

######################################
# EDA Tools
######################################
#
# A workspace EDA tool is a directory under the workspace tools directory
# (odatix_userconfig/tools by default) containing a "tool.yml" file (and usually
# a "metrics.yml"). These helpers manage those workspace tool directories from
# the GUI (list / create / duplicate / delete / rename, and read/write of the
# tool.yml and metrics.yml files). Built-in tools shipped with Odatix are handled
# read-only through odatix.lib.eda_tools; only workspace tools are edited here.

TOOL_SETTINGS_FILENAME = hard_settings.tool_settings_filename  # "tool.yml"
TOOL_METRICS_FILENAME = "metrics.yml"

# The platform sections of a tool.yml, in render order.
TOOL_PLATFORM_KEYS = ("unix", "windows")

# The job types a flow declares a command (or steps) for, in render order. Only
# the ones in TOOL_STEPPED_JOB_TYPES can be split into resumable steps: checking
# that the tool is installed is a single command by nature.
TOOL_JOB_TYPES = ("tool_test", "fmax_synthesis", "custom_freq_synthesis", "analysis")
TOOL_STEPPED_JOB_TYPES = ("fmax_synthesis", "custom_freq_synthesis", "analysis")
TOOL_COMMAND_KEYS = tuple(f"{job_type}_command" for job_type in TOOL_JOB_TYPES)

# The metric sections of a tool metrics.yml, in render order, with the tool.yml
# key each is stored under (see odatix.components.export_results.extract_metrics).
TOOL_METRIC_SECTIONS = [
    ("fmax_synthesis_metrics", "Fmax synthesis metrics"),
    ("custom_freq_synthesis_metrics", "Custom frequency synthesis metrics"),
    ("metrics", "Common metrics"),
]

# Settings of a built-in tool.yml the workspace may override, i.e. everything
# but its flows: the built-in flows and their commands (declared in the top level
# "unix"/"windows" sections, and pointed at by "default_flow") belong to Odatix.
TOOL_OVERRIDABLE_KEYS = (
    "label", "description", "icon", "process_group",
    "report_path", "target_file", "default_metrics_file",
)

def get_tools(path: str) -> list:
    """
    Get the list of workspace tools (directories containing a tool.yml).

    Overlays on built-in tools (see is_builtin_overlay) are left out: they are
    not tools of their own, they are what the workspace adds to a built-in tool,
    and are listed with it.
    """
    if not path or not os.path.isdir(path):
        return []
    tools = [
        d for d in os.listdir(path)
        if not d.startswith("_") and not d.startswith(".")
        and os.path.isfile(os.path.join(path, d, TOOL_SETTINGS_FILENAME))
        and not is_builtin_overlay(path, d)
    ]
    return natsorted(tools)

def get_builtin_tool_dir(name) -> str:
    """
    Directory of the built-in tool of that name, or None when there is none.
    """
    from odatix.lib.settings import OdatixSettings

    candidate = os.path.join(OdatixSettings.odatix_eda_tools_path, name)
    return candidate if os.path.isfile(os.path.join(candidate, TOOL_SETTINGS_FILENAME)) else None

def builtin_tool_exists(name) -> bool:
    """True when a built-in tool of that name is shipped with Odatix."""
    return bool(name) and get_builtin_tool_dir(name) is not None

def is_builtin_overlay(tools_path, name) -> bool:
    """
    True when `name` is a built-in tool: whatever the workspace holds for it is
    an overlay on the built-in definition, never a tool of its own. Odatix owns
    the built-in flows and their commands; the workspace can add flows of its own
    and override the rest of the settings (see save_tool_overlay). Odatix merges
    the two at run time (see odatix.lib.eda_tools.load_tool_settings).

    `tools_path` is unused: a built-in tool stays a built-in tool whatever the
    workspace says about it. It is kept so callers read as the other helpers do.
    """
    return builtin_tool_exists(name)

def load_builtin_tool_settings(name) -> dict:
    """
    Load the tool.yml shipped with Odatix for that tool, or {} when there is no
    built-in tool of that name.
    """
    tool_dir = get_builtin_tool_dir(name)
    if tool_dir is None:
        return {}
    data = load_yaml_file(os.path.join(tool_dir, TOOL_SETTINGS_FILENAME), default={})
    return data if isinstance(data, dict) else {}

def load_overlaid_tool_settings(tools_path, name) -> dict:
    """
    Load a built-in tool.yml with the workspace overlay applied on top, the way
    odatix resolves it at run time: what the overlay says about the built-in
    flows is dropped, so the editor shows what actually runs.
    """
    import odatix.lib.eda_tools as eda_tools

    builtin = load_builtin_tool_settings(name)
    overlay = eda_tools.strip_builtin_overrides(
        builtin, load_tool_settings(tools_path, name), tool=name, source=get_tool_settings_path(tools_path, name)
    )
    return eda_tools._deep_merge(builtin, overlay)

def save_tool_overlay(tools_path, name, overrides, flows) -> None:
    """
    Write the workspace overlay of a built-in tool: the flows it adds, and the
    settings it overrides. Nothing of the built-in flows is written: their
    commands stay owned by Odatix.

    `overrides` holds only what actually differs from the built-in definition
    (TOOL_OVERRIDABLE_KEYS and "format"), so a setting reset back to what Odatix
    says simply disappears from the file instead of being frozen into it. Values
    are written as given, empty lists included: an empty marker list is how the
    overlay says a built-in one is cleared.
    """
    tool_dir = os.path.join(tools_path, name)
    path = os.path.join(tool_dir, TOOL_SETTINGS_FILENAME)

    named_flows = [
        flow for flow in flows or []
        if isinstance(flow, dict) and str(flow.get("name", "")).strip() != ""
    ]
    overrides = overrides if isinstance(overrides, dict) else {}

    data = CommentedMap()

    for key in TOOL_OVERRIDABLE_KEYS:
        if key not in overrides:
            continue
        value = overrides.get(key)
        data[key] = bool(value) if key == "process_group" else ("" if value is None else str(value))

    fmt = overrides.get("format") if isinstance(overrides.get("format"), dict) else {}
    fmt_map = CommentedMap()
    for section_key in ("logs", "tags"):
        section = fmt.get(section_key)
        if isinstance(section, dict) and len(section) > 0:
            section_map = CommentedMap()
            for entry_key, markers in section.items():
                section_map[str(entry_key)] = _as_flow_seq(_as_command_list(markers))
            fmt_map[section_key] = section_map
    if "replace" in fmt:
        replace_seq = CommentedSeq()
        for entry in fmt.get("replace") or []:
            if not isinstance(entry, dict):
                continue
            item = CommentedMap()
            for pattern, repl in entry.items():
                if str(pattern).strip() != "":
                    item[str(pattern)] = "" if repl is None else str(repl)
            if len(item) > 0:
                replace_seq.append(item)
        fmt_map["replace"] = replace_seq
    if len(fmt_map) > 0:
        data["format"] = fmt_map

    if named_flows:
        flows_map = CommentedMap()
        for flow in named_flows:
            flow_name = str(flow.get("name", "")).strip()
            entry = CommentedMap()
            for key in ("label", "description", "icon", "metrics_file"):
                value = flow.get(key)
                if value is not None and str(value).strip() != "":
                    entry[key] = str(value)
            for platform_key in TOOL_PLATFORM_KEYS:
                section = _emit_platform_section(flow.get("platforms", {}).get(platform_key, {}))
                if len(section) > 0:
                    entry[platform_key] = section
            flows_map[flow_name] = entry
        data["flows"] = flows_map

    if len(data) == 0:
        # Nothing left of its own: drop the overlay rather than leave an empty
        # one behind, so the tool goes back to being a plain built-in.
        if os.path.isfile(path):
            os.remove(path)
        if os.path.isdir(tool_dir) and not os.listdir(tool_dir):
            os.rmdir(tool_dir)
        return

    os.makedirs(tool_dir, exist_ok=True)

    data.yaml_set_start_comment(
f"""##############################################
# Your changes to the built-in {name} tool
##############################################

# This file was generated by Odatix GUI {motd.read_version()} on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}.
# It is merged over the {name} tool shipped with Odatix: it holds the flows you
# added to it and the settings you overrode, everything else (the commands of
# {name}'s own flows) still comes from the built-in definition. You can still
# modify manually this file as needed.
"""
    )

    save_yaml_file(path, data, yaml_obj=YAML())

def tool_exists(path, name) -> bool:
    """
    Check if a specific workspace tool exists.
    """
    return bool(name) and os.path.isfile(os.path.join(path, name, TOOL_SETTINGS_FILENAME))

def create_tool(path, name) -> None:
    """
    Create a new workspace tool directory with a minimal tool.yml.
    """
    tool_dir = os.path.join(path, name)
    os.makedirs(tool_dir, exist_ok=True)
    settings_path = os.path.join(tool_dir, TOOL_SETTINGS_FILENAME)
    if not os.path.isfile(settings_path):
        save_tool_settings(path, name, {
            "label": name,
            "process_group": True,
            "default_metrics_file": "$tool_path/metrics.yml",
        })

def duplicate_tool(path, source_name, target_name) -> None:
    """
    Duplicate a workspace tool directory.
    """
    source_path = os.path.join(path, source_name)
    target_path = os.path.join(path, target_name)
    if not os.path.isdir(source_path):
        raise ValueError(f"Source tool '{source_name}' does not exist.")
    if os.path.exists(target_path):
        raise ValueError(f"Target tool '{target_name}' already exists.")
    copytree(source_path, target_path)

def duplicate_builtin_tool(builtin_dir, tools_path, target_name) -> None:
    """
    Copy a built-in tool directory into the workspace tools directory so it can
    be edited. `builtin_dir` is the resolved source directory (from
    odatix.lib.eda_tools.get_tool_dir).
    """
    target_path = os.path.join(tools_path, target_name)
    if not builtin_dir or not os.path.isdir(builtin_dir):
        raise ValueError("Built-in tool directory does not exist.")
    if os.path.exists(target_path):
        raise ValueError(f"Target tool '{target_name}' already exists.")
    os.makedirs(tools_path, exist_ok=True)
    copytree(builtin_dir, target_path)

def delete_tool(path, name) -> None:
    """
    Delete a workspace tool directory.
    """
    tool_dir = os.path.join(path, name)
    if os.path.isdir(tool_dir):
        shutil.rmtree(tool_dir)

def rename_tool(path, old_name, new_name) -> None:
    """
    Rename a workspace tool directory.
    """
    old_path = os.path.join(path, old_name)
    new_path = os.path.join(path, new_name)
    if not os.path.isdir(old_path):
        return
    if os.path.exists(new_path):
        return
    shutil.move(old_path, new_path)

def get_tool_settings_path(tools_path, name) -> str:
    """
    Get the tool.yml path of a specific workspace tool.
    """
    return os.path.join(tools_path, name, TOOL_SETTINGS_FILENAME)

def load_tool_settings(tools_path, name) -> dict:
    """
    Load a workspace tool's tool.yml. YAML anchors/aliases used in the built-in
    tools are resolved on load (safe_load), so commands come back as plain lists;
    the editor re-emits a flat, anchor-free tool.yml on save.
    """
    path = get_tool_settings_path(tools_path, name)
    data = load_yaml_file(path, default={})
    return data if isinstance(data, dict) else {}

def save_tool_settings(tools_path, name, settings) -> None:
    """
    Write a workspace tool's tool.yml from a structured settings dict. The file
    is rewritten from scratch (no comment preservation) since the graphical
    editor owns the whole document; a header comment is added.
    """
    path = get_tool_settings_path(tools_path, name)
    yaml_obj = YAML()

    data = CommentedMap()
    data.yaml_set_start_comment(
f"""##############################################
# Settings for {name}
##############################################

# This file was generated by Odatix GUI {motd.read_version()} on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}.
# You can still modify manually this file as needed.
"""
    )

    def _clean_str(value):
        return "" if value is None else str(value)

    # Display metadata
    for key in ("label", "description", "icon"):
        val = settings.get(key)
        if val is not None and str(val).strip() != "":
            data[key] = str(val)

    # Behaviour
    if "process_group" in settings and settings.get("process_group") is not None:
        data["process_group"] = bool(settings.get("process_group"))
    report_path = settings.get("report_path")
    if report_path is not None and str(report_path).strip() != "":
        data["report_path"] = str(report_path)
    target_file = settings.get("target_file")
    if target_file is not None and str(target_file).strip() != "":
        data["target_file"] = str(target_file)
    default_metrics_file = settings.get("default_metrics_file")
    if default_metrics_file is not None and str(default_metrics_file).strip() != "":
        data["default_metrics_file"] = str(default_metrics_file)

    # Flows, or, for a settings dict predating them, plain platform sections.
    #
    # The commands of the default flow are the ones declared directly in the
    # "unix"/"windows" sections (see odatix.lib.eda_tools), so they are written
    # there; every flow, the default one included, gets an entry in "flows"
    # holding its metadata and, for the others, what it overrides.
    flows = settings.get("flows")
    if isinstance(flows, list) and flows:
        named = [f for f in flows if isinstance(f, dict) and str(f.get("name", "")).strip() != ""]
        default_flow = next((f for f in named if f.get("is_default")), next(iter(named), None))

        if default_flow is not None:
            data["default_flow"] = str(default_flow.get("name")).strip()
            for platform_key in TOOL_PLATFORM_KEYS:
                section = _emit_platform_section(default_flow.get("platforms", {}).get(platform_key, {}))
                if len(section) > 0:
                    data[platform_key] = section

        flows_map = CommentedMap()
        for flow in flows:
            if not isinstance(flow, dict):
                continue
            name = str(flow.get("name", "")).strip()
            if name == "":
                continue
            entry = CommentedMap()
            for key in ("label", "description", "icon", "metrics_file"):
                value = flow.get(key)
                if value is not None and str(value).strip() != "":
                    entry[key] = str(value)
            if flow is not default_flow:
                for platform_key in TOOL_PLATFORM_KEYS:
                    section = _emit_platform_section(flow.get("platforms", {}).get(platform_key, {}))
                    if len(section) > 0:
                        entry[platform_key] = section
            flows_map[name] = entry
        if len(flows_map) > 0:
            data["flows"] = flows_map
    else:
        platforms = settings.get("platforms", {})
        if isinstance(platforms, dict):
            for platform_key in TOOL_PLATFORM_KEYS:
                platform = platforms.get(platform_key, {})
                if not isinstance(platform, dict):
                    continue
                section = CommentedMap()
                for cmd_key in TOOL_COMMAND_KEYS:
                    commands = _as_command_list(platform.get(cmd_key))
                    if commands:
                        section[cmd_key] = _as_flow_seq(commands)
                if len(section) > 0:
                    data[platform_key] = section

    # Log formatting section
    fmt = settings.get("format", {})
    if isinstance(fmt, dict):
        fmt_map = CommentedMap()

        logs = fmt.get("logs", {})
        if isinstance(logs, dict):
            logs_map = CommentedMap()
            for level, tags in logs.items():
                if isinstance(tags, str):
                    tags = [t.strip() for t in tags.split(",") if t.strip()]
                if isinstance(tags, (list, tuple)):
                    tags = [str(t) for t in tags if str(t).strip() != ""]
                    if tags:
                        logs_map[level] = _as_flow_seq(tags)
            if len(logs_map) > 0:
                fmt_map["logs"] = logs_map

        tags = fmt.get("tags", {})
        if isinstance(tags, dict):
            tags_map = CommentedMap()
            for tag_name, markers in tags.items():
                if isinstance(markers, str):
                    markers = [m.strip() for m in markers.split(",") if m.strip()]
                if isinstance(markers, (list, tuple)):
                    markers = [str(m) for m in markers if str(m).strip() != ""]
                    if markers:
                        tags_map[tag_name] = _as_flow_seq(markers)
            if len(tags_map) > 0:
                fmt_map["tags"] = tags_map

        replace = fmt.get("replace", [])
        if isinstance(replace, (list, tuple)):
            replace_seq = CommentedSeq()
            for entry in replace:
                if isinstance(entry, dict) and entry:
                    item = CommentedMap()
                    for pattern, repl in entry.items():
                        if str(pattern).strip() != "":
                            item[str(pattern)] = _clean_str(repl)
                    if len(item) > 0:
                        replace_seq.append(item)
            if len(replace_seq) > 0:
                fmt_map["replace"] = replace_seq

        if len(fmt_map) > 0:
            data["format"] = fmt_map

    save_yaml_file(path, data, yaml_obj=yaml_obj)

def _as_flow_seq(values):
    """Return a ruamel sequence rendered on its own block lines (default)."""
    seq = CommentedSeq(values)
    return seq

def _as_command_list(commands):
    """Normalize a command (list, or text with one token per line) to a list."""
    if isinstance(commands, str):
        commands = [line.strip() for line in commands.splitlines() if line.strip()]
    if isinstance(commands, (list, tuple)):
        return [str(c) for c in commands if str(c).strip() != ""]
    return []

def _emit_platform_section(jobs) -> CommentedMap:
    """
    Build the "unix"/"windows" section of a flow from its {job_type: spec} dict,
    where a spec is {"mode": "inherit"|"command"|"steps", "command", "steps"}.
    A job type left on "inherit" declares nothing, so the flow runs whatever it
    inherits from the tool's default flow (see odatix.lib.eda_tools).
    """
    section = CommentedMap()
    if not isinstance(jobs, dict):
        return section
    for job_type in TOOL_JOB_TYPES:
        spec = jobs.get(job_type)
        if not isinstance(spec, dict):
            continue
        mode = spec.get("mode", "inherit")
        if mode == "command":
            commands = _as_command_list(spec.get("command"))
            if commands:
                section[f"{job_type}_command"] = _as_flow_seq(commands)
        elif mode == "steps" and job_type in TOOL_STEPPED_JOB_TYPES:
            steps_seq = CommentedSeq()
            for step in spec.get("steps") or []:
                if not isinstance(step, dict):
                    continue
                step_name = str(step.get("name", "")).strip()
                commands = _as_command_list(step.get("command"))
                if step_name == "" or not commands:
                    continue
                item = CommentedMap()
                item["name"] = step_name
                item["command"] = _as_flow_seq(commands)
                steps_seq.append(item)
            if len(steps_seq) > 0:
                section[f"{job_type}_steps"] = steps_seq
    return section

def get_tool_metrics_path(tools_path, name) -> str:
    """
    Get the metrics.yml path of a specific workspace tool.
    """
    return os.path.join(tools_path, name, TOOL_METRICS_FILENAME)

def load_tool_metrics(tools_path, name) -> dict:
    """
    Load a workspace tool's metrics.yml.

    Returns:
        dict: {section_key: {metric_name: definition}} for each of
        TOOL_METRIC_SECTIONS. Missing sections come back as empty dicts.
    """
    path = get_tool_metrics_path(tools_path, name)
    data = load_yaml_file(path, default={})
    result = {}
    for section_key, _label in TOOL_METRIC_SECTIONS:
        section = data.get(section_key, {}) if isinstance(data, dict) else {}
        result[section_key] = section if isinstance(section, dict) else {}
    return result

def save_tool_metrics(tools_path, name, sections) -> None:
    """
    Save a workspace tool's metrics.yml, preserving comments and any key not
    owned by the editor. `sections` is a {section_key: {metric_name: definition}}
    dict for the TOOL_METRIC_SECTIONS keys.

    The file holds only what the workspace says about the tool's metrics: the
    metrics it adds, the built-in ones it overrides, and, as entries mapped to
    None, the built-in ones it removes (see odatix.lib.metrics).
    """
    path = get_tool_metrics_path(tools_path, name)
    yaml_obj = YAML()

    if os.path.exists(path):
        with open(path, "r") as f:
            data = yaml_obj.load(f)
        if data is None:
            data = CommentedMap()
    else:
        data = CommentedMap()

    for section_key, _label in TOOL_METRIC_SECTIONS:
        definitions = sections.get(section_key, {})
        if isinstance(definitions, dict) and len(definitions) > 0:
            data[section_key] = definitions
        else:
            data.pop(section_key, None)

    save_yaml_file(path, data, yaml_obj=yaml_obj)

######################################
# Architecture Settings
######################################
 
def load_architecture_settings(arch_path, arch_name, domain=hard_settings.main_parameter_domain) -> dict:
    """
    Load the settings of a specific parameter domain of an architecture.
    """
    path = get_arch_domain_path(arch_path, arch_name, domain)
    path = os.path.join(path, hard_settings.param_settings_filename)
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}

def save_architecture_settings(arch_path, arch_name, settings) -> None:
    """
    Save the settings of a specific parameter domain of an architecture.
    """
    path = get_arch_domain_path(arch_path, arch_name, hard_settings.main_parameter_domain)
    os.makedirs(path, exist_ok=True)
    path = os.path.join(path, hard_settings.param_settings_filename)

    yaml_obj = YAML()

    data = CommentedMap()

    data.yaml_set_start_comment(
f"""##############################################
# Settings for {arch_name}
##############################################

# This file was generated by Odatix GUI {motd.read_version()} on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}.
# You can still modify manually this file as needed.
"""
    )

    generate_rtl = settings.get('generate_rtl', False)
    data['generate_rtl'] = generate_rtl
    data.yaml_set_comment_before_after_key('generate_rtl', before="\nRTL generation")
    
    if generate_rtl:
        data['design_path'] = settings.get('design_path', [])
        data['design_path_whitelist'] = settings.get('design_path_whitelist', [])
        data['design_path_blacklist'] = settings.get('design_path_blacklist', [])
        data['generate_command'] = settings.get('generate_command', "")
        data['generate_output'] = settings.get('generate_output', "")
    else:
        data['rtl_path'] = settings.get('rtl_path', "")
    data['top_level_file'] = settings.get('top_level_file', "")
    data['top_level_module'] = settings.get('top_level_module', "")
    if generate_rtl:
        data.yaml_set_comment_before_after_key('top_level_file', before="\nSource files")
    else:
        data.yaml_set_comment_before_after_key('rtl_path', before="\nSource files")

    data['clock_signal'] = settings.get('clock_signal', "")
    data['reset_signal'] = settings.get('reset_signal', "")
    data.yaml_set_comment_before_after_key('clock_signal', before="\nSignals")

    data['use_parameters'] = settings.get('use_parameters', False)
    data['start_delimiter'] = settings.get('start_delimiter', "")
    data['stop_delimiter'] = settings.get('stop_delimiter', "")
    data.yaml_set_comment_before_after_key('use_parameters', before="\nDelimiters for parameter files")

    fmax = CommentedMap()
    settings_fmax = settings.get('fmax_synthesis', {})
    lower_bound = settings_fmax.get('lower_bound', "")
    upper_bound = settings_fmax.get('upper_bound', "")
    if lower_bound != "" and upper_bound != "":
        fmax = {}
    elif lower_bound != "":
        fmax['lower_bound'] = lower_bound if lower_bound != "" else hard_settings.default_fmax_lower_bound
    elif upper_bound != "":
        fmax['upper_bound'] = upper_bound if upper_bound != "" else hard_settings.default_fmax_upper_bound
    data['fmax_synthesis'] = fmax
    data.yaml_set_comment_before_after_key('fmax_synthesis', before="\nDefault frequencies (in MHz)")

    custom = CommentedMap()
    settings_custom = settings.get('custom_freq_synthesis', {})
    settings_custom_list = settings_custom.get('list', [])
    custom_list = CommentedSeq(settings_custom_list)
    custom_list.fa.set_flow_style()
    custom['list'] = custom_list
    data['custom_freq_synthesis'] = custom if settings_custom_list else {}

    generate_configurations = settings.get('generate_configurations', False)
    data['generate_configurations'] = generate_configurations
    settings_gen = settings.get('generate_configurations_settings', {})
    if settings_gen:
        data['generate_configurations_settings'] = settings_gen
    data.yaml_set_comment_before_after_key('generate_configurations', before="\nConfiguration generation")

    with open(path, "w") as f:
        yaml_obj.dump(data, f)


######################################
# Parameter Domains
######################################

def get_arch_domain_path(arch_path, arch_name, domain=hard_settings.main_parameter_domain) -> str:
    """
    Get the path of a specific parameter domain.
    """
    if domain == hard_settings.main_parameter_domain:
        return os.path.join(arch_path, arch_name)
    else:
        return os.path.join(arch_path, arch_name, domain)

def get_param_domains(arch_path, arch_name) -> list:
    """
    Get the list of parameter domains for a specific architecture.
    """
    folder = os.path.join(arch_path, arch_name)
    if not os.path.isdir(folder):
        return []
    domain_list = [
        d for d in os.listdir(folder)
        if os.path.isdir(os.path.join(folder, d)) and not d.startswith("_")
    ]
    return natsorted(domain_list)

def create_parameter_domain(arch_path, arch_name, domain=hard_settings.main_parameter_domain) -> None:
    """
    Create a new parameter domain for a specific architecture.
    """
    path = os.path.join(arch_path, arch_name, domain)
    os.makedirs(path, exist_ok=True)

def duplicate_parameter_domain(arch_path, source_arch_name, target_arch_name, source_domain, target_domain) -> None:
    """
    Duplicate a parameter domain for a specific architecture.
    """
    if target_domain == hard_settings.main_parameter_domain:
        raise ValueError("Cannot duplicate to the main parameter domain.")
    if target_domain == source_domain and source_arch_name == target_arch_name:
        raise ValueError("Source and target domain cannot be the same.")
    
    source_path = get_arch_domain_path(arch_path, source_arch_name, source_domain)
    target_path = get_arch_domain_path(arch_path, target_arch_name, target_domain)
    if not os.path.isdir(source_path):
        return
    if os.path.exists(target_path):
        return
    
    if source_domain == hard_settings.main_parameter_domain:
        # copy only the files in the main domain folder, not the folders
        for item in os.listdir(source_path):
            s = os.path.join(source_path, item)
            d = os.path.join(target_path, item)
            if os.path.isdir(s):
                continue
            os.makedirs(target_path, exist_ok=True)
            with open(s, "rb") as fsrc:
                with open(d, "wb") as fdst:
                    fdst.write(fsrc.read())
            # overwrite the settings file to remove unwanted keys
            settings = load_architecture_settings(arch_path, source_arch_name, source_domain)
            save_domain_settings(arch_path, target_arch_name, target_domain, settings)
    else:
        # copy the entire folder
        copytree(source_path, target_path)

def delete_parameter_domain(arch_path, arch_name, domain=hard_settings.main_parameter_domain) -> None:
    """
    Delete a specific parameter domain for a specific architecture.
    """
    if domain == hard_settings.main_parameter_domain:
        raise ValueError("Cannot delete the main parameter domain.")
    path = os.path.join(arch_path, arch_name, domain)
    if os.path.isdir(path):
        for root, dirs, files in os.walk(path, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(path)

def rename_parameter_domain(arch_path, arch_name, old_domain, new_domain) -> None:
    """
    Rename a specific parameter domain for a specific architecture.
    """
    if old_domain == hard_settings.main_parameter_domain:
        raise ValueError("Cannot rename the main parameter domain.")
    old_path = os.path.join(arch_path, arch_name, old_domain)
    new_path = os.path.join(arch_path, arch_name, new_domain)
    if not os.path.isdir(old_path):
        return
    if os.path.exists(new_path):
        return
    os.rename(old_path, new_path)

def parameter_domain_exists(arch_path, arch_name, domain=hard_settings.main_parameter_domain) -> bool:
    """
    Check if a specific parameter domain exists.
    """
    path = get_arch_domain_path(arch_path, arch_name, domain)
    return os.path.isdir(path)

def check_parameter_domain_use_parameters(arch_path, arch_name, domain=hard_settings.main_parameter_domain) -> bool:
    """
    Check if a specific parameter domain uses parameters.
    """
    settings = load_architecture_settings(arch_path, arch_name, domain)
    if not settings:
        return False
    return settings.get('use_parameters', True)

#######################################
# Parameter Domain Settings
#######################################

def save_domain_settings(arch_path, arch_name, domain, settings) -> None:
    """
    Save the settings of a specific parameter domain of an architecture.
    """
    if domain == hard_settings.main_parameter_domain:
        settings = update_raw_settings(arch_path, arch_name, domain, settings)
        save_architecture_settings(arch_path, arch_name, settings)
        return
    
    path = get_arch_domain_path(arch_path, arch_name, domain)
    os.makedirs(path, exist_ok=True)
    path = os.path.join(path, hard_settings.param_settings_filename)

    yaml_obj = YAML()

    data = CommentedMap()

    data.yaml_set_start_comment(
f"""##############################################
# Settings for {arch_name} - {domain}
##############################################

# This file was generated by Odatix GUI {motd.read_version()} on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}.
# You can still modify manually this file as needed.
"""
    )

    data['use_parameters'] = settings.get('use_parameters', True)
    data['param_target_file'] = settings.get('param_target_file', "")
    data['start_delimiter'] = settings.get('start_delimiter', "")
    data['stop_delimiter'] = settings.get('stop_delimiter', "")
    data.yaml_set_comment_before_after_key('param_target_file', before="\nDelimiters for parameter files")

    data['generate_configurations'] = settings.get('generate_configurations', False)
    settings_gen = settings.get('generate_configurations_settings', {})
    data['generate_configurations_settings'] = settings_gen
    data.yaml_set_comment_before_after_key('generate_configurations', before="\nConfiguration generation settings")

    with open(path, "w") as f:
        yaml_obj.dump(data, f)

def update_domain_settings(arch_path, arch_name, domain, settings_to_update) -> None:
    """
    Update only the provided settings in the YAML file, preserving comments and other keys.
    """
    path = get_arch_domain_path(arch_path, arch_name, domain)
    path = os.path.join(path, hard_settings.param_settings_filename)

    if not os.path.exists(path):
        save_domain_settings(arch_path, arch_name, domain, settings_to_update)
        return

    yaml_obj = YAML()

    # Load current settings with comments
    if os.path.exists(path):
        with open(path, "r") as f:
            settings = yaml_obj.load(f)
            if settings is None:
                settings = CommentedMap()
    else:
        settings = CommentedMap()

    # Update only the provided keys
    for k, v in settings_to_update.items():
        # Special handling for 'generate_configurations_settings' to preserve list formatting
        if k == "generate_configurations_settings" and isinstance(v, dict):
            _compact_list_variables_in_config_settings(v)
        settings[k] = v

    # Save back, preserving comments and formatting
    with open(path, "w") as f:
        yaml_obj.dump(settings, f)


#######################################
# Generic Instance Domain Settings (Architectures & Workflows)
#######################################

def load_instance_domain_settings(path, name, domain=hard_settings.main_parameter_domain, kind="arch") -> dict:
    """
    Load the settings of a parameter domain, for either an architecture or a workflow.
    """
    if kind == "workflow":
        return load_workflow_settings(path, name, domain)
    return load_architecture_settings(path, name, domain)

def update_instance_domain_settings(path, name, domain, settings_to_update, kind="arch") -> None:
    """
    Update the settings of a parameter domain, for either an architecture or a workflow.
    """
    if kind == "workflow":
        update_workflow_settings(path, name, settings_to_update, domain)
    else:
        update_domain_settings(path, name, domain, settings_to_update)


######################################
# Configuration Files
######################################

def get_config_files(arch_path, arch_name, domain=hard_settings.main_parameter_domain) -> list:
    """
    Get the list of configuration files for a specific parameter domain of an architecture.
    """
    path = get_arch_domain_path(arch_path, arch_name, domain)
    if not os.path.isdir(path):
        return []
    return natsorted([
        f for f in os.listdir(path)
        if f.endswith(".txt") and os.path.isfile(os.path.join(path, f))
    ])

def load_config_file(arch_path, arch_name, domain, filename) -> str:
    """
    Load the content of a specific configuration file for a specific parameter domain of an architecture.
    """
    path = get_arch_domain_path(arch_path, arch_name, domain)
    path = os.path.join(path, filename)
    if not os.path.exists(path):
        return ""
    with open(path, "r") as f:
        return f.read()

def save_config_file(arch_path, arch_name, domain, filename, content) -> None:
    """
    Save the content of a specific configuration file for a specific parameter domain of an architecture.
    """
    path = get_arch_domain_path(arch_path, arch_name, domain)
    os.makedirs(path, exist_ok=True)
    path = os.path.join(path, filename)
    with open(path, "w") as f:
        f.write(content)

def delete_config_file(arch_path, arch_name, domain, filename) -> None:
    """
    Delete a specific configuration file for a specific parameter domain of an architecture.
    """
    path = get_arch_domain_path(arch_path, arch_name, domain)
    path = os.path.join(path, filename)
    if os.path.exists(path):
        os.remove(path)

def delete_all_config_files(arch_path, arch_name, domain=hard_settings.main_parameter_domain) -> None:
    """
    Delete all configuration files for a specific parameter domain of an architecture.
    """
    path = get_arch_domain_path(arch_path, arch_name, domain)
    if not os.path.isdir(path):
        return
    for f in os.listdir(path):
        if f.endswith(".txt"):
            os.remove(os.path.join(path, f))


######################################
# Workflow Configuration Files
######################################

def get_workflow_config_files(workflow_path, workflow_name) -> list:
    """
    Get configuration files for a workflow.
    """
    return get_config_files(workflow_path, workflow_name, hard_settings.main_parameter_domain)

def load_workflow_config_file(workflow_path, workflow_name, filename) -> str:
    """
    Load a workflow configuration file.
    """
    return load_config_file(workflow_path, workflow_name, hard_settings.main_parameter_domain, filename)

def save_workflow_config_file(workflow_path, workflow_name, filename, content) -> None:
    """
    Save a workflow configuration file.
    """
    save_config_file(workflow_path, workflow_name, hard_settings.main_parameter_domain, filename, content)

def delete_workflow_config_file(workflow_path, workflow_name, filename) -> None:
    """
    Delete a workflow configuration file.
    """
    delete_config_file(workflow_path, workflow_name, hard_settings.main_parameter_domain, filename)

def delete_all_workflow_config_files(workflow_path, workflow_name) -> None:
    """
    Delete all workflow configuration files.
    """
    delete_all_config_files(workflow_path, workflow_name, hard_settings.main_parameter_domain)

def count_combinations(domains_configs):
    """Return the number of possible combinations for the current domains_configs dict."""
    if not domains_configs:
        return 0
    sizes = [len(cfgs) for cfgs in domains_configs.values() if cfgs]
    if not sizes:
        return 0
    return reduce(operator.mul, sizes, 1)

def generate_config_combinations(domains_configs, arch_name) -> list:
    if domains_configs == {}:
        return []

    domain_names = list(domains_configs.keys())
    config_lists = [domains_configs[d] for d in domain_names]

    combinations = []
    for combo in product(*config_lists):
        replaced_parts = []
        for domain, cfg in zip(domain_names, combo):
            display_domain = arch_name if domain == hard_settings.main_parameter_domain else domain
            replaced_parts.append(f"{display_domain}/{cfg}")

        if domain_names and domain_names[0] != hard_settings.main_parameter_domain:
            combination = [arch_name] + replaced_parts
        else:
            combination = replaced_parts

        combinations.append(combination)

    return combinations

#######################################
# Configuration Generation
#######################################

def create_config_gen_dict(name: str, template: str, variables: dict) -> dict:
    """
    Create a configuration generation dictionary.

    Args:
        name (str): Name of the configuration.
        template (str): Template string for the configuration name.
        variables (dict): Dictionary of variables and their values.

    Returns:
        dict: Configuration generation dictionary.
    """
    return {
        'generate_configurations': True,
        'generate_configurations_settings': {
            'name': name,
            'template': template,
            'variables': variables,
        }
    }

def create_config_gen_variable_dict(name: str, type: str, settings: dict, format: Optional[str]=None, group: Optional[str]=None) -> dict:
    """
    Create a configuration generation variable dictionary.

    Args:
        name (str): Name of the variable.
        type (str): Type of the variable (e.g., 'range', 'list', 'function').
        settings (dict): Settings specific to the variable type.
        format (str): Optional format string for the variable's values.
        group (str): Optional pairing group. Variables sharing the same group are
            zipped together (values matched position by position) instead of being
            cross-combined.

    Returns:
        dict: Configuration generation variable dictionary.
    """
    var_dict = {
        name: {
            'type': type,
            'settings': settings,
        }
    }
    if format:
        var_dict[name]['format'] = format
    if group:
        var_dict[name]['group'] = group
    return var_dict


######################################
# EDA Target Files
######################################
#
# Target files ("target_<tool>.yml") hold the synthesis targets of one EDA
# tool. The run flows only consume the "targets" list, so disabled targets are
# kept as commented-out entries of that list ("# - <target>"), the historical
# hand-written format of these files: they stay in the file and can be
# re-enabled later. A "disabled_targets" list is also understood when reading.
# Per-target options such as "script_copy_enable" / "script_copy_source" live
# in the "target_settings" mapping, which is already understood by
# ArchitectureHandler.

# "  - name" (enabled) or "  # - name" (disabled), optional trailing comment
_target_item_pattern = re.compile(r'^\s+-\s*([^#]+?)\s*(?:#.*)?$')
_target_commented_pattern = re.compile(r'^\s*#\s*-\s*([^#]+?)\s*(?:#.*)?$')
_targets_key_pattern = re.compile(r'^targets\s*:')
_commented_target_line_pattern = re.compile(r'^\s*#\s*-\s*\S')


def _scan_targets_block(text):
    """
    Scan the "targets:" block of a target file, line by line, and return the
    ordered list of (name, enabled) entries: plain list items are enabled,
    commented-out items ("# - <target>") are disabled.
    """
    entries = []
    in_block = False
    for line in text.splitlines():
        if _targets_key_pattern.match(line):
            in_block = True
            continue
        if not in_block:
            continue
        item_match = _target_item_pattern.match(line)
        commented_match = _target_commented_pattern.match(line)
        if item_match:
            entries.append((item_match.group(1).strip().strip("\"'"), True))
        elif commented_match:
            entries.append((commented_match.group(1).strip().strip("\"'"), False))
        elif line.strip() == "" or line.lstrip().startswith("#"):
            continue  # blank lines and other comments do not end the block
        elif not line[0].isspace():
            in_block = False  # next top-level key
    return entries


def _scrub_commented_targets(commented_map, key):
    """
    Remove "# - <target>" lines from the ruamel comments attached to a key,
    keeping any other comment line. Tokens left empty are dropped entirely
    (empty comment tokens corrupt the ruamel emitter output).
    """
    ca_items = getattr(getattr(commented_map, "ca", None), "items", None)
    if not ca_items or key not in ca_items:
        return

    def scrub_token(token):
        if token is None or not hasattr(token, "value"):
            return token
        kept = [line for line in token.value.splitlines(keepends=True) if not _commented_target_line_pattern.match(line)]
        token.value = "".join(kept)
        return token if token.value != "" else None

    slots = ca_items[key]
    for i, slot in enumerate(slots):
        if isinstance(slot, list):
            kept_tokens = [t for t in (scrub_token(token) for token in slot) if t is not None]
            slots[i] = kept_tokens if kept_tokens else None
        else:
            slots[i] = scrub_token(slot)
    if all(slot is None for slot in slots):
        del ca_items[key]

def get_target_file_path(target_path, tool) -> str:
    """
    Get the path of the target file of an EDA tool.

    The file name comes from the tool's tool.yml ("target_file" key, defaulting
    to "target_<tool>.yml"). The file is looked up in `target_path` first, then
    in the userconfig root (see odatix.lib.eda_tools.resolve_target_file), so an
    existing file at the legacy location is edited in place; a brand-new file is
    created under `target_path` (odatix_userconfig/targets by default).
    """
    import odatix.lib.eda_tools as eda_tools
    return eda_tools.resolve_target_file(tool, target_path)


def target_file_exists(target_path, tool) -> bool:
    """
    Check if the target file of an EDA tool exists.
    """
    return os.path.isfile(get_target_file_path(target_path, tool))


def get_targets(target_path, tool) -> list:
    """
    Get the normalized target list of an EDA tool. Commented-out entries of
    the "targets" list ("# - <target>") are returned as disabled targets.

    Returns:
        list of dicts: {"name", "enabled", "script_copy_enable", "script_copy_source"},
        in file order.
    """
    path = get_target_file_path(target_path, tool)
    data = load_yaml_file(path, default={})
    if not isinstance(data, dict):
        data = {}

    # File order (with commented-out entries as disabled targets)
    entries = []
    if os.path.isfile(path):
        try:
            with open(path, "r") as f:
                entries = _scan_targets_block(f.read())
        except OSError:
            entries = []

    seen = {name for name, _ in entries}

    # Merge entries only visible to the yaml parser (e.g. flow-style lists)
    enabled_names = data.get("targets") or []
    disabled_names = data.get("disabled_targets") or []
    if isinstance(enabled_names, list):
        entries += [(str(n), True) for n in enabled_names if str(n) not in seen]
        seen.update(str(n) for n in enabled_names)
    if isinstance(disabled_names, list):
        entries += [(str(n), False) for n in disabled_names if str(n) not in seen]

    target_settings = data.get("target_settings")
    if not isinstance(target_settings, dict):
        target_settings = {}

    targets = []
    added = set()
    for name, enabled in entries:
        name = str(name)
        if name == "" or name in added:
            continue
        added.add(name)
        settings = target_settings.get(name)
        settings = settings if isinstance(settings, dict) else {}
        targets.append({
            "name": name,
            "enabled": enabled,
            "script_copy_enable": _parse_bool(settings.get("script_copy_enable", False)),
            "script_copy_source": str(settings.get("script_copy_source", "") or ""),
        })
    return targets


def target_exists(target_path, tool, name) -> bool:
    """
    Check if a target exists (enabled or disabled) for an EDA tool.
    """
    return any(target["name"] == name for target in get_targets(target_path, tool))


def save_target_selection(target_path, tool, targets) -> None:
    """
    Save the target list of an EDA tool while preserving comments and any
    other key of the target file (constraint_file, tool_install_path, ...).
    Disabled targets are written as commented-out entries of the "targets"
    list ("# - <target>").

    Args:
        targets: list of dicts {"name", "enabled", "script_copy_enable",
            "script_copy_source"} and optionally "original_name" (for renames:
            existing per-target settings are carried over).
    """
    path = get_target_file_path(target_path, tool)
    yaml_obj = YAML()

    settings = None
    if os.path.exists(path):
        with open(path, "r") as f:
            settings = yaml_obj.load(f)
    if settings is None:
        settings = CommentedMap()

    old_target_settings = settings.get("target_settings")
    if not isinstance(old_target_settings, dict):
        old_target_settings = {}

    ordered = []  # (name, enabled), deduplicated
    new_target_settings = CommentedMap()
    seen = set()
    for target in targets:
        name = str(target.get("name", "")).strip()
        original_name = str(target.get("original_name") or name)
        if name == "":
            name = original_name
        if name == "" or name in seen:
            continue
        seen.add(name)
        ordered.append((name, bool(target.get("enabled", True))))

        # Carry over existing per-target settings (possibly under the old name)
        per_target = old_target_settings.get(original_name, old_target_settings.get(name))
        per_target = copy.deepcopy(per_target) if isinstance(per_target, dict) else CommentedMap()
        if _parse_bool(target.get("script_copy_enable", False)):
            per_target["script_copy_enable"] = True
            per_target["script_copy_source"] = str(target.get("script_copy_source", "") or "")
        else:
            per_target.pop("script_copy_enable", None)
            per_target.pop("script_copy_source", None)
        if per_target:
            new_target_settings[name] = per_target

    # Old commented-out target entries are re-emitted below: remove them from
    # the comments attached to the "targets" key (comments that precede the
    # first list item live there; comments attached to the old list items are
    # dropped with the list itself).
    _scrub_commented_targets(settings, "targets")

    # The whole block is rewritten textually below ("targets: []" placeholder)
    settings["targets"] = []
    settings.pop("disabled_targets", None)  # legacy representation
    if new_target_settings:
        settings["target_settings"] = new_target_settings
    else:
        settings.pop("target_settings", None)

    buffer = io.StringIO()
    yaml_obj.dump(settings, buffer)
    text = buffer.getvalue()

    if ordered:
        block_lines = ["targets:"]
        for name, enabled in ordered:
            block_lines.append(f"  - {name}" if enabled else f"  # - {name}")
        text = re.sub(r"(?m)^targets:\s*\[\]\s*$", lambda _: "\n".join(block_lines), text, count=1)

    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


def add_target(target_path, tool, name, enabled=True) -> None:
    """
    Add a new target to the target file of an EDA tool.
    """
    targets = get_targets(target_path, tool)
    if any(target["name"] == name for target in targets):
        raise ValueError(f"Target '{name}' already exists.")
    targets.append({"name": name, "enabled": enabled, "script_copy_enable": False, "script_copy_source": ""})
    save_target_selection(target_path, tool, targets)


def duplicate_target(target_path, tool, source_name, target_name) -> None:
    """
    Duplicate a target (including its per-target settings).
    """
    targets = get_targets(target_path, tool)
    source = next((target for target in targets if target["name"] == source_name), None)
    if source is None:
        raise ValueError(f"Source target '{source_name}' does not exist.")
    if any(target["name"] == target_name for target in targets):
        raise ValueError(f"Target '{target_name}' already exists.")
    duplicate = dict(source)
    duplicate["name"] = target_name
    duplicate["original_name"] = source_name  # carry per-target settings over
    targets.append(duplicate)
    save_target_selection(target_path, tool, targets)


def remove_target(target_path, tool, name) -> None:
    """
    Remove a target (and its per-target settings) from the target file.
    """
    targets = [target for target in get_targets(target_path, tool) if target["name"] != name]
    save_target_selection(target_path, tool, targets)


#######################################
# Architecture Selection
#######################################

DEFAULT_ARCH_SELECTION_SETTINGS = {
    "overwrite": False,
    "ask_continue": False,
    "exit_when_done": False,
    "log_size_limit": 300,
    "nb_jobs": 8,
    "frequencies": {
        "override": False,
        "list": hard_settings.default_custom_freq_list,
        "range": {
            "from": 50,
            "to": 100,
            "step": 10,
        },
    },
    "architectures": [],
}

def load_yaml_file(path: str, default=None):
    if default is None:
        default = {}
    if not path or not os.path.isfile(path):
        return copy.deepcopy(default)
    try:
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        if data is None:
            return copy.deepcopy(default)
        return data
    except Exception:
        return copy.deepcopy(default)

def save_yaml_file(path: str, data, yaml_obj: Optional[YAML]=None) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    writer = yaml_obj if yaml_obj is not None else YAML()
    with open(path, "w") as f:
        writer.dump(data, f)

def load_arch_selection_settings(path: str) -> dict:
    if not os.path.exists(path):
        print(f"Settings file '{path}' does not exist. Using default settings.", "yellow")
        return {}
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}

def load_analysis_tools(path: str) -> list:
    """
    Load the list of eda tools to run the RTL analysis with (the "tools" key of
    the analysis settings file). Returns an empty list if the file or the key is
    missing.
    """
    data = load_yaml_file(path, default={})
    if not isinstance(data, dict):
        return []
    tools = data.get("tools", [])
    if isinstance(tools, str):
        tools = [tools]
    if not isinstance(tools, (list, tuple)):
        return []
    return [str(tool) for tool in tools if tool]

def get_frequencies_form_values(settings: dict) -> dict:
    frequencies = _normalize_frequencies_settings(settings.get("frequencies", {}))
    return {
        "frequencies": frequencies,
    }

def create_custom_frequencies_settings_dict(
    override_enabled,
    target_frequencies,
    from_frequency,
    to_frequency,
    step_frequency,
    use_custom_freq_list=None,
    use_custom_freq_range=None,
) -> dict:
    frequencies = copy.deepcopy(DEFAULT_ARCH_SELECTION_SETTINGS["frequencies"])
    frequencies["override"] = bool(override_enabled)

    frequencies["list"] = _parse_int_list(target_frequencies)

    frequencies["range"] = {
        "from": _parse_int(from_frequency),
        "to": _parse_int(to_frequency),
        "step": _parse_int(step_frequency),
    }

    normalized = _normalize_frequencies_settings(frequencies)

    # The "List" / "Range" switches are only reflected in the parsed list/range
    # values on save (via disabled_list/disabled_range), so their toggle state
    # is passed through explicitly here to make it visible for change detection.
    if use_custom_freq_list is not None:
        normalized["use_custom_freq_list"] = bool(use_custom_freq_list)
    if use_custom_freq_range is not None:
        normalized["use_custom_freq_range"] = bool(use_custom_freq_range)

    return normalized

def create_fmax_bounds_settings_dict(lower_bound, upper_bound, override_enabled=None) -> dict:
    """
    Build the fmax synthesis bounds settings dict from the GUI form values.
    Empty fields are stored as "" (meaning "use the default / architecture-specific bound").
    """
    lower = _parse_int(lower_bound)
    upper = _parse_int(upper_bound)
    return {
        "override": bool(override_enabled),
        "lower_bound": lower if lower is not None else "",
        "upper_bound": upper if upper is not None else "",
    }

def save_architecture_selection(path, settings, run_mode="default", use_custom_freq_list=False, use_custom_freq_range=False) -> None:
    """
    Save the architecture selection settings.
    """
    
    if run_mode == "fmax_synthesis":
        run_mode_display = "fmax synthesis"
    elif run_mode == "custom_freq_synthesis":
        run_mode_display = "custom frequency synthesis"
    elif run_mode == "workflow":
        run_mode_display = "workflows"
    elif run_mode == "simulation":
        run_mode_display = "simulations"
    elif run_mode == "analyze":
        run_mode_display = "RTL analysis"
    else:
        run_mode_display = run_mode

    yaml_obj = YAML()

    data = CommentedMap()

    data.yaml_set_start_comment(
f"""##############################################
# Odatix settings for {run_mode_display}
##############################################

# This file was generated by Odatix GUI {motd.read_version()} on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}.
# You can still modify manually this file as needed.
"""
    )

    # overwrite
    overwrite_val = "Yes" if settings.get('overwrite', False) else "No"
    data['overwrite'] = overwrite_val
    data.yaml_set_comment_before_after_key(key='overwrite', before="\n overwrite existing results")
    data.yaml_add_eol_comment(key='overwrite', comment="overridden by -o / --overwrite")

    # ask_continue
    ask_continue_val = "Yes" if settings.get('ask_continue', False) else "No"
    data['ask_continue'] = ask_continue_val
    data.yaml_set_comment_before_after_key(key='ask_continue', before="\n prompt 'Continue? (Y/n)' after settings checks")
    data.yaml_add_eol_comment(key='ask_continue', comment="overridden by -y / --noask")

    # exit_when_done
    exit_when_done_val = "Yes" if settings.get('exit_when_done', False) else "No"
    data['exit_when_done'] = exit_when_done_val
    data.yaml_set_comment_before_after_key(key='exit_when_done', before="\n exit monitor when all jobs are done")
    data.yaml_add_eol_comment(key='exit_when_done', comment="overridden by -E / --exit")

    # log_size_limit
    log_size_limit_val = settings.get('log_size_limit', 300)
    data['log_size_limit'] = log_size_limit_val
    data.yaml_set_comment_before_after_key(key='log_size_limit', before="\n size of the log history per job in the monitor")
    data.yaml_add_eol_comment(key='log_size_limit', comment="overridden by --logsize")

    # nb_jobs
    nb_jobs_val = settings.get('nb_jobs', 8)
    data['nb_jobs'] = nb_jobs_val
    data.yaml_set_comment_before_after_key(key='nb_jobs', before="\n maximum number of parallel jobs ('auto' = number of CPUs minus one)")
    data.yaml_add_eol_comment(key='nb_jobs', comment="overridden by -j / --jobs")

    # force_single_thread
    force_single_thread_val = "Yes" if settings.get('force_single_thread', False) else "No"
    data['force_single_thread'] = force_single_thread_val
    data.yaml_set_comment_before_after_key(key='force_single_thread', before="\n force single thread execution (to avoid cpu overload when running many jobs in parallel)")

    if run_mode == "custom_freq_synthesis":
        # frequencies
        frequencies = _normalize_frequencies_settings(settings.get('frequencies', {}))
        frequencies_data = CommentedMap()
        
        frequencies_data['override'] = "Yes" if frequencies.get('override', False) else "No"
        frequencies_data.yaml_add_eol_comment(key='override', comment="if false, those values are only used when no architecture-specific frequencies are defined")

        list_values = CommentedSeq(frequencies.get('list', []))
        list_values.fa.set_flow_style()
        if use_custom_freq_list:
            frequencies_data['list'] = list_values
            frequencies_data.yaml_add_eol_comment(key='list', comment="overridden by --at")
        else:
            frequencies_data['disabled_list'] = list_values
            frequencies_data.yaml_add_eol_comment(key='disabled_list', comment=" not used but settings are saved")
        
        range_data = CommentedMap()
        range_val = frequencies.get('range', {})
        range_data['from'] = range_val.get('from')
        range_data['to'] = range_val.get('to')
        range_data['step'] = range_val.get('step')
        range_data.yaml_add_eol_comment(key='from', comment="overridden by --from")
        range_data.yaml_add_eol_comment(key='to', comment="overridden by --to")
        range_data.yaml_add_eol_comment(key='step', comment="overridden by --step")

        if use_custom_freq_range:
            frequencies_data['range'] = range_data
        else:
            frequencies_data['disabled_range'] = range_data
            frequencies_data.yaml_add_eol_comment(key='disabled_range', comment=" not used but settings are saved")

        data['frequencies'] = frequencies_data
        data.yaml_set_comment_before_after_key(key='frequencies', before="\n synthesis frequencies (in MHz)")

    if run_mode == "fmax_synthesis":
        # fmax binary search bounds
        settings_fmax = settings.get('fmax_synthesis', {})
        if not isinstance(settings_fmax, dict):
            settings_fmax = {}
        fmax_data = CommentedMap()

        fmax_data['override'] = "Yes" if _parse_bool(settings_fmax.get('override'), False) else "No"
        fmax_data.yaml_add_eol_comment(key='override', comment="if false, those values are only used when no architecture-specific bounds are defined")

        lower_bound = _parse_int(settings_fmax.get('lower_bound'))
        upper_bound = _parse_int(settings_fmax.get('upper_bound'))
        fmax_data['lower_bound'] = lower_bound if lower_bound is not None else ""
        fmax_data['upper_bound'] = upper_bound if upper_bound is not None else ""
        fmax_data.yaml_add_eol_comment(key='lower_bound', comment="overridden by --from (empty: use default / architecture-specific bound)")
        fmax_data.yaml_add_eol_comment(key='upper_bound', comment="overridden by --to (empty: use default / architecture-specific bound)")

        data['fmax_synthesis'] = fmax_data
        data.yaml_set_comment_before_after_key(key='fmax_synthesis', before="\n fmax binary search bounds (in MHz)")

    # eda tools to run the analysis with (analysis only)
    if run_mode == "analyze":
        tools_list = settings.get('tools', []) or []
        tools_seq = CommentedSeq([str(tool) for tool in tools_list if tool])
        data['tools'] = tools_seq
        data.yaml_set_comment_before_after_key(key='tools', before="\n eda tools to run the analysis with")
        data.yaml_add_eol_comment(key='tools', comment="overridden by -t / --tool")

    # targeted instances (architectures, workflows or simulations)
    if run_mode == "workflow":
        workflows = settings.get('workflows', settings.get('architectures', []))
        data['workflows'] = workflows
        data.yaml_set_comment_before_after_key(key='workflows', before="\n targeted workflows")
    elif run_mode == "simulation":
        # One entry per simulation, each holding the architecture configurations
        # it runs on (see load_simulation_selection).
        simulations = settings.get('simulations', [])
        if isinstance(simulations, dict):
            simulations = create_simulation_selection_list(simulations)
        data['simulations'] = simulations
        data.yaml_set_comment_before_after_key(key='simulations', before="\n targeted simulations")
    else:
        architectures = settings.get('architectures', {})
        data['architectures'] = architectures
        data.yaml_set_comment_before_after_key(key='architectures', before="\n targeted architectures")

    save_yaml_file(path, data, yaml_obj=yaml_obj)


#######################################
# Helpers
#######################################

def _parse_bool(value, default=False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        val = value.strip().lower()
        if val in ("yes", "true", "1"):
            return True
        if val in ("no", "false", "0"):
            return False
    return default

def _parse_int(value, default=None):
    try:
        if value in (None, ""):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default

def _parse_int_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        iterable = value
    else:
        iterable = str(value).replace(";", ",").split(",")

    parsed = []
    for item in iterable:
        number = _parse_int(item)
        if number is None:
            continue
        parsed.append(number)
    return parsed

def _normalize_frequencies_settings(frequencies: dict) -> dict:
    defaults = copy.deepcopy(DEFAULT_ARCH_SELECTION_SETTINGS["frequencies"])

    if not isinstance(frequencies, dict):
        return defaults

    defaults["override"] = _parse_bool(frequencies.get("override"), defaults["override"])
    list =_parse_int_list(frequencies.get("list", []))
    disabled_list = _parse_int_list(frequencies.get("disabled_list", []))
    if list:
        defaults["list"] = list
        defaults["use_custom_freq_list"] = True
    else:
        defaults["list"] = disabled_list
        defaults["use_custom_freq_list"] = False

    range = frequencies.get("range", {})
    disabled_range = frequencies.get("disabled_range", {})
    if range:
        range_value = range
        defaults["use_custom_freq_range"] = True
    else:
        range_value = disabled_range
        defaults["use_custom_freq_range"] = False

    if not isinstance(range_value, dict):
        range_value = {}
    
    defaults["range"] = {
        "from": _parse_int(range_value.get("from")),
        "to": _parse_int(range_value.get("to")),
        "step": _parse_int(range_value.get("step")),
    }

    return defaults

def _compact_list_variables_in_config_settings(config_settings: dict):
    """
    Edit the 'variables' in 'generate_configurations_settings' to ensure lists are compact in YAML.
    Args:
        config_settings (dict): The configuration settings dictionary.    
    """
    variables = config_settings.get("variables", {})
    for var_name, var_cfg in variables.items():
        if (
            isinstance(var_cfg, dict)
            and var_cfg.get("type") == "list"
            and "settings" in var_cfg
            and isinstance(var_cfg["settings"], dict)
            and "list" in var_cfg["settings"]
        ):
            compact_list = CommentedSeq(var_cfg["settings"]["list"])
            compact_list.fa.set_flow_style()
            var_cfg["settings"]["list"] = compact_list

def update_raw_settings(arch_path, arch_name, domain, settings_to_update) -> dict:
    """
    Update only the provided keys from a yaml file, without any formatting.
    Args:
        arch_path (str): Path to the architectures folder.
        arch_name (str): Name of the architecture.
        domain (str): Name of the parameter domain.
        settings_to_update (dict): Dictionary of settings to update.
    Returns:
        dict: Updated settings.
    """
    path = get_arch_domain_path(arch_path, arch_name, domain)
    path = os.path.join(path, hard_settings.param_settings_filename)

    # Load current settings if the file exists
    settings = load_yaml_file(path, default={})

    # Update only the provided keys
    for k, v in settings_to_update.items():
        settings[k] = v
    
    return settings


######################################
# Derived metrics
######################################

def get_derived_metrics_path(odatix_settings=None) -> str:
    """
    Path of the workspace derived metrics file (see odatix.lib.derived_metrics).
    """
    from odatix.lib.settings import OdatixSettings

    path = (odatix_settings or {}).get("derived_metrics_file", "")
    if isinstance(path, str) and path.strip() != "":
        return path

    settings_data = OdatixSettings.get_settings_file_dict(silent=True)
    if isinstance(settings_data, dict):
        path = settings_data.get("derived_metrics_file", "")
        if isinstance(path, str) and path.strip() != "":
            return path

    return OdatixSettings.DEFAULT_DERIVED_METRICS_FILE


def load_derived_metrics_file(odatix_settings=None) -> tuple:
    """
    Load the derived metrics of the workspace.

    Returns:
        tuple: (groups, metrics), each a name -> definition dict. Both are empty
        when the file is missing or unparsable, which is the normal state of a
        workspace that derives nothing.
    """
    data = load_yaml_file(get_derived_metrics_path(odatix_settings), default={})
    if not isinstance(data, dict):
        return {}, {}

    groups = data.get("groups")
    metrics = data.get("derived_metrics")
    return (
        groups if isinstance(groups, dict) else {},
        metrics if isinstance(metrics, dict) else {},
    )


def save_derived_metrics_file(groups, metrics, odatix_settings=None) -> None:
    """
    Save the derived metrics of the workspace, preserving the comments and any
    top-level key the editor does not know about.
    """
    path = get_derived_metrics_path(odatix_settings)
    yaml_obj = YAML()

    if os.path.exists(path):
        with open(path, "r") as f:
            data = yaml_obj.load(f)
        if data is None:
            data = CommentedMap()
    else:
        data = CommentedMap()

    data["groups"] = groups if groups else CommentedMap()
    data["derived_metrics"] = metrics if metrics else CommentedMap()

    save_yaml_file(path, data, yaml_obj=yaml_obj)
