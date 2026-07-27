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
odatix.components.workspace and odatix.lib.eda_tools). It exposes, in the style
of the Workflow Editor:
  - display metadata (label / description / icon),
  - behaviour (process_group, report_path, default_metrics_file),
  - the per-platform commands (unix / windows), one textarea per flow,
  - the log formatting section (logs / tags / replace).

YAML anchors used by the built-in tool.yml files are resolved on load, so the
editor works on plain command lists and re-emits a flat, anchor-free tool.yml on
save. The tool's metrics.yml is edited from the "Edit Metrics" button
(/metric_editor?tool=...).
"""

import os

import dash
from dash import html, dcc, Input, Output, State, ctx

import odatix.components.workspace as workspace
from odatix.gui.icons import icon
from odatix.gui.utils import get_key_from_url
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

# The command flows edited per platform, with their display label and tooltip.
FLOW_COMMANDS = [
    ("tool_test_command", "Tool test command", "Command run to check the tool is installed and reachable."),
    ("fmax_synthesis_command", "Fmax synthesis command", "Command run for the maximum-frequency synthesis flow."),
    ("custom_freq_synthesis_command", "Custom frequency synthesis command", "Command run for the custom-frequency synthesis flow."),
    ("analysis_command", "RTL analysis command", "Command run for the RTL analysis flow."),
]

# Supported platforms, with their display label.
PLATFORMS = [
    ("unix", "Unix / Linux"),
    ("windows", "Windows"),
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

def _get_tools_path(odatix_settings):
    tools_path = odatix_settings.get("tools_path", "") if isinstance(odatix_settings, dict) else ""
    if tools_path:
        return tools_path
    settings_data = OdatixSettings.get_settings_file_dict(silent=True)
    if isinstance(settings_data, dict):
        return settings_data.get("tools_path", OdatixSettings.DEFAULT_TOOLS_PATH)
    return OdatixSettings.DEFAULT_TOOLS_PATH

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

def normalize_tool_settings(raw):
    """
    Map a loaded tool.yml (anchors resolved) into the editor's canonical dict,
    used both to render the form and as the dirty-state reference.
    """
    if not isinstance(raw, dict):
        raw = {}

    platforms = {}
    for platform_key, _label in PLATFORMS:
        section = raw.get(platform_key, {})
        if not isinstance(section, dict):
            section = {}
        platforms[platform_key] = {
            flow: _lines_to_list(_as_lines(section.get(flow, [])))
            for flow, _l, _t in FLOW_COMMANDS
        }

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
        "platforms": platforms,
        "format": {"logs": logs, "tags": tags, "replace": replace},
    }

def build_tool_settings(
    label, description, icon_value, process_group, report_path, target_file, default_metrics_file,
    command_values, log_values, tag_names, tag_markers, replace_patterns, replace_repls,
):
    """
    Build the canonical settings dict from the raw field values gathered by the
    save callback. `command_values` is a {(platform, flow): text} mapping and
    `log_values` a {level: text} mapping.
    """
    platforms = {}
    for platform_key, _label in PLATFORMS:
        platforms[platform_key] = {
            flow: _lines_to_list(command_values.get((platform_key, flow), ""))
            for flow, _l, _t in FLOW_COMMANDS
        }

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
        "platforms": platforms,
        "format": {"logs": logs, "tags": tags, "replace": replace},
    }

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
        "platforms": n.get("platforms", {}),
        "format": {
            "logs": {k: list(v) for k, v in (n.get("format", {}).get("logs", {}) or {}).items() if v},
            "tags": {k: list(v) for k, v in (n.get("format", {}).get("tags", {}) or {}).items() if v},
            "replace": _replace_pairs(n.get("format", {}).get("replace", [])),
        },
    }

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

def tool_title(tool_name):
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
            style={"position": "relative"},
        ),
        className="card-matrix config",
        style={"marginTop": "0px", "marginBottom": "10px"},
    )

def tool_form_field(label, id, value="", tooltip="", placeholder=""):
    return html.Div(
        children=[
            html.Label(label),
            ui.tooltip_icon(tooltip) if tooltip else None,
            dcc.Input(id=id, value=value, type="text", placeholder=placeholder, style={"width": "100%"}),
        ],
        style={"marginBottom": "12px"},
    )

def command_textarea(platform_key, flow, label, tooltip, value=""):
    return html.Div(
        children=[
            html.Label(label, style={"fontWeight": "bold", "fontSize": "1em"}),
            ui.tooltip_icon(tooltip) if tooltip else None,
            dcc.Textarea(
                value=value,
                id=f"tool-cmd-{platform_key}-{flow}",
                className="auto-resize-textarea",
                placeholder="One argument per line",
                style={
                    "width": "100%",
                    "minHeight": "70px",
                    "resize": "vertical",
                    "fontFamily": "monospace",
                    "fontWeight": "500",
                    "marginBottom": "10px",
                    "boxSizing": "border-box",
                },
            ),
        ],
        style={"marginBottom": "6px"},
    )

def tool_form(settings, tool_name=""):
    target_placeholder = f"target_{tool_name}.yml" if tool_name else "target_<tool>.yml"

    metadata_tile = html.Div(
        [
            html.H3("Tool Metadata"),
            tool_form_field("Label", "tool-label", value=settings.get("label", ""),
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
            html.H3("Behaviour"),
            html.Div(
                children=[
                    dcc.Checklist(
                        options=[{"label": "Group processes", "value": True}],
                        value=[True] if settings.get("process_group", True) else [],
                        id="tool-process-group",
                        className="checklist-switch",
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

def command_tiles(settings):
    platforms = settings.get("platforms", {})
    command_tiles = []
    for platform_key, platform_label in PLATFORMS:
        platform_commands = platforms.get(platform_key, {})
        command_tiles.append(
            html.Div(
                [
                    html.H3(platform_label),
                    *[
                        command_textarea(
                            platform_key, flow, label, tooltip,
                            value=_as_lines(platform_commands.get(flow, [])),
                        )
                        for flow, label, tooltip in FLOW_COMMANDS
                    ],
                ],
                className="tile config",
            )
        )

    return html.Div(
        children=command_tiles,
        className="tiles-container config",
        style={"marginBottom": "20px"},
    )

def log_formatting_tiles(settings):
    logs = settings.get("format", {}).get("logs", {})
    tags = settings.get("format", {}).get("tags", {})

    log_tile = html.Div(
        [
            html.H3("Log Levels"),
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
            html.H3("Log Format Tags"),
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
        style={"padding": "10px", "margin": "5px", "display": "inline-block", "verticalAlign": "top", "boxSizing": "border-box"},
    )

def replace_cards_from_list(replace):
    cards = []
    for idx, pair in enumerate(_replace_pairs(replace)):
        cards.append(replace_card(f"rep{idx + 1}", pattern=pair[0], replacement=pair[1]))
    cards.append(add_card("tool-replace", "Add replacement"))
    return cards


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
)
def update_tool_title(search):
    tool_name = get_key_from_url(search, "tool") or ""
    return tool_title(tool_name)

@dash.callback(
    Output("tool-form-container", "children"),
    Output("tool-initial-settings", "data"),
    Output("tool-replace-cards-row", "children"),
    Output("tool-log-format-container", "children"),
    Output("tool-commands-container", "children"),
    Input(f"url_{page_path}", "search"),
    State(f"url_{page_path}", "pathname"),
    State("odatix-settings", "data"),
)
def init_form(search, page, odatix_settings):
    if page != page_path:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update

    tool_name = get_key_from_url(search, "tool")
    if not tool_name:
        settings = normalize_tool_settings({})
        return (
            tool_form(settings, ""),
            settings,
            replace_cards_from_list([]),
            log_formatting_tiles(settings),
            command_tiles(settings),
        )

    tools_path = _get_tools_path(odatix_settings)
    settings = normalize_tool_settings(workspace.load_tool_settings(tools_path, tool_name))
    fmt = settings.get("format", {})
    return (
        tool_form(settings, tool_name),
        settings,
        replace_cards_from_list(fmt.get("replace", [])),
        log_formatting_tiles(settings),
        command_tiles(settings),
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
    Input("tool-cmd-unix-tool_test_command", "value"),
    Input("tool-cmd-unix-fmax_synthesis_command", "value"),
    Input("tool-cmd-unix-custom_freq_synthesis_command", "value"),
    Input("tool-cmd-unix-analysis_command", "value"),
    Input("tool-cmd-windows-tool_test_command", "value"),
    Input("tool-cmd-windows-fmax_synthesis_command", "value"),
    Input("tool-cmd-windows-custom_freq_synthesis_command", "value"),
    Input("tool-cmd-windows-analysis_command", "value"),
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
    prevent_initial_call=True,
)
def save_and_status(
    n_clicks, tool_title_value, label, description, icon_value, process_group, report_path, target_file, default_metrics_file,
    u_test, u_fmax, u_custom, u_analysis, w_test, w_fmax, w_custom, w_analysis,
    log_error, log_crit, log_warning, log_info, log_trace,
    tag_markers, replace_patterns, replace_repls,
    tag_ids, search, page, initial_settings, saved_settings, odatix_settings,
):
    # The tag set is fixed (the ANSI style/color names): the tag names come from
    # the markers inputs' ids, not from an editable field.
    tag_names = [tid.get("name") if isinstance(tid, dict) else None for tid in (tag_ids or [])]
    triggered_id = ctx.triggered_id
    if triggered_id == f"url_{page_path}" and page != page_path:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update

    command_values = {
        ("unix", "tool_test_command"): u_test,
        ("unix", "fmax_synthesis_command"): u_fmax,
        ("unix", "custom_freq_synthesis_command"): u_custom,
        ("unix", "analysis_command"): u_analysis,
        ("windows", "tool_test_command"): w_test,
        ("windows", "fmax_synthesis_command"): w_fmax,
        ("windows", "custom_freq_synthesis_command"): w_custom,
        ("windows", "analysis_command"): w_analysis,
    }
    log_values = {
        "error": log_error, "crit_warning": log_crit, "warning": log_warning,
        "info": log_info, "trace": log_trace,
    }

    current_settings = build_tool_settings(
        label, description, icon_value, process_group, report_path, target_file, default_metrics_file,
        command_values, log_values, tag_names, tag_markers, replace_patterns, replace_repls,
    )

    reference_settings = normalize_for_compare(saved_settings if saved_settings is not None else initial_settings)
    current_compare = normalize_for_compare(current_settings)

    tool_name = get_key_from_url(search, "tool")
    tools_path = _get_tools_path(odatix_settings)

    error_class = "color-button error-status icon-button tooltip bottom"

    if not tool_title_value:
        return error_class, "Tool name cannot be empty", dash.no_update, saved_settings
    for character in hard_settings.invalid_filename_characters:
        if character in tool_title_value:
            label_char = "' ' (space)" if character == " " else f"'{character}'"
            return error_class, f"Unauthorized character in tool name: {label_char}", dash.no_update, saved_settings

    if triggered_id == {"page": page_path, "action": "save-all"}:
        new_search = dash.no_update

        if tool_name and tool_title_value != tool_name:
            if workspace.tool_exists(tools_path, tool_title_value):
                return error_class, f"'{tool_title_value}' already exists", dash.no_update, saved_settings
            if _builtin_tool_exists(tool_title_value):
                return error_class, f"'{tool_title_value}' is a built-in tool name", dash.no_update, saved_settings
            if workspace.tool_exists(tools_path, tool_name):
                workspace.rename_tool(tools_path, tool_name, tool_title_value)
            tool_name = tool_title_value
            new_search = f"?tool={tool_name}"
        elif not tool_name:
            if workspace.tool_exists(tools_path, tool_title_value):
                return error_class, f"'{tool_title_value}' already exists", dash.no_update, saved_settings
            if _builtin_tool_exists(tool_title_value):
                return error_class, f"'{tool_title_value}' is a built-in tool name", dash.no_update, saved_settings
            tool_name = tool_title_value
            new_search = f"?tool={tool_name}"

        if not workspace.tool_exists(tools_path, tool_name):
            workspace.create_tool(tools_path, tool_name)

        try:
            workspace.save_tool_settings(tools_path, tool_name, current_settings)
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
        html.Div(id="tool-form-container"),
        html.Div(
            children=[
                ui.title_tile(text="Commands", id="tool-commands-title", tooltip="Commands run for each flow, per platform."),
                html.Div(id="tool-commands-container"),
                ui.title_tile(text="Log Formatting", id="tool-format-title", tooltip="Tags and markers used to colorize the tool output in the job monitor."),
                html.Div(id="tool-log-format-container"),
                ui.title_tile(text="Log Replacements", id="tool-replace-title", tooltip="Regular expressions applied to the tool output to recolor or rewrite matching text."),
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
