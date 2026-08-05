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
Tool Editor page.

Graphical editor for a workspace tool's tool.yml (see
odatix.workspace.tools and odatix.lib.eda_tools). It exposes:
  - display metadata (Display name / description / icon),
  - behaviour (process_group, report_path, default_metrics_file),
  - the tool's *flows*: every way of running it, each one editable, and one of
    them marked as the default,
  - the log formatting section (logs / tags / replace).

A flow declares, per platform and per job type, either a single command or an
ordered list of resumable steps; a non-default flow can also declare nothing and
inherit what the default flow does. That is exactly what the three "Inherited /
Command / Steps" choices of each job type mean. The commands of the default
flow are the ones written directly in the "unix"/"windows" sections of tool.yml,
the other flows live under "flows:" — the editor hides that asymmetry.

A built-in tool is edited as an overlay: the flows Odatix ships are shown
read-only (their commands belong to Odatix, duplicate one to start from what it
does), while everything else — the metadata, the behaviour, the log formatting —
can be overridden in the workspace. Only what actually differs from the built-in
definition is written, and each section has a button putting it back to the
built-in state, the way the metrics editor handles built-in metrics. A tool with
such an overlay is still a built-in tool, on /tools as everywhere else.

YAML anchors used by the built-in tool.yml files are resolved on load, so the
editor works on plain command lists and re-emits a flat, anchor-free tool.yml on
save. The tool's metrics.yml is edited from the "Edit Metrics" button
(/metric_editor?tool=...).
"""

import copy as copy_module
import os

import dash
from dash import html, dcc, Input, Output, State, ctx

from odatix.workspace.tools import OVERRIDABLE_KEYS
import odatix.lib.eda_tools as eda_tools
from odatix.gui.icons import icon
from odatix.gui.utils import get_key_from_url, get_workspace
from odatix.gui.css_helper import Style
import odatix.gui.ui_components as ui
import odatix.gui.navigation as navigation
import odatix.lib.hard_settings as hard_settings
from odatix.lib.settings import OdatixSettings

page_path = "/tool_editor"

dash.register_page(
    __name__,
    path=page_path,
    title="Odatix - Tool Editor",
    name="Tool Editor",
    order=5,
)

# The job types a flow declares commands for, with their display label, tooltip,
# and whether they can be split into resumable steps.
JOBS = [
    ("tool_test", "Tool test", "Command run to check the tool is installed and reachable.", False),
    ("fmax_synthesis", "Fmax synthesis", "Command run to search for the maximum frequency of a design.", True),
    ("custom_freq_synthesis", "Custom frequency synthesis", "Command run to synthesize a design at given frequencies.", True),
    ("pnr", "Place & route", "Command run to place and route a netlist another tool has already synthesized.", True),
    ("analysis", "RTL analysis", "Command run to analyze (lint, elaborate) a design.", True),
]

# Supported platforms, with their display label.
PLATFORMS = [
    ("unix", "Unix / Linux"),
    ("windows", "Windows"),
]

# What a job type of a flow can declare. "inherit" declares nothing: a
# non-default flow then runs what the default flow does, and the default flow
# simply does not support the job type.
MODE_OPTIONS_DEFAULT = [
    {"label": "Not supported", "value": "inherit"},
    {"label": "Command", "value": "command"},
    {"label": "Steps", "value": "steps"},
]
MODE_OPTIONS_FLOW = [
    {"label": "Inherited", "value": "inherit"},
    {"label": "Command", "value": "command"},
    {"label": "Steps", "value": "steps"},
]

# Log levels shown in the formatting section, with their display label.
LOG_LEVELS = [
    ("error", "Error"),
    ("crit_warning", "Critical warning"),
    ("warning", "Warning"),
    ("info", "Info"),
    ("trace", "Trace"),
]

# Inline format tags recognized in the tool output. This is the fixed set of
# ANSI style/color names from JobOutputFormatter.ansi_codes: a tool only defines
# the marker string(s) mapped to each tag, it never adds or removes tags. Kept in
# sync with odatix.lib.parallel_job_handler.job_output_formatter.ansi_codes.
TAG_NAMES = [
    "black", "red", "green", "yellow", "blue",
    "magenta", "cyan", "white", "bold", "end", "grey", "light_red", "light_green",
    "light_yellow", "light_blue", "light_magenta", "light_cyan", "light_white", "end_bold",
]


######################################
# Helpers
######################################

def _builtin_tool_exists(name):
    """Check if a name collides with a built-in (non-workspace) tool."""
    builtin_path = os.path.join(OdatixSettings.odatix_eda_tools_path, name, hard_settings.tool_settings_filename)
    return bool(name) and os.path.isfile(builtin_path)

def _as_lines(value):
    """A command list/str -> textarea text (one token per line)."""
    if isinstance(value, (list, tuple)):
        return "\n".join(str(v) for v in value if str(v).strip() != "")
    if value is None:
        return ""
    return str(value)

def _lines_to_list(text):
    """A textarea text -> command list (one token per non-empty line)."""
    if not text:
        return []
    return [line.strip() for line in str(text).splitlines() if line.strip() != ""]

def _markers_to_list(text):
    """Comma-separated markers -> list."""
    if not text:
        return []
    return [m.strip() for m in str(text).split(",") if m.strip() != ""]

def _parse_platform_section(section):
    """
    Read what one platform section of a flow declares for each job type, as
    {job_type: {"mode", "command", "steps"}}. A job type the section says
    nothing about is left on "inherit".
    """
    if not isinstance(section, dict):
        section = {}
    jobs = {}
    for job, _label, _tooltip, supports_steps in JOBS:
        mode, command, steps = "inherit", [], []
        session = {"command": [], "begin": [], "end": []}
        if section.get(f"{job}_command") is not None:
            mode = "command"
            command = _lines_to_list(_as_lines(section.get(f"{job}_command")))
        elif supports_steps and isinstance(section.get(f"{job}_steps"), list):
            mode = "steps"
            declared_session = section.get(f"{job}_session")
            if isinstance(declared_session, dict):
                for part, key in (("command", "command"), ("begin", "begin"), ("end", "end")):
                    session[part] = _lines_to_list(_as_lines(declared_session.get(key)))
            for entry in section.get(f"{job}_steps"):
                if not isinstance(entry, dict):
                    continue
                name = str(entry.get("name", "") or "").strip()
                if name == "":
                    continue
                # A step declares either its whole command or what it adds to
                # the session; which one it is has to survive a round-trip.
                in_session = entry.get("command") in (None, "") and entry.get("args") not in (None, "")
                steps.append({
                    "name": name,
                    "kind": "args" if in_session else "command",
                    "command": _lines_to_list(_as_lines(entry.get("command"))),
                    "args": _lines_to_list(_as_lines(entry.get("args"))),
                    "default": bool(entry.get("default", False)),
                })
        jobs[job] = {"mode": mode, "command": command, "steps": steps, "session": session}
    return jobs

def _empty_platforms():
    return {platform: _parse_platform_section({}) for platform, _label in PLATFORMS}

def normalize_flows(raw):
    """
    Read the flows of a tool.yml as an ordered list, the default flow first.

    The default flow is the one holding the commands declared directly in the
    "unix"/"windows" sections; anything it also declares under "flows:" (its
    label, its description) is merged into it, so the editor shows one entry per
    flow whether or not the file names it.
    """
    default_name = str(raw.get("default_flow", "") or "").strip() or eda_tools.DEFAULT_FLOW_NAME

    declared = raw.get("flows")
    if not isinstance(declared, dict):
        declared = {}

    names = [default_name] + [str(name) for name in declared if str(name) != default_name]

    flows = []
    for name in names:
        spec = declared.get(name)
        if not isinstance(spec, dict):
            spec = {}
        is_default = name == default_name
        platforms = {}
        for platform, _label in PLATFORMS:
            # The default flow declares its commands at the top level; a flow
            # that also has a section under "flows:" (an alternative binary, for
            # instance) overrides what it declares there.
            section = spec.get(platform) if isinstance(spec.get(platform), dict) else {}
            if is_default:
                base = raw.get(platform) if isinstance(raw.get(platform), dict) else {}
                merged = dict(base)
                merged.update(section)
                section = merged
            platforms[platform] = _parse_platform_section(section)
        flows.append({
            "name": str(name),
            "label": str(spec.get("label", "") or ""),
            "description": str(spec.get("description", "") or ""),
            "is_default": is_default,
            # A loaded flow starts folded: the page opens on what the tool is and
            # the list of what it can run, and a flow is unfolded to work on it.
            # A tool with nothing saved yet has nothing to read, so its flow is
            # unfolded: the page opens ready to be filled in.
            "collapsed": bool(raw),
            "platforms": platforms,
        })
    return flows

def normalize_tool_settings(raw):
    """
    Map a loaded tool.yml (anchors resolved) into the editor's canonical dict,
    used both to render the form and as the dirty-state reference.
    """
    if not isinstance(raw, dict):
        raw = {}

    flows = normalize_flows(raw)

    raw_format = raw.get("format", {})
    if not isinstance(raw_format, dict):
        raw_format = {}

    raw_logs = raw_format.get("logs", {})
    logs = {}
    if isinstance(raw_logs, dict):
        for level, _label in LOG_LEVELS:
            logs[level] = _markers_to_list(_as_lines(raw_logs.get(level, [])).replace("\n", ","))

    raw_tags = raw_format.get("tags", {})
    tags = {}
    if isinstance(raw_tags, dict):
        for tag_name, markers in raw_tags.items():
            if isinstance(markers, (list, tuple)):
                tags[str(tag_name)] = [str(m) for m in markers if str(m).strip() != ""]
            elif markers is not None:
                tags[str(tag_name)] = _markers_to_list(markers)

    raw_replace = raw_format.get("replace", [])
    replace = []
    if isinstance(raw_replace, (list, tuple)):
        for entry in raw_replace:
            if isinstance(entry, dict):
                for pattern, repl in entry.items():
                    replace.append({"pattern": str(pattern), "replacement": "" if repl is None else str(repl)})

    return {
        "label": str(raw.get("label", "") or ""),
        "description": str(raw.get("description", "") or ""),
        "icon": str(raw.get("icon", "") or ""),
        "process_group": bool(raw.get("process_group", True)),
        "report_path": str(raw.get("report_path", "") or ""),
        "target_file": str(raw.get("target_file", "") or ""),
        "default_metrics_file": str(raw.get("default_metrics_file", "") or ""),
        "flows": flows,
        "format": {"logs": logs, "tags": tags, "replace": replace},
    }

def build_tool_settings(
    label, description, icon_value, process_group, report_path, target_file, default_metrics_file,
    flows, log_values, tag_names, tag_markers, replace_patterns, replace_repls,
):
    """
    Build the canonical settings dict from the raw field values gathered by the
    save callback. `flows` is the list returned by gather_flows() and
    `log_values` a {level: text} mapping.
    """
    logs = {level: _markers_to_list(log_values.get(level, "")) for level, _label in LOG_LEVELS}

    tags = {}
    nb_tags = len(tag_names) if isinstance(tag_names, list) else 0
    for idx in range(nb_tags):
        tag_name = str(tag_names[idx]).strip() if tag_names[idx] is not None else ""
        if tag_name == "":
            continue
        markers = _markers_to_list(tag_markers[idx] if idx < len(tag_markers) else "")
        if markers:
            tags[tag_name] = markers

    replace = []
    nb_replace = len(replace_patterns) if isinstance(replace_patterns, list) else 0
    for idx in range(nb_replace):
        pattern = str(replace_patterns[idx]).strip() if replace_patterns[idx] is not None else ""
        if pattern == "":
            continue
        replacement = replace_repls[idx] if idx < len(replace_repls) else ""
        replace.append({pattern: "" if replacement is None else str(replacement)})

    return {
        "label": label or "",
        "description": description or "",
        "icon": icon_value or "",
        "process_group": True if process_group else False,
        "report_path": report_path or "",
        "target_file": target_file or "",
        "default_metrics_file": default_metrics_file or "",
        "flows": flows,
        "format": {"logs": logs, "tags": tags, "replace": replace},
    }

def _flows_for_compare(flows):
    """
    Flows as they round-trip through save/load, so dirty detection ignores what
    is not written out (an empty step, a command typed under an inherited job
    type) instead of flagging a change that saving would not make.
    """
    compared = []
    for flow in flows or []:
        if not isinstance(flow, dict) or str(flow.get("name", "")).strip() == "":
            continue
        platforms = {}
        for platform, _label in PLATFORMS:
            jobs = {}
            for job, _l, _t, supports_steps in JOBS:
                spec = (flow.get("platforms", {}).get(platform, {}) or {}).get(job) or {}
                mode = spec.get("mode", "inherit")
                if mode == "command":
                    command = [c for c in (spec.get("command") or []) if str(c).strip() != ""]
                    if command:
                        jobs[job] = ["command", command]
                elif mode == "steps" and supports_steps:
                    steps = [
                        [
                            str(step.get("name", "")).strip(),
                            str(step.get("kind", "command")),
                            list((step.get("args") if step.get("kind") == "args" else step.get("command")) or []),
                            bool(step.get("default")),
                        ]
                        for step in (spec.get("steps") or [])
                        if str(step.get("name", "")).strip() != ""
                        and (step.get("args") if step.get("kind") == "args" else step.get("command"))
                    ]
                    session = spec.get("session") or {}
                    session = {part: list(session.get(part) or []) for part in ("command", "begin", "end")}
                    if steps or any(session.values()):
                        jobs[job] = ["steps", steps, session]
            if jobs:
                platforms[platform] = jobs
        compared.append({
            "name": str(flow.get("name", "")).strip(),
            "label": str(flow.get("label", "") or ""),
            "description": str(flow.get("description", "") or ""),
            "is_default": bool(flow.get("is_default")),
            "platforms": platforms,
        })
    return compared

def normalize_for_compare(settings):
    """
    Canonical dict as it round-trips through save/load, so dirty detection does
    not flag lossless differences (e.g. an empty replacement kept vs dropped).
    """
    n = normalize_tool_settings({}) if not isinstance(settings, dict) else dict(settings)
    # settings coming from build_tool_settings already match the canonical shape;
    # re-emit tags/replace/logs in a comparable form.
    return {
        "label": str(n.get("label", "") or ""),
        "description": str(n.get("description", "") or ""),
        "icon": str(n.get("icon", "") or ""),
        "process_group": bool(n.get("process_group", True)),
        "report_path": str(n.get("report_path", "") or ""),
        "target_file": str(n.get("target_file", "") or ""),
        "default_metrics_file": str(n.get("default_metrics_file", "") or ""),
        "flows": _flows_for_compare(n.get("flows", [])),
        "format": {
            "logs": {k: list(v) for k, v in (n.get("format", {}).get("logs", {}) or {}).items() if v},
            "tags": {k: list(v) for k, v in (n.get("format", {}).get("tags", {}) or {}).items() if v},
            "replace": _replace_pairs(n.get("format", {}).get("replace", [])),
        },
    }

def overlay_overrides(current, builtin):
    """
    What the workspace says about a built-in tool's settings: only the values
    that differ from the built-in definition, so a setting put back to what
    Odatix says drops out of the workspace file instead of being frozen into it.

    The flows are not part of it: the built-in ones belong to Odatix and the
    added ones are written on their own (see Tool.save_overlay).
    """
    builtin = builtin if isinstance(builtin, dict) else {}
    overrides = {}
    for key in OVERRIDABLE_KEYS:
        if current.get(key) != builtin.get(key):
            overrides[key] = current.get(key)

    current_format = current.get("format", {}) or {}
    builtin_format = builtin.get("format", {}) or {}
    fmt = {}
    for section_key in ("logs", "tags"):
        current_section = current_format.get(section_key, {}) or {}
        builtin_section = builtin_format.get(section_key, {}) or {}
        # Built-in entries first, so the file reads in the order the tool.yml it
        # overrides does; a marker list cleared by the user is kept as an empty
        # list, which is how the overlay says a built-in one no longer applies.
        keys = list(builtin_section) + [key for key in current_section if key not in builtin_section]
        section = {
            key: list(current_section.get(key) or [])
            for key in keys
            if list(current_section.get(key) or []) != list(builtin_section.get(key) or [])
        }
        if section:
            fmt[section_key] = section

    current_replace = current_format.get("replace", [])
    if _replace_pairs(current_replace) != _replace_pairs(builtin_format.get("replace", [])):
        fmt["replace"] = current_replace

    if fmt:
        overrides["format"] = fmt
    return overrides

def _replace_pairs(replace):
    """Normalize a replace list to a list of (pattern, replacement) pairs."""
    pairs = []
    for entry in replace or []:
        if isinstance(entry, dict):
            if "pattern" in entry:
                pairs.append([str(entry.get("pattern", "")), str(entry.get("replacement", "") or "")])
            else:
                for pattern, repl in entry.items():
                    pairs.append([str(pattern), str(repl or "")])
    return pairs


######################################
# UI Components
######################################

def tool_title(tool_name, overlay=False):
    title_buttons = html.Div(
        children=[
            ui.icon_button(
                id="button-open-tool-metric-editor",
                icon=icon("metrics", className="icon blue"),
                text="Edit Metrics",
                tooltip="Open the metrics editor for this tool",
                tooltip_options="bottom delay",
                color="default",
                link=f"/metric_editor?tool={tool_name}",
                multiline=False,
                width="135px",
            ),
            ui.save_button(
                id={"page": page_path, "action": "save-all"},
                tooltip="Save all changes",
                disabled=True,
            ),
        ],
        className="inline-flex-buttons",
    )

    return html.Div(
        html.Div(
            children=[
                html.Div(
                    children=[
                        html.Div(
                            children=[
                                dcc.Input(
                                    value=f"{tool_name}",
                                    type="text",
                                    id="tool-title",
                                    placeholder="Tool Name...",
                                    className="title-input",
                                    style={"width": "100%", "transform": "translate(-5px, 5px)"},
                                    disabled=overlay,
                                )
                            ],
                            id="tool-title-container",
                        ),
                        html.Div([title_buttons]),
                    ],
                    className="title-tile-flex",
                    style={"display": "flex", "alignItems": "center", "padding": "0px", "justifyContent": "space-between"},
                ),
                ui.back_button(link="/tools"),
            ],
            className="tile title",
            # The notice sits right under the title tile: they read as one block.
            style={"position": "relative", "borderRadius": "var(--card-border-radius) var(--card-border-radius) 0 0"}
            if overlay else {"position": "relative"},
        ),
        className="card-matrix config",
        style={"marginTop": "0px", "marginBottom": "0px" if overlay else "10px"},
    )

def tool_form_field(label, id, value="", tooltip="", placeholder="", disabled=False):
    return html.Div(
        children=[
            html.Label(label),
            ui.tooltip_icon(tooltip) if tooltip else None,
            dcc.Input(id=id, value=value, type="text", placeholder=placeholder, style={"width": "100%"},
                      disabled=disabled),
        ],
        style={"marginBottom": "12px"},
    )

def builtin_notice(tool_name):
    """
    What the editor can and cannot do to a built-in tool: its flows belong to
    Odatix, everything else can be overridden in the workspace.
    """
    return html.Div(html.Div(
        children=[
            html.Div(
                [
                    ui.badge("built-in", className="odx-flow-builtin-badge", color="warning"),
                    html.Span(
                        [
                            html.Strong(tool_name),
                            " tool definition is shipped with Odatix. Its settings, log formatting and metrics can be overridden in your workspace, "
                            "and you can add flows of your own to it.  ",
                            html.Br(),
                            "However, the flows it already declares stay read-only: duplicate one to start from what it does. ",
                            "Use the reset buttons to put a section back to what Odatix defines.",
                        ],
                        style={"transform": "translateX(4px)"},
                    ),
                ],
                className="odx-notice-text",
                style={"transform": "translateX(-4px)"},
            ),

        ],
        # "tile title" only for its width rules: the notice must always be as
        # wide as the title tile above it, including in the responsive breakpoints.
        className="odx-notice tile title",
        # No "auto" side margins: when the tile is wider than the grid track they
        # resolve to 0 and shift the notice right of the title tile above it.
        style={"margin": "-20px 0 32px", "borderRadius": "0 0 var(--card-border-radius) var(--card-border-radius)"},
    ), className="card-matrix config")

def reset_builtin_button(section, tooltip):
    """The button dropping what the workspace says about one section of a
    built-in tool, putting it back to what Odatix defines."""
    return ui.icon_button(
        id={"type": "tool-reset-builtin", "section": section},
        icon=icon("reset", className="icon default"),
        text="Reset",
        tooltip=tooltip,
        tooltip_options="bottom delay",
        color="default",
        width="auto",
        bold=False,
    )

def tile_head(title, reset_section=None, reset_tooltip=""):
    """The heading of a settings tile, with its reset button when the tool is a
    built-in one and the section can be put back to the built-in state."""
    return html.Div(
        children=[
            html.H3(title, style={"margin": "0"}),
            reset_builtin_button(reset_section, reset_tooltip) if reset_section else None,
        ],
        style={"display": "flex", "alignItems": "center", "justifyContent": "space-between",
               "gap": "10px", "marginBottom": "14px", "minHeight": "26px"},
    )

def tool_form(settings, tool_name="", overlay=False):
    target_placeholder = f"target_{tool_name}.yml" if tool_name else "target_<tool>.yml"

    metadata_tile = html.Div(
        [
            tile_head("Tool Metadata", "metadata" if overlay else None,
                      "Reset the metadata to what Odatix defines for this built-in tool"),
            tool_form_field("Display Name", "tool-label", value=settings.get("label", ""),
                            tooltip="Display name shown in the GUI (defaults to the tool identifier)."),
            tool_form_field("Description", "tool-description", value=settings.get("description", ""),
                            tooltip="Short description shown on the tool selection page."),
            tool_form_field("Icon", "tool-icon", value=settings.get("icon", ""),
                            placeholder="assets/icons/my_tool.png",
                            tooltip="Optional icon path (relative to the GUI assets) shown on the tool selection page."),
        ],
        className="tile config",
    )

    behaviour_tile = html.Div(
        [
            tile_head("Behaviour", "behaviour" if overlay else None,
                      "Reset the behaviour to what Odatix defines for this built-in tool"),
            html.Div(
                children=[
                    dcc.Checklist(
                        value=[True] if settings.get("process_group", True) else [],
                        id="tool-process-group",
                        className="checklist-switch",
                        options=[{"label": "Group processes", "value": True}],
                        style={"marginBottom": "12px", "marginTop": "5px", "display": "inline-block"},
                    ),
                    ui.tooltip_icon("Group the tool's child processes so they can be terminated together."),
                ],
                style={"marginBottom": "12px"},
            ),
            tool_form_field("Report Path", "tool-report-path", value=settings.get("report_path", ""),
                            tooltip="Optional path (relative to the run directory) where the tool writes its reports."),
            tool_form_field("Target Definition File", "tool-target-file",
                            value=settings.get("target_file", ""),
                            placeholder=target_placeholder,
                            tooltip="Name of the target definition file for this tool (defaults to target_<tool>.yml). "
                                    "Looked up in the workspace target directory, then in odatix_userconfig."),
            tool_form_field("Default Metrics File", "tool-default-metrics-file",
                            value=settings.get("default_metrics_file", ""),
                            placeholder="$tool_path/metrics.yml",
                            tooltip="Metrics definition file used at export time. Use $tool_path to point inside the tool directory."),
        ],
        className="tile config",
    )

    return html.Div(
        children=[metadata_tile, behaviour_tile],
        className="tiles-container config",
        style={"marginTop": "-10px", "marginBottom": "20px"},
    )

######################################
# Flows
######################################
# Every flow is rendered at once, so what the user typed lives in the page and
# never has to be mirrored into a store. Component ids carry the flow (and, for
# a step, the step) they belong to: "f000" / "s000", zero padded so the order
# dash returns pattern matching values in is the order they are displayed in.

def _uid(prefix, index):
    return f"{prefix}{index:03d}"

def _hidden(shown):
    """Keep a body in the page but out of sight (see job_editor)."""
    return {} if shown else {"display": "none"}

def step_row(flow_uid, platform, job, step_uid, name="", command="", is_default=False, locked=False, kind="command"):
    """
    One step of a job type. "Default" marks the step the flow stops at when a run
    does not say where to: the later steps stay declared, and are only run when
    asked for (see odatix.lib.eda_tools.get_default_step). No step marked means
    the flow runs to its end.

    A step is either a process of its own ("command") or a fragment of the job
    type's session ("args"), which is what lets the steps of a run share a single
    process of the tool. Which one it is is a hidden value: it comes from the
    file, and a step added to a job type that opens a session joins it.
    """
    return html.Div(
        children=[
            html.Div(
                children=[
                    dcc.Input(
                        id={"type": "tool-step-name", "flow": flow_uid, "platform": platform, "job": job, "step": step_uid},
                        value=name,
                        type="text",
                        placeholder="Step name...",
                        className="odx-jobstep-name",
                        disabled=locked,
                    ),
                    # Like the default flow: a hidden value the server owns, so
                    # two steps can never end up marked at once.
                    dcc.Input(
                        id={"type": "tool-step-default", "flow": flow_uid, "platform": platform, "job": job, "step": step_uid},
                        value="1" if is_default else "",
                        type="hidden",
                    ),
                    dcc.Input(
                        id={"type": "tool-step-kind", "flow": flow_uid, "platform": platform, "job": job, "step": step_uid},
                        value=kind,
                        type="hidden",
                    ),
                    html.Button(
                        "Default",
                        id={"type": "tool-step-set-default", "flow": flow_uid, "platform": platform, "job": job, "step": step_uid},
                        n_clicks=0,
                        disabled=locked,
                        className="odx-flow-default-chip" + (" active" if is_default else ""),
                        title=(
                            "The last step run when nothing else is asked for. "
                            "Click again to unmark it and run the whole flow by default."
                        ),
                    ),
                    *([] if locked else [
                        ui.duplicate_button(
                            id={"type": "tool-step-duplicate", "flow": flow_uid, "platform": platform, "job": job, "step": step_uid},
                            tooltip="Duplicate this step",
                        ),
                        ui.delete_button(
                            id={"type": "tool-step-delete", "flow": flow_uid, "platform": platform, "job": job, "step": step_uid},
                            tooltip="Delete this step",
                        ),
                    ]),
                ],
                className="odx-jobstep-head",
            ),
            dcc.Textarea(
                id={"type": "tool-step-cmd", "flow": flow_uid, "platform": platform, "job": job, "step": step_uid},
                value=command,
                placeholder=(
                    "One argument per line, added to the session"
                    if kind == "args" else "One argument per line"
                ),
                className="auto-resize-textarea",
                disabled=locked,
            ),
        ],
        className="odx-jobstep",
    )

def session_editor(flow_uid, platform, job, session, locked=False):
    """
    How a job type opens the tool: the command launching it, and what is run on
    opening and on closing whatever steps run in between.

    Declaring a command here is what makes the steps of a run share a single
    process: they are then sourced by that one session instead of opening and
    closing the tool once each. Leaving it empty makes every step a process of
    its own.
    """
    def field(kind, label_text, tooltip_text, value):
        return html.Div(
            children=[
                ui.caption(label_text, tooltip=tooltip_text),
                dcc.Textarea(
                    id={"type": "tool-session-" + kind, "flow": flow_uid, "platform": platform, "job": job},
                    value=_as_lines(value),
                    placeholder="One argument per line",
                    className="auto-resize-textarea",
                    disabled=locked,
                ),
            ],
            className="odx-job-session-field",
        )

    return html.Div(
        children=[
            field("cmd", "Session", "How the tool is opened for this job type, once per run", session.get("command", [])),
            field("begin", "On opening", "Added right after the session is opened, before any step", session.get("begin", [])),
            field("end", "On closing", "Added after the last step of the run, before the tool exits", session.get("end", [])),
        ],
        className="odx-job-session",
    )


def job_editor(flow_uid, platform, job, label, tooltip, supports_steps, spec, is_default, locked=False):
    """
    One job type of one platform of one flow: what it runs, and how.

    Both the one shot command and the steps are always rendered, the inactive
    one hidden, so switching between them (or to "inherited" and back) keeps
    what was typed instead of throwing it away.
    """
    mode = spec.get("mode", "inherit")
    options = MODE_OPTIONS_DEFAULT if is_default else MODE_OPTIONS_FLOW
    if not supports_steps:
        options = [option for option in options if option["value"] != "steps"]
        if mode == "steps":
            mode = "command"

    bodies = [
        html.Div(
            "Inherited from the default flow." if not is_default else "This tool does not run this job type.",
            className="odx-job-inherited",
            style=_hidden(mode == "inherit"),
        ),
        html.Div(
            dcc.Textarea(
                id={"type": "tool-cmd", "flow": flow_uid, "platform": platform, "job": job},
                value=_as_lines(spec.get("command", [])),
                placeholder="One argument per line",
                className="auto-resize-textarea",
                disabled=locked,
            ),
            style=_hidden(mode == "command"),
        ),
    ]

    if supports_steps:
        steps = spec.get("steps") or []
        session = spec.get("session") or {}
        bodies.append(
            html.Div(
                children=[
                    session_editor(flow_uid, platform, job, session, locked=locked),
                    *[
                        step_row(flow_uid, platform, job, _uid("s", index),
                                 name=step.get("name", ""),
                                 command=_as_lines(step.get("args") if step.get("kind") == "args" else step.get("command", [])),
                                 is_default=bool(step.get("default")), locked=locked,
                                 kind=step.get("kind", "command"))
                        for index, step in enumerate(steps)
                    ],
                    *([] if locked else [
                        html.Button(
                            "+ Add step",
                            id={"type": "tool-step-new", "flow": flow_uid, "platform": platform, "job": job},
                            n_clicks=0,
                            className="odx-jobstep-add",
                        ),
                    ]),
                ],
                className="odx-jobsteps",
                style=_hidden(mode == "steps"),
            )
        )

    return html.Div(
        children=[
            html.Div(
                children=[
                    ui.caption(label, tooltip=tooltip),
                    dcc.RadioItems(
                        id={"type": "tool-job-mode", "flow": flow_uid, "platform": platform, "job": job},
                        options=[dict(option, disabled=True) for option in options] if locked else options,
                        value=mode,
                        className="odx-chips",
                    ),
                ],
                className="odx-job-head",
            ),
            *bodies,
        ],
        className="odx-job",
    )

def flow_card(flow_uid, flow, lock_default=False):
    """
    One flow. A built-in flow of a built-in tool is shown locked: it belongs to
    Odatix, and what the workspace adds on top of it is a flow of its own
    (duplicate it to start from what it does).

    A card can be folded down to its head, so a tool with several flows stays
    readable. Whether it is folded is held in the page like the other states the
    server owns, so it survives the re-render a structural change triggers.
    """
    is_default = bool(flow.get("is_default"))
    locked = bool(flow.get("builtin"))
    collapsed = bool(flow.get("collapsed"))
    platforms = flow.get("platforms", {})

    head = html.Div(
        children=[
            ui.icon_button(
                id={"type": "tool-flow-toggle", "flow": flow_uid},
                icon=icon(
                    "more",
                    className="icon normal rotate" + ("" if collapsed else " rotated"),
                    id={"type": "tool-flow-toggle-icon", "flow": flow_uid},
                ),
                color="default",
                tooltip="Fold or unfold this flow",
                tooltip_options="bottom auto delay",
            ),
            dcc.Input(
                id={"type": "tool-flow-collapsed", "flow": flow_uid},
                value="1" if collapsed else "",
                type="hidden",
            ),
            dcc.Input(
                id={"type": "tool-flow-name", "flow": flow_uid},
                value=flow.get("name", ""),
                type="text",
                placeholder="Flow name...",
                className="odx-card-name",
                disabled=locked,
            ),
            # The default flow is held by the page, not by a checkbox per card:
            # a single hidden value the server owns, so two flows can never end
            # up marked as the default at once.
            dcc.Input(
                id={"type": "tool-flow-default", "flow": flow_uid},
                value="1" if is_default else "",
                type="hidden",
            ),
            dcc.Input(
                id={"type": "tool-flow-builtin", "flow": flow_uid},
                value="1" if locked else "",
                type="hidden",
            ),
            html.Button(
                "Default",
                id={"type": "tool-flow-set-default", "flow": flow_uid},
                n_clicks=0,
                disabled=is_default or lock_default,
                className="odx-flow-default-chip" + (" active" if is_default else ""),
                title=(
                    "Built-in tools default flow cannot be changed."
                    if lock_default and not is_default
                    else "The flow used when none is asked for. Its commands are the ones the other flows start from."
                ),
            ),
            html.Div(style={"flex": "1"}),
            *([ui.badge("read-only", className="odx-flow-builtin-badge", color="warning")] if locked else []),
            ui.duplicate_button(id={"type": "tool-flow-duplicate", "flow": flow_uid}, tooltip="Duplicate this flow"),
            *([] if locked else [
                ui.delete_button(id={"type": "tool-flow-delete", "flow": flow_uid}, tooltip="Delete this flow"),
            ]),
        ],
        className="odx-card-head odx-flow-head",
    )

    metadata = html.Div(
        children=[
            ui.form_field(
                "Label", {"type": "tool-flow-label", "flow": flow_uid},
                value=flow.get("label", ""), placeholder=flow.get("name", ""),
                tooltip="Display name of the flow in the GUI (defaults to its name).",
                disabled=locked,
            ),
            ui.form_field(
                "Description", {"type": "tool-flow-description", "flow": flow_uid},
                value=flow.get("description", ""),
                tooltip="What this flow does differently, shown on the tool selection page.",
                disabled=locked,
            ),
        ],
        className="odx-field-row",
    )

    platform_panels = [
        ui.panel(
            title=platform_label,
            body=[
                job_editor(flow_uid, platform, job, label, tooltip, supports_steps,
                           platforms.get(platform, {}).get(job, {}), is_default, locked=locked)
                for job, label, tooltip, supports_steps in JOBS
            ],
        )
        for platform, platform_label in PLATFORMS
    ]

    body = html.Div(
        children=[metadata, ui.grid(platform_panels, className="wide top")],
        id={"type": "tool-flow-body", "flow": flow_uid},
        className="animated-section" + (" hide" if collapsed else ""),
    )

    return html.Div(
        children=[head, body],
        id={"type": "tool-flow-card", "flow": flow_uid},
        className="odx-panel padded odx-flow-card"
                  + (" default" if is_default else "")
                  + (" locked" if locked else "")
                  + (" collapsed" if collapsed else ""),
    )

def flow_cards(flows, lock_default=False):
    """The whole flows section: one card per flow, plus the "add a flow" card."""
    cards = [flow_card(_uid("f", index), flow, lock_default=lock_default) for index, flow in enumerate(flows)]
    cards.append(ui.add_card(id="tool-flow-new", text="Add a flow", className="odx-flow-add"))
    return cards

def new_flow(name):
    """A flow that declares nothing yet: it inherits the default flow as is."""
    return {"name": name, "label": "", "description": "", "is_default": False,
            "builtin": False, "collapsed": False, "platforms": _empty_platforms()}

def _new_step(spec):
    """
    An empty step of a job type. It joins the job type's session when it opens
    one, so the steps of a run keep sharing a single process of the tool.
    """
    in_session = bool(((spec or {}).get("session") or {}).get("command"))
    return {
        "name": "",
        "kind": "args" if in_session else "command",
        "command": [],
        "args": [],
        "default": False,
    }

def _unique_flow_name(base, taken):
    name = base
    index = 2
    while name in taken:
        name = f"{base}_{index}"
        index += 1
    return name


######################################
# Reading the flows back from the page
######################################

def _by_uid(ids, values):
    """{flow uid: value} for a one-per-flow pattern matching input."""
    return {i.get("flow"): v for i, v in zip(ids or [], values or []) if isinstance(i, dict)}

def _by_job(ids, values):
    """{(flow uid, platform, job): value} for a one-per-job pattern matching input."""
    return {
        (i.get("flow"), i.get("platform"), i.get("job")): v
        for i, v in zip(ids or [], values or []) if isinstance(i, dict)
    }

def _single_default(steps):
    """
    Keep at most one step marked as the default one of its job type: the last one
    marked. Like the default flow, the mark is a hidden value only the server
    writes, so this is a safety net rather than a rule to enforce.
    """
    marked = [index for index, step in enumerate(steps) if step.get("default")]
    for index in marked[:-1]:
        steps[index]["default"] = False
    return steps

def gather_flows(
    flow_ids, flow_names, flow_labels, flow_descriptions, flow_defaults, flow_builtins, flow_collapsed,
    mode_ids, mode_values, cmd_ids, cmd_values,
    session_ids, session_cmds, session_begins, session_ends,
    step_ids, step_names, step_cmds, step_defaults, step_kinds,
):
    """
    Rebuild the flows list from what is currently in the page. Used both to save
    and to re-render the section after a structural change, so an edit in one
    flow survives adding, duplicating or deleting another.

    The command and the steps of a job type are both read whatever its mode is:
    only the mode decides what gets written out, so switching a job type back
    and forth does not lose what the other choice held.
    """
    names = _by_uid(flow_ids, flow_names)
    labels = _by_uid(flow_ids, flow_labels)
    descriptions = _by_uid(flow_ids, flow_descriptions)
    defaults = _by_uid(flow_ids, flow_defaults)
    builtins = _by_uid(flow_ids, flow_builtins)
    collapsed = _by_uid(flow_ids, flow_collapsed)
    modes = _by_job(mode_ids, mode_values)
    commands = _by_job(cmd_ids, cmd_values)
    session_commands = _by_job(session_ids, session_cmds)
    session_begins_by_job = _by_job(session_ids, session_begins)
    session_ends_by_job = _by_job(session_ids, session_ends)

    steps = {}
    for step_id, step_name, step_cmd, step_default, step_kind in zip(
        step_ids or [], step_names or [], step_cmds or [], step_defaults or [], step_kinds or [],
    ):
        if not isinstance(step_id, dict):
            continue
        key = (step_id.get("flow"), step_id.get("platform"), step_id.get("job"))
        steps.setdefault(key, []).append((step_id.get("step"), step_name, step_cmd, step_default, step_kind))

    flows = []
    for uid in sorted(names):
        platforms = {}
        for platform, _platform_label in PLATFORMS:
            jobs = {}
            for job, _label, _tooltip, supports_steps in JOBS:
                key = (uid, platform, job)
                mode = modes.get(key) or "inherit"
                if mode == "steps" and not supports_steps:
                    mode = "command"
                jobs[job] = {
                    "mode": mode,
                    "command": _lines_to_list(commands.get(key, "")),
                    "session": {
                        "command": _lines_to_list(session_commands.get(key, "")),
                        "begin": _lines_to_list(session_begins_by_job.get(key, "")),
                        "end": _lines_to_list(session_ends_by_job.get(key, "")),
                    },
                    "steps": _single_default([
                        {
                            "name": str(step_name or "").strip(),
                            "kind": "args" if step_kind == "args" else "command",
                            # One textarea holds both: which key it is written to
                            # is what the step's kind says.
                            "command": [] if step_kind == "args" else _lines_to_list(step_cmd),
                            "args": _lines_to_list(step_cmd) if step_kind == "args" else [],
                            "default": bool(step_default),
                        }
                        for _step_uid, step_name, step_cmd, step_default, step_kind in sorted(steps.get(key, []))
                    ]),
                }
            platforms[platform] = jobs
        flows.append({
            "uid": uid,
            "name": str(names.get(uid) or "").strip(),
            "label": str(labels.get(uid) or ""),
            "description": str(descriptions.get(uid) or ""),
            "is_default": bool(defaults.get(uid)),
            "builtin": bool(builtins.get(uid)),
            "collapsed": bool(collapsed.get(uid)),
            "platforms": platforms,
        })

    # A tool has exactly one default flow: the commands the others start from.
    # The page holds it in a hidden value only the server writes, so this is a
    # safety net rather than a rule to enforce.
    seen_default = False
    for flow in flows:
        if flow["is_default"] and not seen_default:
            seen_default = True
        else:
            flow["is_default"] = False
    if flows and not seen_default:
        flows[0]["is_default"] = True
    return flows

# The pattern matching dependencies holding the flows, in the order the
# callbacks using them take their arguments (dash hands them over in
# declaration order). Ids and server owned values are always read as State;
# `text_dep` and `choice_dep` say which of the rest wake the callback up: the
# structural callback only re-renders when a job type is switched between a
# command and steps, while the save callback watches everything to keep its
# dirty state fresh.
def flow_dependencies(text_dep, choice_dep):
    job_pattern = {"flow": dash.ALL, "platform": dash.ALL, "job": dash.ALL}
    step_pattern = dict(job_pattern, step=dash.ALL)
    return [
        State({"type": "tool-flow-name", "flow": dash.ALL}, "id"),
        text_dep({"type": "tool-flow-name", "flow": dash.ALL}, "value"),
        text_dep({"type": "tool-flow-label", "flow": dash.ALL}, "value"),
        text_dep({"type": "tool-flow-description", "flow": dash.ALL}, "value"),
        # Hidden, server owned values: they only ever change with a re-render.
        State({"type": "tool-flow-default", "flow": dash.ALL}, "value"),
        State({"type": "tool-flow-builtin", "flow": dash.ALL}, "value"),
        State({"type": "tool-flow-collapsed", "flow": dash.ALL}, "value"),
        State(dict(job_pattern, type="tool-job-mode"), "id"),
        choice_dep(dict(job_pattern, type="tool-job-mode"), "value"),
        State(dict(job_pattern, type="tool-cmd"), "id"),
        text_dep(dict(job_pattern, type="tool-cmd"), "value"),
        State(dict(job_pattern, type="tool-session-cmd"), "id"),
        text_dep(dict(job_pattern, type="tool-session-cmd"), "value"),
        text_dep(dict(job_pattern, type="tool-session-begin"), "value"),
        text_dep(dict(job_pattern, type="tool-session-end"), "value"),
        State(dict(step_pattern, type="tool-step-name"), "id"),
        text_dep(dict(step_pattern, type="tool-step-name"), "value"),
        text_dep(dict(step_pattern, type="tool-step-cmd"), "value"),
        State(dict(step_pattern, type="tool-step-default"), "value"),
        State(dict(step_pattern, type="tool-step-kind"), "value"),
    ]


######################################
# Adding, duplicating and deleting flows and steps
######################################

def _flow_index(flows, uid):
    for index, flow in enumerate(flows):
        if flow.get("uid") == uid:
            return index
    return None

def _step_index(step_ids, key, step_uid):
    """Position of a step in its job, from the ids currently in the page."""
    uids = sorted(
        i.get("step") for i in step_ids or []
        if isinstance(i, dict) and (i.get("flow"), i.get("platform"), i.get("job")) == key
    )
    return uids.index(step_uid) if step_uid in uids else None

@dash.callback(
    Output({"type": "tool-flow-body", "flow": dash.MATCH}, "className"),
    Output({"type": "tool-flow-toggle-icon", "flow": dash.MATCH}, "className"),
    Output({"type": "tool-flow-card", "flow": dash.MATCH}, "className"),
    Output({"type": "tool-flow-collapsed", "flow": dash.MATCH}, "value"),
    Input({"type": "tool-flow-toggle", "flow": dash.MATCH}, "n_clicks"),
    State({"type": "tool-flow-collapsed", "flow": dash.MATCH}, "value"),
    State({"type": "tool-flow-card", "flow": dash.MATCH}, "className"),
    prevent_initial_call=True,
)
def toggle_flow(n_clicks, collapsed, card_class):
    """
    Fold a flow card down to its head, or unfold it. The new state is written
    back to the hidden value the card carries, so a re-render of the section
    (a flow added, a job type switched to steps) keeps every card as it was.
    """
    if not n_clicks:
        return (dash.no_update,) * 4

    collapsed = not collapsed
    classes = [name for name in str(card_class or "").split() if name != "collapsed"]
    if collapsed:
        classes.append("collapsed")
    return (
        "animated-section hide" if collapsed else "animated-section",
        "icon normal rotate" if collapsed else "icon normal rotate rotated",
        " ".join(classes),
        "1" if collapsed else "",
    )

@dash.callback(
    Output("tool-flows-container", "children", allow_duplicate=True),
    # A flow added, duplicated or deleted changes the settings without any field
    # changing, and the save callback cannot watch the section itself without
    # closing a dependency cycle through the url: mark the button from here.
    Output({"page": page_path, "action": "save-all"}, "className", allow_duplicate=True),
    Output({"page": page_path, "action": "save-all"}, "data-tooltip", allow_duplicate=True),
    Input("tool-flow-new", "n_clicks"),
    Input({"type": "tool-flow-duplicate", "flow": dash.ALL}, "n_clicks"),
    Input({"type": "tool-flow-delete", "flow": dash.ALL}, "n_clicks"),
    Input({"type": "tool-flow-set-default", "flow": dash.ALL}, "n_clicks"),
    Input({"type": "tool-step-new", "flow": dash.ALL, "platform": dash.ALL, "job": dash.ALL}, "n_clicks"),
    Input({"type": "tool-step-duplicate", "flow": dash.ALL, "platform": dash.ALL, "job": dash.ALL, "step": dash.ALL}, "n_clicks"),
    Input({"type": "tool-step-delete", "flow": dash.ALL, "platform": dash.ALL, "job": dash.ALL, "step": dash.ALL}, "n_clicks"),
    Input({"type": "tool-step-set-default", "flow": dash.ALL, "platform": dash.ALL, "job": dash.ALL, "step": dash.ALL}, "n_clicks"),
    *flow_dependencies(State, Input),
    State("tool-edit-overlay", "data"),
    prevent_initial_call=True,
)
def update_flows(
    new_click, duplicate_clicks, delete_clicks, set_default_clicks,
    step_new_clicks, step_duplicate_clicks, step_delete_clicks, step_set_default_clicks,
    flow_ids, flow_names, flow_labels, flow_descriptions, flow_defaults, flow_builtins, flow_collapsed,
    mode_ids, mode_values, cmd_ids, cmd_values,
    session_ids, session_cmds, session_begins, session_ends,
    step_ids, step_names, step_cmds, step_defaults, step_kinds, overlay,
):
    """
    Apply a structural change (a flow or a step added, duplicated or deleted, a
    new default flow, a job type switched between a command and steps) and
    re-render the whole section from what the page currently holds, so every
    unsaved edit is carried over.
    """
    trigger = ctx.triggered_id
    trigger_value = ctx.triggered[0]["value"] if ctx.triggered else None
    action = trigger if isinstance(trigger, str) else (trigger or {}).get("type")

    # A click is only an action once the button has actually been clicked;
    # a value of 0 is a button that was just rendered.
    if action in (
        "tool-flow-new", "tool-flow-duplicate", "tool-flow-delete", "tool-flow-set-default",
        "tool-step-new", "tool-step-duplicate", "tool-step-delete", "tool-step-set-default",
    ) and not trigger_value:
        return dash.no_update, dash.no_update, dash.no_update

    flows = gather_flows(
        flow_ids, flow_names, flow_labels, flow_descriptions, flow_defaults, flow_builtins, flow_collapsed,
        mode_ids, mode_values, cmd_ids, cmd_values,
        session_ids, session_cmds, session_begins, session_ends,
        step_ids, step_names, step_cmds, step_defaults, step_kinds,
    )
    taken = {flow["name"] for flow in flows}

    if action == "tool-flow-new":
        flows.append(new_flow(_unique_flow_name("new_flow", taken)))

    elif action == "tool-flow-duplicate":
        index = _flow_index(flows, trigger.get("flow"))
        if index is not None:
            copy = copy_module.deepcopy(flows[index])
            copy["name"] = _unique_flow_name(f"{flows[index]['name'] or 'flow'}_copy", taken)
            copy["is_default"] = False
            # A copy belongs to the workspace, even when what it copies does not,
            # and is unfolded whatever the flow it copies is: it is there to be
            # worked on.
            copy["builtin"] = False
            copy["collapsed"] = False
            flows.insert(index + 1, copy)

    elif action == "tool-flow-delete":
        # A tool always runs something: its last flow cannot be deleted.
        index = _flow_index(flows, trigger.get("flow"))
        if index is not None and len(flows) > 1:
            was_default = flows[index]["is_default"]
            flows.pop(index)
            if was_default:
                flows[0]["is_default"] = True

    elif action == "tool-flow-set-default":
        # Exactly one flow is the default: the one that was just picked.
        if _flow_index(flows, trigger.get("flow")) is not None:
            for flow in flows:
                flow["is_default"] = flow.get("uid") == trigger.get("flow")

    elif action == "tool-job-mode":
        # Switching a job type to steps starts it off with one step to fill in.
        index = _flow_index(flows, trigger.get("flow"))
        if index is not None and trigger_value == "steps":
            spec = flows[index]["platforms"][trigger.get("platform")][trigger.get("job")]
            if not spec["steps"]:
                spec["steps"] = [_new_step(spec)]

    elif action in ("tool-step-new", "tool-step-duplicate", "tool-step-delete", "tool-step-set-default"):
        index = _flow_index(flows, trigger.get("flow"))
        if index is not None:
            spec = flows[index]["platforms"][trigger.get("platform")][trigger.get("job")]
            key = (trigger.get("flow"), trigger.get("platform"), trigger.get("job"))
            if action == "tool-step-new":
                spec["steps"].append(_new_step(spec))
            else:
                step_index = _step_index(step_ids, key, trigger.get("step"))
                if step_index is not None and step_index < len(spec["steps"]):
                    if action == "tool-step-delete":
                        spec["steps"].pop(step_index)
                    elif action == "tool-step-set-default":
                        # At most one step is the default one, and clicking the
                        # one already marked unmarks it: the flow then runs to
                        # its end unless a run says otherwise.
                        was_default = spec["steps"][step_index].get("default")
                        for position, step in enumerate(spec["steps"]):
                            step["default"] = (position == step_index) and not was_default
                    else:
                        copy = copy_module.deepcopy(spec["steps"][step_index])
                        copy["name"] = f"{copy['name']}_copy" if copy["name"] else ""
                        # The copy is a new step, not the one the flow stops at.
                        copy["default"] = False
                        spec["steps"].insert(step_index + 1, copy)

    return (
        flow_cards(flows, lock_default=bool(overlay)),
        "color-button warning icon-button tooltip bottom small",
        "Unsaved changes!",
    )

def log_formatting_tiles(settings, overlay=False):
    logs = settings.get("format", {}).get("logs", {})
    tags = settings.get("format", {}).get("tags", {})

    log_tile = html.Div(
        [
            tile_head("Log Levels", "logs" if overlay else None,
                      "Reset the log levels to what Odatix defines for this built-in tool"),
            html.Div(
                "Comma-separated markers: a log line containing one of them is colored with the level.",
                style={"fontSize": "0.85em", "opacity": "0.7", "marginBottom": "10px"},
            ),
            *[
                tool_form_field(
                    label, f"tool-log-{level}",
                    value=", ".join(logs.get(level, [])),
                    placeholder="<error>, ERROR:",
                )
                for level, label in LOG_LEVELS
            ],
        ],
        className="tile config",
    )

    tag_rows = [tag_marker_row(name, ", ".join(tags.get(name, []))) for name in TAG_NAMES]
    tag_columns_split = (len(tag_rows) + 1) // 2

    tags_tile = html.Div(
        [
            tile_head("Log Format Tags", "tags" if overlay else None,
                      "Reset the format tags to what Odatix defines for this built-in tool"),
            html.Div(
                "Marker(s) used in the tool output for each style/color, replaced by the "
                "matching ANSI escape code. Comma-separate several markers; leave empty to disable a tag.",
                style={"fontSize": "0.85em", "opacity": "0.7", "marginBottom": "10px"},
            ),
            html.Div(
                [
                    html.Div(tag_rows[:tag_columns_split], style={"flex": "1 1 0", "minWidth": "0"}),
                    html.Div(tag_rows[tag_columns_split:], style={"flex": "1 1 0", "minWidth": "0"}),
                ],
                style={"display": "flex", "gap": "20px"},
            ),
        ],
        className="tile config",
    )

    return html.Div(
        children=[log_tile, tags_tile],
        className="tiles-container config",
        style={"marginBottom": "20px"},
    )

def tag_marker_row(name, markers=""):
    # Fixed row: the tag name (an ANSI style/color) + its editable marker(s).
    return html.Div(
        [
            html.Label(name, style={"flex": "0 0 100px", "fontWeight": "600", "fontSize": "0.9em"}),
            dcc.Input(
                value=markers,
                type="text",
                placeholder=f"<{name}>",
                id={"type": "tool-tag-markers", "name": name},
                className="value-input",
                style={"flex": "1 1 auto", "minWidth": "0", "marginBottom": "0"},
            ),
        ],
        style={"display": "flex", "alignItems": "center", "gap": "10px", "marginBottom": "6px"},
    )


######################################
# Tag and Replace cards (dynamic)
######################################

def replace_card(name, pattern="", replacement=""):
    return html.Div(
        [
            html.Div([
                html.Label("Pattern (regex)", style={"fontWeight": "bold", "fontSize": "0.95em"}),
                dcc.Input(
                    value=pattern,
                    type="text",
                    placeholder="(Slack \\(VIOLATED\\))",
                    id={"type": "tool-replace-pattern", "name": name},
                    className="value-input",
                    style={"width": "100%", "marginBottom": "6px"},
                ),
                html.Label("Replacement", style={"fontWeight": "bold", "fontSize": "0.95em"}),
                dcc.Input(
                    value=replacement,
                    type="text",
                    placeholder="<red>$1<end>",
                    id={"type": "tool-replace-repl", "name": name},
                    className="value-input",
                    style={"width": "100%", "marginBottom": "6px"},
                ),
            ]),
            html.Div([
                html.Div(),
                html.Div([
                    ui.duplicate_button(id={"type": "tool-replace-duplicate", "name": name}),
                    ui.delete_button(id={"type": "tool-replace-delete", "name": name}),
                ], style={"display": "flex", "flexDirection": "row", "alignItems": "center", "gap": "5px"}),
            ], style={"marginTop": "8px", "display": "flex", "flexDirection": "row", "width": "100%", "justifyContent": "space-between"}),
        ],
        className="card configs",
        id={"type": "tool-replace-card", "name": name},
        style={"padding": "10px", "margin": "5px", "display": "inline-block", "verticalAlign": "top"},
    )

def add_card(prefix, text):
    """The "add one more" card."""
    return html.Div(
        html.Div(
            html.Div(
                children=[
                    html.Div(text, style={"fontWeight": "bold", "fontSize": "1.2em", "paddingTop": "20px"}),
                    html.Div("+", style={"fontSize": "2.5em", "lineHeight": "80px", "height": "80px"}),
                ],
                style={"display": "flex", "flexDirection": "column", "alignItems": "center", "justifyContent": "center", "height": "100%"}
            ),
            id=f"{prefix}-new",
            n_clicks=0,
            style={"textDecoration": "none", "height": "100%"},
        ),
        className="card configs add hover",
        id=f"{prefix}-add-card",
        style={"padding": "10px", "margin": "5px", "verticalAlign": "top", "boxSizing": "border-box",
               "display": "inline-block"},
    )

def replace_cards_from_list(replace):
    cards = []
    for idx, pair in enumerate(_replace_pairs(replace)):
        cards.append(replace_card(f"rep{idx + 1}", pattern=pair[0], replacement=pair[1]))
    cards.append(add_card("tool-replace", "Add replacement"))
    return cards

def replace_section_title(overlay=False):
    """The heading of the log replacements section: they are cards, not a tile,
    so their reset button lives in the title tile."""
    return ui.title_tile(
        text="Log Replacements", id="tool-replace-title",
        tooltip="Regular expressions applied to the tool output to recolor or rewrite matching text.",
        buttons=reset_builtin_button(
            "replace", "Reset the replacements to what Odatix defines for this built-in tool",
        ) if overlay else html.Div(),
    )


######################################
# Card add/delete callbacks
######################################

def _strip_add_card(cards, add_card_id):
    if cards and isinstance(cards[-1], dict) and cards[-1].get("props", {}).get("id") == add_card_id:
        return cards[:-1]
    return cards

@dash.callback(
    Output("tool-replace-cards-row", "children", allow_duplicate=True),
    Input("tool-replace-new", "n_clicks"),
    Input({"type": "tool-replace-duplicate", "name": dash.ALL}, "n_clicks"),
    Input({"type": "tool-replace-delete", "name": dash.ALL}, "n_clicks"),
    State("tool-replace-cards-row", "children"),
    State({"type": "tool-replace-pattern", "name": dash.ALL}, "value"),
    State({"type": "tool-replace-repl", "name": dash.ALL}, "value"),
    prevent_initial_call=True,
)
def update_replace_cards(new_click, duplicate_clicks, delete_clicks, cards, pattern_vals, repl_vals):
    trigger_id = ctx.triggered_id
    if cards is None:
        cards = []
    cards = _strip_add_card(cards, "tool-replace-add-card")

    if trigger_id == "tool-replace-new" and new_click:
        existing = [c.get("props", {}).get("id", {}).get("name", "") for c in cards if isinstance(c.get("props", {}).get("id", {}), dict)]
        idx = 1
        while f"rep{idx}" in existing:
            idx += 1
        cards.append(replace_card(f"rep{idx}"))
    elif isinstance(trigger_id, dict):
        trig_type = trigger_id.get("type")
        trig_name = trigger_id.get("name")
        idx = None
        for i, c in enumerate(cards):
            cid = c.get("props", {}).get("id", {})
            if isinstance(cid, dict) and cid.get("type") == "tool-replace-card" and cid.get("name") == trig_name:
                idx = i
                break

        if trig_type == "tool-replace-delete" and idx is not None and idx < len(delete_clicks) and delete_clicks[idx]:
            cards = [
                c for c in cards
                if not (isinstance(c.get("props", {}).get("id", {}), dict)
                        and c.get("props", {}).get("id", {}).get("type") == "tool-replace-card"
                        and c.get("props", {}).get("id", {}).get("name") == trig_name)
            ]
        elif trig_type == "tool-replace-duplicate" and idx is not None and idx < len(duplicate_clicks) and duplicate_clicks[idx]:
            existing = [c.get("props", {}).get("id", {}).get("name", "") for c in cards if isinstance(c.get("props", {}).get("id", {}), dict)]
            copy_idx = 1
            while f"{trig_name}_copy{copy_idx}" in existing:
                copy_idx += 1
            new_name = f"{trig_name}_copy{copy_idx}"
            cards.append(replace_card(
                new_name,
                pattern=pattern_vals[idx] if idx < len(pattern_vals) else "",
                replacement=repl_vals[idx] if idx < len(repl_vals) else "",
            ))

    cards.append(add_card("tool-replace", "Add replacement"))
    return cards


######################################
# Page-level callbacks
######################################

@dash.callback(
    Output({"page": page_path, "type": "tool-title-div"}, "children"),
    Input(f"url_{page_path}", "search"),
    State("odatix-settings", "data"),
)
def update_tool_title(search, odatix_settings):
    tool_name = get_key_from_url(search, "tool") or ""
    tools = get_workspace(odatix_settings).tools
    return tool_title(tool_name, overlay=_is_overlay(tools, tool_name))

def _is_overlay(tools, tool_name):
    """
    True when editing a built-in tool: its flows belong to Odatix, and what the
    workspace says about the rest is an overlay.
    """
    return bool(tool_name) and tools.entry(tool_name).is_builtin

def load_editor_settings(tools, tool_name):
    """
    Load what the editor shows for a tool: its settings, the built-in definition
    they may override (empty for a workspace tool), and whether it is a built-in
    tool.

    For a built-in tool, the built-in definition and the workspace overlay are
    merged the way odatix resolves them at run time, and every flow the built-in
    already declares is marked as such so the page can lock it.
    """
    empty = normalize_tool_settings({})
    if not tool_name:
        return empty, empty, False

    tool = tools.entry(tool_name)
    overlay = _is_overlay(tools, tool_name)
    if not overlay:
        return normalize_tool_settings(tool.document), empty, False

    builtin = normalize_tool_settings(tool.builtin_document)
    settings = normalize_tool_settings(tool.effective_document)
    builtin_names = {flow["name"] for flow in builtin.get("flows", [])}
    for flow in settings.get("flows", []):
        flow["builtin"] = flow["name"] in builtin_names
    return settings, builtin, True

@dash.callback(
    Output("tool-form-container", "children"),
    Output("tool-initial-settings", "data"),
    Output("tool-replace-cards-row", "children"),
    Output("tool-replace-title-container", "children"),
    Output("tool-log-format-container", "children"),
    Output("tool-flows-container", "children"),
    Output("tool-overlay-notice", "children"),
    Output("tool-edit-overlay", "data"),
    Output("tool-builtin-settings", "data"),
    Input(f"url_{page_path}", "search"),
    State(f"url_{page_path}", "pathname"),
    State("odatix-settings", "data"),
)
def init_form(search, page, odatix_settings):
    if page != page_path:
        return (dash.no_update,) * 9

    tool_name = get_key_from_url(search, "tool")
    settings, builtin, overlay = load_editor_settings(get_workspace(odatix_settings).tools, tool_name)

    fmt = settings.get("format", {})
    return (
        tool_form(settings, tool_name or "", overlay=overlay),
        settings,
        replace_cards_from_list(fmt.get("replace", [])),
        replace_section_title(overlay=overlay),
        log_formatting_tiles(settings, overlay=overlay),
        flow_cards(settings.get("flows", []), lock_default=overlay),
        builtin_notice(tool_name) if overlay else None,
        overlay,
        builtin,
    )

# The section a reset button puts back to the built-in state, and the settings
# keys it covers. "logs", "tags" and "replace" are the "format" subsections.
RESET_SECTIONS = {
    "metadata": ("label", "description", "icon"),
    "behaviour": ("process_group", "report_path", "target_file", "default_metrics_file"),
}

@dash.callback(
    Output("tool-form-container", "children", allow_duplicate=True),
    Output("tool-log-format-container", "children", allow_duplicate=True),
    Output("tool-replace-cards-row", "children", allow_duplicate=True),
    Input({"type": "tool-reset-builtin", "section": dash.ALL}, "n_clicks"),
    State("tool-label", "value"),
    State("tool-description", "value"),
    State("tool-icon", "value"),
    State("tool-process-group", "value"),
    State("tool-report-path", "value"),
    State("tool-target-file", "value"),
    State("tool-default-metrics-file", "value"),
    State("tool-log-error", "value"),
    State("tool-log-crit_warning", "value"),
    State("tool-log-warning", "value"),
    State("tool-log-info", "value"),
    State("tool-log-trace", "value"),
    State({"type": "tool-tag-markers", "name": dash.ALL}, "value"),
    State({"type": "tool-tag-markers", "name": dash.ALL}, "id"),
    State({"type": "tool-replace-pattern", "name": dash.ALL}, "value"),
    State({"type": "tool-replace-repl", "name": dash.ALL}, "value"),
    State("tool-builtin-settings", "data"),
    State(f"url_{page_path}", "search"),
    prevent_initial_call=True,
)
def reset_section_to_builtin(
    reset_clicks, label, description, icon_value, process_group, report_path, target_file, default_metrics_file,
    log_error, log_crit, log_warning, log_info, log_trace,
    tag_markers, tag_ids, replace_patterns, replace_repls, builtin, search,
):
    """
    Drop what the workspace says about one section of a built-in tool: its fields
    go back to the built-in values, and saving then writes nothing for them.

    The whole form is re-rendered from what the page currently holds, so the
    unsaved edits of the other sections are carried over. The re-render feeds the
    fields back to save_and_status, which refreshes the dirty state on its own.
    """
    trigger = ctx.triggered_id
    section = trigger.get("section") if isinstance(trigger, dict) else None
    if section is None or not (ctx.triggered[0]["value"] if ctx.triggered else None):
        return (dash.no_update,) * 3

    tag_names = [tid.get("name") if isinstance(tid, dict) else None for tid in (tag_ids or [])]
    log_values = {
        "error": log_error, "crit_warning": log_crit, "warning": log_warning,
        "info": log_info, "trace": log_trace,
    }
    settings = build_tool_settings(
        label, description, icon_value, process_group, report_path, target_file, default_metrics_file,
        [], log_values, tag_names, tag_markers, replace_patterns, replace_repls,
    )

    builtin = builtin if isinstance(builtin, dict) else normalize_tool_settings({})
    if section in RESET_SECTIONS:
        for key in RESET_SECTIONS[section]:
            settings[key] = builtin.get(key)
    elif section in ("logs", "tags", "replace"):
        settings["format"][section] = copy_module.deepcopy(builtin.get("format", {}).get(section))
    else:
        return (dash.no_update,) * 3

    tool_name = get_key_from_url(search, "tool") or ""
    return (
        tool_form(settings, tool_name, overlay=True),
        log_formatting_tiles(settings, overlay=True),
        replace_cards_from_list(settings.get("format", {}).get("replace", [])),
    )

@dash.callback(
    Output({"page": page_path, "action": "save-all"}, "className"),
    Output({"page": page_path, "action": "save-all"}, "data-tooltip"),
    Output(f"url_{page_path}", "search"),
    Output("tool-saved-settings", "data"),
    Input({"page": page_path, "action": "save-all"}, "n_clicks"),
    Input("tool-title", "value"),
    Input("tool-label", "value"),
    Input("tool-description", "value"),
    Input("tool-icon", "value"),
    Input("tool-process-group", "value"),
    Input("tool-report-path", "value"),
    Input("tool-target-file", "value"),
    Input("tool-default-metrics-file", "value"),
    *flow_dependencies(Input, Input),
    Input("tool-log-error", "value"),
    Input("tool-log-crit_warning", "value"),
    Input("tool-log-warning", "value"),
    Input("tool-log-info", "value"),
    Input("tool-log-trace", "value"),
    Input({"type": "tool-tag-markers", "name": dash.ALL}, "value"),
    Input({"type": "tool-replace-pattern", "name": dash.ALL}, "value"),
    Input({"type": "tool-replace-repl", "name": dash.ALL}, "value"),
    State({"type": "tool-tag-markers", "name": dash.ALL}, "id"),
    State(f"url_{page_path}", "search"),
    State(f"url_{page_path}", "pathname"),
    State("tool-initial-settings", "data"),
    State("tool-saved-settings", "data"),
    State("odatix-settings", "data"),
    State("tool-edit-overlay", "data"),
    State("tool-builtin-settings", "data"),
    prevent_initial_call=True,
)
def save_and_status(
    n_clicks, tool_title_value, label, description, icon_value, process_group, report_path, target_file, default_metrics_file,
    flow_ids, flow_names, flow_labels, flow_descriptions, flow_defaults, flow_builtins, flow_collapsed,
    mode_ids, mode_values, cmd_ids, cmd_values,
    session_ids, session_cmds, session_begins, session_ends,
    step_ids, step_names, step_cmds, step_defaults, step_kinds,
    log_error, log_crit, log_warning, log_info, log_trace,
    tag_markers, replace_patterns, replace_repls,
    tag_ids, search, page, initial_settings, saved_settings, odatix_settings, overlay, builtin_settings,
):
    # The tag set is fixed (the ANSI style/color names): the tag names come from
    # the markers inputs' ids, not from an editable field.
    tag_names = [tid.get("name") if isinstance(tid, dict) else None for tid in (tag_ids or [])]
    triggered_id = ctx.triggered_id
    if triggered_id == f"url_{page_path}" and page != page_path:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update

    flows = gather_flows(
        flow_ids, flow_names, flow_labels, flow_descriptions, flow_defaults, flow_builtins, flow_collapsed,
        mode_ids, mode_values, cmd_ids, cmd_values,
        session_ids, session_cmds, session_begins, session_ends,
        step_ids, step_names, step_cmds, step_defaults, step_kinds,
    )
    log_values = {
        "error": log_error, "crit_warning": log_crit, "warning": log_warning,
        "info": log_info, "trace": log_trace,
    }

    current_settings = build_tool_settings(
        label, description, icon_value, process_group, report_path, target_file, default_metrics_file,
        flows, log_values, tag_names, tag_markers, replace_patterns, replace_repls,
    )

    reference_settings = normalize_for_compare(saved_settings if saved_settings is not None else initial_settings)
    current_compare = normalize_for_compare(current_settings)

    tool_name = get_key_from_url(search, "tool")
    tools = get_workspace(odatix_settings).tools

    error_class = "color-button error-status icon-button tooltip bottom"

    if not tool_title_value:
        return error_class, "Tool name cannot be empty", dash.no_update, saved_settings
    for character in hard_settings.invalid_filename_characters:
        if character in tool_title_value:
            label_char = "' ' (space)" if character == " " else f"'{character}'"
            return error_class, f"Unauthorized character in tool name: {label_char}", dash.no_update, saved_settings

    if triggered_id == {"page": page_path, "action": "save-all"}:
        new_search = dash.no_update

        # A built-in tool keeps its name and its flows: the workspace file holds
        # the flows added to it and the settings that differ from the built-in
        # ones, nothing else.
        if overlay:
            added = [flow for flow in flows if not flow.get("builtin")]
            overrides = overlay_overrides(
                current_settings,
                builtin_settings if isinstance(builtin_settings, dict) else {},
            )
            try:
                tools[tool_name].save_overlay(overrides, added)
                return (
                    "color-button disabled icon-button tooltip delay bottom small",
                    "Nothing to save",
                    dash.no_update,
                    current_settings,
                )
            except Exception:
                return error_class + " small", "Failed to save...", dash.no_update, saved_settings

        if tool_name and tool_title_value != tool_name:
            if tools.exists(tool_title_value):
                return error_class, f"'{tool_title_value}' already exists", dash.no_update, saved_settings
            if _builtin_tool_exists(tool_title_value):
                return error_class, f"'{tool_title_value}' is a built-in tool name", dash.no_update, saved_settings
            if tools.exists(tool_name):
                tools.rename(tool_name, tool_title_value)
            tool_name = tool_title_value
            new_search = f"?tool={tool_name}"
        elif not tool_name:
            if tools.exists(tool_title_value):
                return error_class, f"'{tool_title_value}' already exists", dash.no_update, saved_settings
            if _builtin_tool_exists(tool_title_value):
                return error_class, f"'{tool_title_value}' is a built-in tool name", dash.no_update, saved_settings
            tool_name = tool_title_value
            new_search = f"?tool={tool_name}"

        tool = tools.get(tool_name)
        if tool is None:
            tool = tools.create(tool_name)

        try:
            tool.settings = current_settings
            tool.save(as_overlay=False)
            return (
                "color-button disabled icon-button tooltip delay bottom small",
                "Nothing to save",
                new_search,
                current_settings,
            )
        except Exception:
            return error_class + " small", "Failed to save...", dash.no_update, saved_settings

    if current_compare != reference_settings or tool_title_value != (tool_name or ""):
        return (
            "color-button warning icon-button tooltip bottom small",
            "Unsaved changes!",
            dash.no_update,
            dash.no_update,
        )

    return (
        "color-button disabled icon-button tooltip delay bottom small",
        "Nothing to save",
        dash.no_update,
        saved_settings,
    )


######################################
# Layout
######################################

layout = html.Div(
    children=[
        dcc.Location(id=f"url_{page_path}"),
        html.Div(id={"page": page_path, "type": "tool-title-div"}, style={"marginTop": "20px"}),
        html.Div(id="tool-overlay-notice"),
        html.Div(id="tool-form-container"),
        html.Div(
            children=[
                ui.title_tile(
                    text="Flows", id="tool-flows-title",
                    tooltip="The ways this tool can be run. Each flow declares, per platform and per job type, "
                            "either a single command or an ordered list of resumable steps; a flow that declares "
                            "nothing runs what the default flow does.",
                ),
                html.Div(id="tool-flows-container", className="odx-flows"),
                ui.title_tile(text="Log Formatting", id="tool-format-title", tooltip="Tags and markers used to colorize the tool output in the job monitor."),
                html.Div(id="tool-log-format-container"),
                html.Div(id="tool-replace-title-container", children=replace_section_title()),
                html.Div([
                    html.Div(
                        id="tool-replace-cards-row",
                        children=[add_card("tool-replace", "Add replacement")],
                        className="card-matrix configs",
                        style={"marginBottom": "30px"},
                    ),
                ]),
            ],
        ),
        dcc.Store(id="tool-edit-overlay", data=False),
        # The built-in definition a built-in tool's settings override, kept so a
        # section can be put back to it and so only what differs is saved.
        dcc.Store(id="tool-builtin-settings", data=None),
        dcc.Store(id="tool-initial-settings", data=None),
        dcc.Store(id="tool-saved-settings", data=None),
    ],
    className="page-content",
    style={
        "display": "flex",
        "flexDirection": "column",
        "min-height": f"calc(100vh - {navigation.top_bar_height})",
    },
)
