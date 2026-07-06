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

import yaml
import dash
from dash import html, dcc, Input, Output, State, ctx
from typing import Optional

import odatix.components.workspace as workspace
from odatix.gui.icons import icon
from odatix.gui.utils import get_key_from_url
from odatix.gui.css_helper import Style
import odatix.gui.ui_components as ui
import odatix.gui.navigation as navigation
import odatix.lib.hard_settings as hard_settings
from odatix.lib.settings import OdatixSettings

page_path = "/workflow_editor"

dash.register_page(
    __name__,
    path=page_path,
    title="Odatix - Workflow Editor",
    name="Workflow Editor",
    order=5,
)


######################################
# Helpers
######################################

def _parse_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        val = value.strip().lower()
        if val in ["yes", "true", "1"]:
            return True
        if val in ["no", "false", "0"]:
            return False
    return default

def _normalize_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [str(v).strip() for v in str(value).split(",") if str(v).strip()]

def _get_workflow_path(odatix_settings):
    workflow_path = odatix_settings.get("workflow_path", "")
    if workflow_path:
        return workflow_path

    settings_data = OdatixSettings.get_settings_file_dict(silent=True)
    if isinstance(settings_data, dict):
        return settings_data.get("workflow_path", OdatixSettings.DEFAULT_WORKFLOW_PATH)

    return OdatixSettings.DEFAULT_WORKFLOW_PATH

def normalize_workflow_settings(settings):
    if not isinstance(settings, dict):
        settings = {}

    sources = settings.get("sources", {})
    if not isinstance(sources, dict):
        sources = {}

    progress = settings.get("progress", {})
    if not isinstance(progress, dict):
        progress = {}

    tasks = settings.get("tasks", [])
    if not isinstance(tasks, list):
        tasks = []

    generate_configurations_settings = settings.get("generate_configurations_settings", {})
    if not isinstance(generate_configurations_settings, dict):
        generate_configurations_settings = {}
    variables = generate_configurations_settings.get("variables", {})
    if not isinstance(variables, dict):
        variables = {}
    generate_configurations_settings = {**generate_configurations_settings, "variables": variables}

    try:
        vars_copy = {}
        for vname, vcfg in generate_configurations_settings.get("variables", {}).items():
            if not isinstance(vcfg, dict):
                vars_copy[vname] = vcfg
                continue

            # Only keep canonical keys
            v_type = vcfg.get("type")
            v_format = vcfg.get("format") if "format" in vcfg else None
            vsettings = vcfg.get("settings", {}) if isinstance(vcfg.get("settings", {}), dict) else {}

            # Normalize list elements to strings when present
            if "list" in vsettings and isinstance(vsettings["list"], (list, tuple)):
                vsettings = dict(vsettings)
                vsettings["list"] = [str(x) for x in vsettings["list"]]

            new_vcfg = {"type": v_type, "settings": vsettings}
            if v_format:
                new_vcfg["format"] = v_format

            vars_copy[vname] = new_vcfg

        generate_configurations_settings["variables"] = vars_copy
    except Exception:
        pass

    return {
        "sources": {
            "path": sources.get("path", ""),
            "whitelist": _normalize_list(sources.get("whitelist", [])),
            "blacklist": _normalize_list(sources.get("blacklist", [])),
        },
        "use_parameters": _parse_bool(settings.get("use_parameters", True), True),
        "param_target_file": settings.get("param_target_file", ""),
        "start_delimiter": settings.get("start_delimiter", ""),
        "stop_delimiter": settings.get("stop_delimiter", ""),
        "progress": {
            "file": progress.get("file", ""),
            "regex": progress.get("regex", ""),
        },
        "tasks": tasks,
        "generate_configurations_settings": generate_configurations_settings,
    }

def format_tasks(tasks):
    if not isinstance(tasks, list) or len(tasks) == 0:
        return ""
    return yaml.safe_dump(tasks, sort_keys=False, default_flow_style=False).strip()

def wf_build_tasks_list(names, dependencies_vals, commands_vals, path_vals, platforms_vals):
    """
    Build the workflow tasks list from task card field values.
    """
    tasks = []
    has_main = False
    nb = len(names) if isinstance(names, list) else 0
    for idx in range(nb):
        name = str(names[idx]).strip() if idx < len(names) and names[idx] is not None else ""
        if name == "":
            continue

        dependencies_raw = dependencies_vals[idx] if idx < len(dependencies_vals) else ""
        dependencies = [
            x.strip() for x in str(dependencies_raw).split(",")
            if x is not None and str(x).strip() != ""
        ]

        commands_raw = commands_vals[idx] if idx < len(commands_vals) else ""
        commands = [
            line.strip() for line in str(commands_raw).splitlines()
            if line is not None and str(line).strip() != ""
        ]

        task = {
            "name": name,
            "commands": commands,
        }
        if name == "main":
            has_main = True
        if len(dependencies) > 0:
            task["dependencies"] = dependencies

        task_path = str(path_vals[idx]).strip() if idx < len(path_vals) and path_vals[idx] is not None else ""
        if task_path != "":
            task["path"] = task_path

        platforms_raw = platforms_vals[idx] if idx < len(platforms_vals) else ""
        platforms = [
            x.strip() for x in str(platforms_raw).split(",")
            if x is not None and str(x).strip() != ""
        ]
        if len(platforms) == 1:
            task["platforms"] = platforms[0]
        elif len(platforms) > 1:
            task["platforms"] = platforms

        tasks.append(task)

    # Always keep at least the mandatory main task.
    if not has_main:
        tasks.insert(0, {"name": "main", "commands": []})

    return tasks

def wf_build_variables_dict(
    titles, types, base_vals, from_vals, to_vals, from_2_pow_vals, to_2_pow_vals, from_type_vals, to_type_vals, step_vals, op_vals, list_vals, source_vals, sources_vals, format_vals
):
    """
    Build a "generate_configurations_settings.variables" dict from the variable card field values.
    """
    variables = {}
    for idx, title in enumerate(titles):
        type = types[idx]
        settings = {}
        format = format_vals[idx] if format_vals[idx] else None
        if type == "range":
            settings["from"] = int(from_vals[idx]) if from_vals[idx] else 0
            settings["to"] = int(to_vals[idx]) if to_vals[idx] else 0
            settings["step"] = int(step_vals[idx]) if step_vals[idx] else 1
        elif type == "power_of_two":
            settings["from_2^"] = int(from_2_pow_vals[idx]) if from_2_pow_vals[idx] else 0
            settings["to_2^"] = int(to_2_pow_vals[idx]) if to_2_pow_vals[idx] else 0
        elif type == "list":
            settings["list"] = [x.strip() for x in list_vals[idx].split(",") if x.strip()] if list_vals[idx] else []
        elif type == "multiples":
            settings["base"] = int(base_vals[idx]) if base_vals[idx] else 1
            settings["from"] = int(from_vals[idx]) if from_vals[idx] else 0
            settings["to"] = int(to_vals[idx]) if to_vals[idx] else 0
        elif type == "function":
            settings["op"] = op_vals[idx] if op_vals[idx] else ""
        elif type == "conversion":
            settings["from"] = from_type_vals[idx] if from_type_vals[idx] else 0
            settings["to"] = to_type_vals[idx] if to_type_vals[idx] else 0
            settings["source"] = source_vals[idx] if source_vals[idx] else ""
        elif type == "format":
            settings["source"] = source_vals[idx] if source_vals[idx] else ""
        elif type in {"union", "disjunctive_union", "intersection", "difference"}:
            settings["sources"] = [x.strip() for x in sources_vals[idx].split(",") if x.strip()] if sources_vals[idx] else []
        variable = workspace.create_config_gen_variable_dict(name=title, type=type, settings=settings, format=format)
        variables.update(variable)
    return variables


######################################
# UI Components
######################################

def workflow_title(workflow_name):
    title_buttons = html.Div(
        children=[
            ui.icon_button(
                id=f"button-open-config-editor",
                icon=icon("edit", className="icon blue"),
                text="Edit Configs",
                tooltip="Open the Configuration Editor for this workflow",
                tooltip_options="bottom delay",
                color="default",
                link=f"/config_editor?workflow={workflow_name}",
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
                                    value=f"{workflow_name}",
                                    type="text",
                                    id="workflow-title",
                                    placeholder="Workflow Name...",
                                    className="title-input",
                                    style={"width": "100%", "transform": "translate(-5px, 5px)"},
                                )
                            ],
                            id="workflow-title-container",
                        ),
                        html.Div([title_buttons]),
                    ],
                    className="title-tile-flex",
                    style={
                        "display": "flex",
                        "alignItems": "center",
                        "padding": "0px",
                        "justifyContent": "space-between",
                    },
                ),
                ui.back_button(link="/workflows"),
            ],
            className="tile title",
            style={"position": "relative"},
        ),
        className="card-matrix config",
        style={"marginTop": "0px", "marginBottom": "10px", "marginLeft": "-13px"},
    )

def workflow_form_field(
    label,
    id,
    value="",
    tooltip="",
    placeholder="",
    tooltip_options="secondary",
):
    return html.Div(
        children=[
            html.Label(label),
            ui.tooltip_icon(tooltip, tooltip_options),
            dcc.Input(id=id, value=value, type="text", placeholder=placeholder, style={"width": "100%"}),
        ],
        style={"marginBottom": "12px"},
    )

def workflow_form(settings):
    defval = lambda k, v=None: settings.get(k, v)

    sources = defval("sources", {})
    progress = defval("progress", {})
    use_parameters = True if defval("use_parameters", True) else False

    return html.Div(
        children=[
            html.Div(
                [
                    html.H3("Workflow Sources"),
                    workflow_form_field(
                        label="Source Path",
                        id="wf-source-path",
                        value=sources.get("path", ""),
                        tooltip="Directory copied in each workflow work directory before running tasks.",
                    ),
                    workflow_form_field(
                        label="Source Whitelist",
                        id="wf-source-whitelist",
                        value=", ".join(sources.get("whitelist", [])),
                        placeholder="src/**, scripts/**",
                        tooltip="Optional comma-separated inclusion patterns.",
                    ),
                    workflow_form_field(
                        label="Source Blacklist",
                        id="wf-source-blacklist",
                        value=", ".join(sources.get("blacklist", [])),
                        placeholder="*.log, tmp/**",
                        tooltip="Optional comma-separated exclusion patterns.",
                    ),
                ],
                className="tile config",
            ),
            html.Div(
                [
                    html.H3("Parameters Replacement"),
                    html.Div(
                        children=[
                            dcc.Checklist(
                                options=[{"label": "Enable parameter replacement", "value": True}],
                                value=[True] if use_parameters else [],
                                id="wf-use-parameters",
                                className="checklist-switch",
                                style={"marginBottom": "12px", "marginTop": "5px", "display": "inline-block"},
                            ),
                            ui.tooltip_icon("Replace values in a target file using selected workflow configuration files."),
                        ],
                        style={"marginBottom": "12px"},
                    ),
                    html.Div(
                        children=[
                            workflow_form_field(
                                label="Parameter Target File",
                                id="wf-param-target-file",
                                value=defval("param_target_file", ""),
                                tooltip="File in the copied sources where replacements are applied.",
                            ),
                            workflow_form_field(
                                label="Start Delimiter",
                                id="wf-start-delimiter",
                                value=defval("start_delimiter", ""),
                                tooltip="Start marker for replacement.",
                            ),
                            workflow_form_field(
                                label="Stop Delimiter",
                                id="wf-stop-delimiter",
                                value=defval("stop_delimiter", ""),
                                tooltip="Stop marker for replacement.",
                            ),
                        ],
                        id="wf-params-config-fields",
                        className="animated-section" if use_parameters else "animated-section hide",
                        style={"overflow": "visible"},
                    ),
                ],
                className="tile config",
            ),
            html.Div(
                [
                    html.H3("Progress Tracking"),
                    workflow_form_field(
                        label="Progress File",
                        id="wf-progress-file",
                        value=progress.get("file", ""),
                        tooltip="Path of the progress file generated by tasks.",
                    ),
                    workflow_form_field(
                        label="Progress Regex",
                        id="wf-progress-regex",
                        value=progress.get("regex", ""),
                        tooltip="Regex containing one capture group for completion percentage.",
                    ),
                ],
                className="tile config",
            ),
        ],
        className="tiles-container config",
        style={"marginTop": "-10px", "marginBottom": "20px"},
    )

def wf_variable_field(
    var: str,
    type: str = "text",
    name: str = "",
    label: Optional[str] = None,
    options: Optional[list] = None,
    value: str = "",
    placeholder: str = "",
    default_style: dict = Style.hidden,
):
    if label is None:
        label = name
    return html.Div(
        children=[
            html.Div(
                children=[
                    html.Label(label, style={"fontWeight": "bold", "fontSize": "1em"}),
                    dcc.Input(
                        value=value,
                        type=type,
                        placeholder=placeholder,
                        id={"type": f"wf-variable-field-{name}", "name": var},
                        className="value-input",
                        style={
                            "width": "calc(100% - 20px)",
                            "marginLeft": "5px",
                            "marginRight": "5px",
                            "marginBottom": "5px",
                            "fontSize": "0.9em",
                            "height": "10px",
                            "zIndex": "900",
                        },
                    ) if options is None else dcc.Dropdown(
                        id={"type": f"wf-variable-field-{name}", "name": var},
                        options=options,
                        value=value,
                        clearable=False,
                        style={
                            "fontSize": "0.95em",
                            "zIndex": "900",
                        },
                    ),
                ],
                style={"marginTop": "5px"}
            ),
        ],
        id={"type": f"wf-variable-field-{name}-div", "name": var},
        style=default_style
    )

def wf_variable_card(
    name, type_value="list",
    base_value="", from_value="", to_value="",
    from_2_pow_value="", to_2_pow_value="", step_value="1",
    from_type_value="dec", to_type_value="hex",
    op_value="", list_value="", source_value="", sources_value="", format_value="",
):
    return html.Div([
        html.Div([
            dcc.Input(
                value=name,
                type="text",
                id={"type": "wf-variable-title", "name": name},
                className="title-input",
                style={
                    "width": "calc(100% - 20px)",
                    "marginLeft": "5px",
                    "marginRight": "5px",
                    "marginTop": "-5px",
                    "marginBottom": "2px",
                    "fontWeight": "bold",
                    "fontSize": "1.1em",
                    "height": "10px",
                    "textAlign": "center",
                },
            ),
            dcc.Dropdown(
                id={"type": "wf-variable-type", "name": name},
                options=[
                    {"label": "Boolean", "value": "bool"},
                    {"label": "List", "value": "list"},
                    {"label": "Range", "value": "range"},
                    {"label": "Power of 2", "value": "power_of_two"},
                    {"label": "Multiples", "value": "multiples"},
                    {"label": "Function", "value": "function"},
                    {"label": "Conversion", "value": "conversion"},
                    {"label": "Format", "value": "format"},
                    {"label": "Union", "value": "union"},
                    {"label": "Disjunctive Union", "value": "disjunctive_union"},
                    {"label": "Intersection", "value": "intersection"},
                    {"label": "Difference", "value": "difference"},
                ],
                value=type_value,
                clearable=False,
            ),
            html.Div(
                children=[
                    wf_variable_field(var=name, name="from", label="From", type="number", value=from_value),
                    wf_variable_field(var=name, name="to", label="To", type="number", value=to_value),
                    wf_variable_field(var=name, name="from_2_pow", label="From 2^", type="number", value=from_2_pow_value),
                    wf_variable_field(var=name, name="to_2_pow", label="To 2^", type="number", value=to_2_pow_value),
                    wf_variable_field(var=name, name="from_type", label="From type", type="text", options=[{"label": "Bin", "value": "bin"}, {"label": "Dec", "value": "dec"}, {"label": "Hex", "value": "hex"}], value=from_type_value),
                    wf_variable_field(var=name, name="to_type", label="To type", type="text", options=[{"label": "Bin", "value": "bin"}, {"label": "Dec", "value": "dec"}, {"label": "Hex", "value": "hex"}], value=to_type_value),
                    wf_variable_field(var=name, name="base", label="Base", type="number", value=base_value),
                    wf_variable_field(var=name, name="step", label="Step", type="number", value=step_value),
                    wf_variable_field(var=name, name="op", label="Op", type="text", value=op_value),
                    wf_variable_field(var=name, name="list", label="List", type="text", placeholder="Comma-separated values", default_style=Style.visible, value=list_value),
                    wf_variable_field(var=name, name="source", label="Source", type="text", value=source_value),
                    wf_variable_field(var=name, name="sources", label="Sources", type="text", placeholder="Comma-separated values", value=sources_value),
                    html.Div(
                        children=[
                            wf_variable_field(var=name, name="format", label="Format", type="text", value=format_value),
                        ],
                        id={"type": "wf-more-variable-field-div", "name": name},
                        className="expandable-area",
                        style=Style.hidden
                    )
                ],
                id="variable-fields-container",
            ),
        ]),
        html.Div([
            html.Div([
                ui.icon_button(
                    icon=icon("more", className="icon normal rotate", id={"type": "wf-more-fields-icon", "name": name}),
                    color="default",
                    id={"type": "wf-more-fields", "name": name},
                    tooltip="Show/Hide extra fields",
                    tooltip_options="bottom small",
                )
            ], id={"type": "wf-more-fields-div", "name": name}, style={"display": "flex", "alignItems": "center"}),
            html.Div([
                ui.duplicate_button(id={"type": "wf-duplicate-var", "name": name}),
                ui.delete_button(id={"type": "wf-delete-var", "name": name}),
            ], style={"display": "flex", "flexDirection": "hotizontal", "alignItems": "center"}),
        ], style={
            "marginTop": "8px",
            "display": "flex",
            "flexDirection": "row",
            "width": "100%",
            "justifyContent": "space-between",
        }),
        dcc.Store(id={"type": "wf-variable-metadata", "name": name}, data={"name": name, "type": type_value, "base_value": base_value, "from_value": from_value, "to_value": to_value, "from_2_pow_value": from_2_pow_value, "to_2_pow_value": to_2_pow_value, "from_type_value": from_type_value, "to_type_value": to_type_value, "step_value": step_value, "op_value": op_value, "list_value": list_value, "source_value": source_value, "sources_value": sources_value, "format_value": format_value}),
    ],
    className="card configs",
    id={"type": "wf-variable-card", "name": name},
    style={
        "padding": "10px",
        "margin": "5px",
        "display": "inline-block",
        "verticalAlign": "top"
    })

def wf_task_card(name="main", dependencies_value="", commands_value="", path_value="", platforms_value=""):
    is_main = str(name).strip() == "main"
    return html.Div([
        html.Div(
            children=[
                dcc.Input(
                    value=name,
                    type="text",
                    id={"type": "wf-task-field-name", "name": name},
                    className="title-input",
                    disabled=is_main,
                    style={
                        "width": "calc(100% - 20px)",
                        "marginLeft": "5px",
                        "marginRight": "5px",
                        "marginTop": "-5px",
                        "marginBottom": "2px",
                        "fontWeight": "bold",
                        "fontSize": "1.1em",
                        "height": "10px",
                        "textAlign": "center",
                    },
                ),
                html.Label("Dependencies", style={"fontWeight": "bold", "fontSize": "1em"}),
                dcc.Input(
                    value=dependencies_value,
                    type="text",
                    placeholder="task_a, task_b",
                    id={"type": "wf-task-field-dependencies", "name": name},
                    className="value-input",
                    style={"width": "100%", "marginBottom": "8px"},
                ),
                html.Label("Commands (one per line)", style={"fontWeight": "bold", "fontSize": "1em"}),
                dcc.Textarea(
                    value=commands_value,
                    id={"type": "wf-task-field-commands", "name": name},
                    className="auto-resize-textarea",
                    style={
                        "width": "100%",
                        "minHeight": "110px",
                        "resize": "vertical",
                        "fontFamily": "monospace",
                        "fontWeight": "500",
                        "marginBottom": "8px",
                    },
                ),
                html.Div(
                    children=[
                        html.Label("Path (optional)", style={"fontWeight": "bold", "fontSize": "1em"}),
                        dcc.Input(
                            value=path_value,
                            type="text",
                            id={"type": "wf-task-field-path", "name": name},
                            className="value-input",
                            style={"width": "100%", "marginBottom": "8px"},
                        ),
                        html.Label("Platforms (optional)", style={"fontWeight": "bold", "fontSize": "1em"}),
                        dcc.Input(
                            value=platforms_value,
                            type="text",
                            placeholder="linux, win32",
                            id={"type": "wf-task-field-platforms", "name": name},
                            className="value-input",
                            style={"width": "100%", "marginBottom": "8px"},
                        ),
                    ],
                    id={"type": "wf-more-task-field-div", "name": name},
                    className="expandable-area",
                    style=Style.hidden,
                ),
            ],
            style={"width": "calc(100% - 10px)"}
        ),
        html.Div([
            html.Div([
                ui.icon_button(
                    icon=icon("more", className="icon normal rotate", id={"type": "wf-more-task-fields-icon", "name": name}),
                    color="default",
                    id={"type": "wf-more-fields-task", "name": name},
                    tooltip="Show/Hide extra fields",
                    tooltip_options="bottom small",
                )
            ], id={"type": "wf-more-fields-task-div", "name": name}, style={"display": "flex", "alignItems": "center"}),
            html.Div([
                ui.duplicate_button(id={"type": "wf-duplicate-task", "name": name}),
                html.Div() if is_main else ui.delete_button(id={"type": "wf-delete-task", "name": name}),
            ], style={"display": "flex", "flexDirection": "horizontal", "alignItems": "center"}),
        ], style={
            "marginTop": "8px",
            "display": "flex",
            "flexDirection": "row",
            "width": "100%",
            "justifyContent": "space-between",
        }),
    ],
    className="tile config",
    style={"marginLeft": "10px"},
    id={"type": "wf-task-card", "name": name},
)

def wf_add_card(prefix: str = "wf-variable", text: str = "Add new variable", mode="variable"):
    return html.Div(
        html.Div(
            html.Div(
                children=[
                    html.Div(text, style={"fontWeight": "bold", "fontSize": "1.2em", "paddingTop": "20px"}),
                    html.Div(
                        "+",
                        style={
                            "fontSize": "2.5em",
                            "lineHeight": "80px",
                            "height": "80px",
                        }
                    ),
                ],
                style={"display": "flex", "flexDirection": "column", "alignItems": "center", "justifyContent": "center", "height": "100%"}
            ),
            id=f"{prefix}-new",
            n_clicks=0,
            style={"textDecoration": "none", "height": "100%"},
        ),
        className="tile config add hover" if mode == "task" else "card configs add hover",
        id=f"{prefix}-add-card",
        style= {
            "marginLeft": "10px",
        } if mode == "task" else {
            "padding": "10px",
            "margin": "5px",
            "display": "inline-block",
            "verticalAlign": "top",
            "boxSizing": "border-box"
        },
    )

def wf_cards_from_tasks(tasks):
    cards = []
    has_main = False
    if isinstance(tasks, list):
        for idx, task in enumerate(tasks):
            if not isinstance(task, dict):
                continue
            name = str(task.get("name", "")).strip()
            if name == "":
                name = f"task{idx + 1}"
            if name == "main":
                has_main = True

            dependencies = task.get("dependencies", [])
            if isinstance(dependencies, str):
                dependencies_value = dependencies
            elif isinstance(dependencies, list):
                dependencies_value = ", ".join([str(x) for x in dependencies if str(x).strip()])
            else:
                dependencies_value = ""

            commands = task.get("commands", [])
            if isinstance(commands, list):
                commands_value = "\n".join([str(x) for x in commands if str(x).strip()])
            elif isinstance(commands, str):
                commands_value = commands
            else:
                commands_value = ""

            path_value = str(task.get("path", "")) if task.get("path", "") is not None else ""

            platforms = task.get("platforms", "")
            if isinstance(platforms, list):
                platforms_value = ", ".join([str(x) for x in platforms if str(x).strip()])
            else:
                platforms_value = str(platforms) if platforms is not None else ""

            cards.append(
                wf_task_card(
                    name=name,
                    dependencies_value=dependencies_value,
                    commands_value=commands_value,
                    path_value=path_value,
                    platforms_value=platforms_value,
                )
            )
    if not has_main:
        cards.insert(0, wf_task_card(name="main"))
    cards.append(wf_add_card(prefix="wf-task", text="Add new task", mode="task"))
    return cards

def wf_cards_from_variables(variables):
    cards = []
    if isinstance(variables, dict):
        for var_name, var_keys in variables.items():
            if not isinstance(var_keys, dict):
                continue
            type_value = var_keys.get("type", "list")
            var_settings = var_keys.get("settings", {})
            cards.append(wf_variable_card(
                name=var_name,
                type_value=type_value,
                base_value=str(var_settings.get("base", "")),
                from_value=str(var_settings.get("from", "")),
                to_value=str(var_settings.get("to", "")),
                from_2_pow_value=str(var_settings.get("from_2^", "")),
                to_2_pow_value=str(var_settings.get("to_2^", "")),
                step_value=str(var_settings.get("step", "")),
                from_type_value=str(var_settings.get("from", "")),
                to_type_value=str(var_settings.get("to", "")),
                op_value=str(var_settings.get("op", "")),
                list_value=", ".join(map(str, var_settings.get("list", []))),
                source_value=str(var_settings.get("source", "")),
                sources_value=", ".join(map(str, var_settings.get("sources", []))),
                format_value=str(var_keys.get("format", "")),
            ))
    cards.append(wf_add_card(prefix="wf-variable", text="Add new variable"))
    return cards

@dash.callback(
    Output("wf-task-cards-row", "children", allow_duplicate=True),
    Input("wf-task-new", "n_clicks"),
    Input({"type": "wf-duplicate-task", "name": dash.ALL}, "n_clicks"),
    Input({"type": "wf-delete-task", "name": dash.ALL}, "n_clicks"),
    State("wf-task-cards-row", "children"),
    State({"type": "wf-task-field-name", "name": dash.ALL}, "value"),
    State({"type": "wf-task-field-dependencies", "name": dash.ALL}, "value"),
    State({"type": "wf-task-field-commands", "name": dash.ALL}, "value"),
    State({"type": "wf-task-field-path", "name": dash.ALL}, "value"),
    State({"type": "wf-task-field-platforms", "name": dash.ALL}, "value"),
    prevent_initial_call=True,
)
def update_wf_task_cards(
    new_click,
    duplicate_clicks,
    delete_clicks,
    cards,
    task_names,
    task_dependencies,
    task_commands,
    task_paths,
    task_platforms,
):
    trigger_id = ctx.triggered_id

    if cards is None:
        cards = []

    if cards and isinstance(cards[-1], dict) and cards[-1].get("props", {}).get("id") == "wf-task-add-card":
        cards = cards[:-1]

    if trigger_id == "wf-task-new" and new_click:
        existing_names = [
            card.get("props", {}).get("id", {}).get("name", "")
            for card in cards
            if isinstance(card.get("props", {}).get("id", {}), dict)
        ]
        idx = 1
        while f"task{idx}" in existing_names:
            idx += 1
        cards.append(wf_task_card(name=f"task{idx}"))

    if isinstance(trigger_id, dict):
        trig_type = trigger_id.get("type")
        trig_name = trigger_id.get("name")

        idx = None
        for i, card in enumerate(cards):
            card_id = card.get("props", {}).get("id", {})
            if isinstance(card_id, dict) and card_id.get("type") == "wf-task-card" and card_id.get("name") == trig_name:
                idx = i
                break

        if trig_type == "wf-delete-task" and idx is not None:
            if trig_name == "main":
                cards.append(wf_add_card(prefix="wf-task", text="Add new task", mode=task))
                return cards
            cards = [
                card for card in cards
                if not (
                    isinstance(card.get("props", {}).get("id", {}), dict)
                    and card.get("props", {}).get("id", {}).get("type") == "wf-task-card"
                    and card.get("props", {}).get("id", {}).get("name") == trig_name
                )
            ]
        elif trig_type == "wf-duplicate-task" and idx is not None and idx < len(duplicate_clicks) and duplicate_clicks[idx]:
            existing_names = [
                card.get("props", {}).get("id", {}).get("name", "")
                for card in cards
                if isinstance(card.get("props", {}).get("id", {}), dict)
            ]
            copy_idx = 1
            while f"{trig_name}_copy{copy_idx}" in existing_names:
                copy_idx += 1
            new_name = f"{trig_name}_copy{copy_idx}"

            cards.append(
                wf_task_card(
                    name=new_name,
                    dependencies_value=task_dependencies[idx] if idx < len(task_dependencies) else "",
                    commands_value=task_commands[idx] if idx < len(task_commands) else "",
                    path_value=task_paths[idx] if idx < len(task_paths) else "",
                    platforms_value=task_platforms[idx] if idx < len(task_platforms) else "",
                )
            )

    # Enforce mandatory main task card.
    has_main = False
    for card in cards:
        card_id = card.get("props", {}).get("id", {}) if isinstance(card, dict) else {}
        if isinstance(card_id, dict) and card_id.get("type") == "wf-task-card" and card_id.get("name") == "main":
            has_main = True
            break
    if not has_main:
        cards.insert(0, wf_task_card(name="main"))

    cards.append(wf_add_card(prefix="wf-task", text="Add new task", mode="task"))
    return cards


######################################
# Callbacks
######################################

@dash.callback(
    Output("workflow-form-container", "children"),
    Output("workflow-initial-settings", "data"),
    Output("wf-task-cards-row", "children"),
    Output("wf-variable-cards-row", "children"),
    Input(f"url_{page_path}", "search"),
    State(f"url_{page_path}", "pathname"),
    State("odatix-settings", "data"),
)
def init_form(search, page, odatix_settings):
    if page != page_path:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update

    workflow_name = get_key_from_url(search, "workflow")
    if not workflow_name:
        return workflow_form({}), {}, wf_cards_from_tasks([]), wf_cards_from_variables({})

    workflow_path = _get_workflow_path(odatix_settings)
    settings = normalize_workflow_settings(workspace.load_workflow_settings(workflow_path, workflow_name))
    variables = settings.get("generate_configurations_settings", {}).get("variables", {})
    tasks = settings.get("tasks", [])
    return workflow_form(settings), settings, wf_cards_from_tasks(tasks), wf_cards_from_variables(variables)

@dash.callback(
    Output({"page": page_path, "action": "save-all"}, "className"),
    Output({"page": page_path, "action": "save-all"}, "data-tooltip"),
    Output(f"url_{page_path}", "search"),
    Output("workflow-saved-settings", "data"),
    Input({"page": page_path, "action": "save-all"}, "n_clicks"),
    Input("workflow-title", "value"),
    Input("wf-source-path", "value"),
    Input("wf-source-whitelist", "value"),
    Input("wf-source-blacklist", "value"),
    Input("wf-use-parameters", "value"),
    Input("wf-param-target-file", "value"),
    Input("wf-start-delimiter", "value"),
    Input("wf-stop-delimiter", "value"),
    Input("wf-progress-file", "value"),
    Input("wf-progress-regex", "value"),
    Input({"type": "wf-task-field-name", "name": dash.ALL}, "value"),
    Input({"type": "wf-task-field-dependencies", "name": dash.ALL}, "value"),
    Input({"type": "wf-task-field-commands", "name": dash.ALL}, "value"),
    Input({"type": "wf-task-field-path", "name": dash.ALL}, "value"),
    Input({"type": "wf-task-field-platforms", "name": dash.ALL}, "value"),
    Input({"type": "wf-variable-title", "name": dash.ALL}, "value"),
    Input({"type": "wf-variable-type", "name": dash.ALL}, "value"),
    Input({"type": "wf-variable-field-base", "name": dash.ALL}, "value"),
    Input({"type": "wf-variable-field-from", "name": dash.ALL}, "value"),
    Input({"type": "wf-variable-field-to", "name": dash.ALL}, "value"),
    Input({"type": "wf-variable-field-from_2_pow", "name": dash.ALL}, "value"),
    Input({"type": "wf-variable-field-to_2_pow", "name": dash.ALL}, "value"),
    Input({"type": "wf-variable-field-from_type", "name": dash.ALL}, "value"),
    Input({"type": "wf-variable-field-to_type", "name": dash.ALL}, "value"),
    Input({"type": "wf-variable-field-step", "name": dash.ALL}, "value"),
    Input({"type": "wf-variable-field-op", "name": dash.ALL}, "value"),
    Input({"type": "wf-variable-field-list", "name": dash.ALL}, "value"),
    Input({"type": "wf-variable-field-source", "name": dash.ALL}, "value"),
    Input({"type": "wf-variable-field-sources", "name": dash.ALL}, "value"),
    Input({"type": "wf-variable-field-format", "name": dash.ALL}, "value"),
    State(f"url_{page_path}", "search"),
    State(f"url_{page_path}", "pathname"),
    State("workflow-initial-settings", "data"),
    State("workflow-saved-settings", "data"),
    State("odatix-settings", "data"),
    prevent_initial_call=True,
)
def save_and_status(
    n_clicks,
    workflow_title_value,
    source_path,
    source_whitelist,
    source_blacklist,
    use_parameters,
    param_target_file,
    start_delimiter,
    stop_delimiter,
    progress_file,
    progress_regex,
    task_names,
    task_dependencies,
    task_commands,
    task_paths,
    task_platforms,
    variable_titles,
    variable_types,
    variable_base_vals,
    variable_from_vals,
    variable_to_vals,
    variable_from_2_pow_vals,
    variable_to_2_pow_vals,
    variable_from_type_vals,
    variable_to_type_vals,
    variable_step_vals,
    variable_op_vals,
    variable_list_vals,
    variable_source_vals,
    variable_sources_vals,
    variable_format_vals,
    search,
    page,
    initial_settings,
    saved_settings,
    odatix_settings,
):
    triggered_id = ctx.triggered_id
    if triggered_id == f"url_{page_path}" and page != page_path:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update

    if saved_settings is None:
        reference_settings = normalize_workflow_settings(initial_settings)
    else:
        reference_settings = normalize_workflow_settings(saved_settings)

    parsed_tasks = wf_build_tasks_list(
        task_names,
        task_dependencies,
        task_commands,
        task_paths,
        task_platforms,
    )

    variables = wf_build_variables_dict(
        variable_titles, variable_types, variable_base_vals, variable_from_vals, variable_to_vals,
        variable_from_2_pow_vals, variable_to_2_pow_vals, variable_from_type_vals, variable_to_type_vals,
        variable_step_vals, variable_op_vals, variable_list_vals, variable_source_vals, variable_sources_vals,
        variable_format_vals,
    )
    generate_configurations_settings = dict(reference_settings.get("generate_configurations_settings", {}))
    generate_configurations_settings["variables"] = variables

    current_settings = normalize_workflow_settings(
        {
            "sources": {
                "path": source_path or "",
                "whitelist": _normalize_list(source_whitelist),
                "blacklist": _normalize_list(source_blacklist),
            },
            "use_parameters": True if use_parameters else False,
            "param_target_file": param_target_file or "",
            "start_delimiter": start_delimiter or "",
            "stop_delimiter": stop_delimiter or "",
            "progress": {
                "file": progress_file or "",
                "regex": progress_regex or "",
            },
            "generate_configurations_settings": generate_configurations_settings,
            "tasks": parsed_tasks,
        }
    )

    workflow_name = get_key_from_url(search, "workflow")
    workflow_path = _get_workflow_path(odatix_settings)

    if not workflow_title_value:
        return (
            "color-button error-status icon-button tooltip bottom",
            "Workflow name cannot be empty",
            dash.no_update,
            saved_settings,
        )

    for character in hard_settings.invalid_filename_characters:
        if character in workflow_title_value:
            label = "' ' (space)" if character == " " else f"'{character}'"
            return (
                "color-button error-status icon-button tooltip bottom",
                f"Unauthorized character in workflow name: {label}",
                dash.no_update,
                saved_settings,
            )

    if triggered_id == {"page": page_path, "action": "save-all"}:
        new_search = dash.no_update

        if workflow_name and workflow_title_value != workflow_name:
            if workspace.workflow_exists(workflow_path, workflow_title_value):
                return (
                    "color-button error-status icon-button tooltip bottom",
                    f"'{workflow_title_value}' already exists",
                    dash.no_update,
                    saved_settings,
                )
            if workspace.workflow_exists(workflow_path, workflow_name):
                workspace.rename_workflow(workflow_path, workflow_name, workflow_title_value)
            workflow_name = workflow_title_value
            new_search = f"?workflow={workflow_name}"
        elif not workflow_name:
            workflow_name = workflow_title_value
            new_search = f"?workflow={workflow_name}"

        if not workspace.workflow_exists(workflow_path, workflow_name):
            workspace.create_workflow(workflow_path, workflow_name)

        try:
            workspace.save_workflow_settings(workflow_path, workflow_name, current_settings)
            return (
                "color-button disabled icon-button tooltip delay bottom small",
                "Nothing to save",
                new_search,
                current_settings,
            )
        except Exception:
            return (
                "color-button error-status icon-button tooltip bottom small",
                "Failed to save...",
                dash.no_update,
                saved_settings,
            )

    if current_settings != reference_settings or workflow_title_value != (workflow_name or ""):
        return (
            "color-button warning icon-button tooltip bottom small tooltip",
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

@dash.callback(
    Output("wf-params-config-fields", "className"),
    Input("wf-use-parameters", "value"),
)
def toggle_parameter_fields(use_parameters):
    return "animated-section" if use_parameters else "animated-section hide"

@dash.callback(
    Output({"page": page_path, "type": "workflow-title-div"}, "children"),
    Input(f"url_{page_path}", "search"),
)
def update_workflow_title(search):
    workflow_name = get_key_from_url(search, "workflow")
    if not workflow_name:
        workflow_name = ""
    return workflow_title(workflow_name)

@dash.callback(
    [
        Output({"type": "wf-variable-field-from-div", "name": dash.ALL}, "style"),
        Output({"type": "wf-variable-field-to-div", "name": dash.ALL}, "style"),
        Output({"type": "wf-variable-field-from_2_pow-div", "name": dash.ALL}, "style"),
        Output({"type": "wf-variable-field-to_2_pow-div", "name": dash.ALL}, "style"),
        Output({"type": "wf-variable-field-from_type-div", "name": dash.ALL}, "style"),
        Output({"type": "wf-variable-field-to_type-div", "name": dash.ALL}, "style"),
        Output({"type": "wf-variable-field-base-div", "name": dash.ALL}, "style"),
        Output({"type": "wf-variable-field-step-div", "name": dash.ALL}, "style"),
        Output({"type": "wf-variable-field-op-div", "name": dash.ALL}, "style"),
        Output({"type": "wf-variable-field-list-div", "name": dash.ALL}, "style"),
        Output({"type": "wf-variable-field-source-div", "name": dash.ALL}, "style"),
        Output({"type": "wf-variable-field-sources-div", "name": dash.ALL}, "style"),
        Output({"type": "wf-variable-field-format-div", "name": dash.ALL}, "style"),
    ],
    Input({"type": "wf-variable-type", "name": dash.ALL}, "value"),
)
def update_wf_variable_fields_visibility(types):
    # Required fields for each type
    mapping = {
        "bool":              {"format"},
        "list":              {"list", "format"},
        "range":             {"from", "to", "step", "format"},
        "power_of_two":      {"from_2_pow", "to_2_pow", "format"},
        "multiples":         {"base", "from", "to", "format"},
        "function":          {"op", "format"},
        "conversion":        {"from_type", "to_type", "source", "format"},
        "format":            {"source", "format"},
        "union":             {"sources", "format"},
        "disjunctive_union": {"sources", "format"},
        "intersection":      {"sources", "format"},
        "difference":        {"sources", "format"},
    }
    all_fields = ["from", "to", "from_2_pow", "to_2_pow", "from_type", "to_type", "base", "step", "op", "list", "source", "sources", "format"]

    styles_by_field = {field: [] for field in all_fields}
    for t in types:
        visible = mapping.get(t, set())
        for field in all_fields:
            styles_by_field[field].append(Style.visible if field in visible else Style.hidden)

    return (
        styles_by_field["from"],
        styles_by_field["to"],
        styles_by_field["from_2_pow"],
        styles_by_field["to_2_pow"],
        styles_by_field["from_type"],
        styles_by_field["to_type"],
        styles_by_field["base"],
        styles_by_field["step"],
        styles_by_field["op"],
        styles_by_field["list"],
        styles_by_field["source"],
        styles_by_field["sources"],
        styles_by_field["format"],
    )

@dash.callback(
    Output({"type": "wf-more-variable-field-div", "name": dash.ALL}, "style"),
    Output({"type": "wf-more-fields-icon", "name": dash.ALL}, "className"),
    Input({"type": "wf-more-fields", "name": dash.ALL}, "n_clicks"),
    State({"type": "wf-more-variable-field-div", "name": dash.ALL}, "style"),
    State({"type": "wf-more-fields-icon", "name": dash.ALL}, "className"),
    State({"type": "wf-variable-metadata", "name": dash.ALL}, "data"),
)
def toggle_wf_more_fields(n_clicks, expandable_area_styles, icon_classes, metadata):
    trigger_id = ctx.triggered_id
    if not isinstance(trigger_id, dict) or "name" not in trigger_id:
        return [dash.no_update] * len(n_clicks), [dash.no_update] * len(n_clicks)

    index = None
    for i, clicks in enumerate(n_clicks):
        current_name = metadata[i].get("name") if metadata and i < len(metadata) else {}
        if trigger_id.get("name") == current_name:
            index = i
            break

    new_expandable_area_styles = list(expandable_area_styles)
    new_icon_classes = list(icon_classes)
    if index is not None:
        if n_clicks[index] % 2 == 0:
            new_expandable_area_styles[index] = Style.hidden
            new_icon_classes[index] = "icon normal rotate"
        else:
            new_expandable_area_styles[index] = Style.visible
            new_icon_classes[index] = "icon normal rotate rotated"
    return new_expandable_area_styles, new_icon_classes

@dash.callback(
    Output({"type": "wf-more-task-field-div", "name": dash.ALL}, "style"),
    Output({"type": "wf-more-task-fields-icon", "name": dash.ALL}, "className"),
    Input({"type": "wf-more-fields-task", "name": dash.ALL}, "n_clicks"),
    State({"type": "wf-more-task-field-div", "name": dash.ALL}, "style"),
    State({"type": "wf-more-task-fields-icon", "name": dash.ALL}, "className"),
    State({"type": "wf-task-field-name", "name": dash.ALL}, "value"),
)
def toggle_wf_task_more_fields(n_clicks, expandable_area_styles, icon_classes, task_names):
    trigger_id = ctx.triggered_id
    if not isinstance(trigger_id, dict) or "name" not in trigger_id:
        return [dash.no_update] * len(n_clicks), [dash.no_update] * len(n_clicks)

    index = None
    for i, current_name in enumerate(task_names):
        if trigger_id.get("name") == current_name:
            index = i
            break

    new_expandable_area_styles = list(expandable_area_styles)
    new_icon_classes = list(icon_classes)
    if index is not None:
        if n_clicks[index] % 2 == 0:
            new_expandable_area_styles[index] = Style.hidden
            new_icon_classes[index] = "icon normal rotate"
        else:
            new_expandable_area_styles[index] = Style.visible
            new_icon_classes[index] = "icon normal rotate rotated"
    return new_expandable_area_styles, new_icon_classes

@dash.callback(
    Output("wf-variable-cards-row", "children", allow_duplicate=True),
    Input("wf-new-variable", "n_clicks"),
    Input({"type": "wf-duplicate-var", "name": dash.ALL}, "n_clicks"),
    Input({"type": "wf-delete-var", "name": dash.ALL}, "n_clicks"),
    State("wf-variable-cards-row", "children"),
    State({"type": "wf-variable-type", "name": dash.ALL}, "value"),
    State({"type": "wf-variable-field-base", "name": dash.ALL}, "value"),
    State({"type": "wf-variable-field-from", "name": dash.ALL}, "value"),
    State({"type": "wf-variable-field-to", "name": dash.ALL}, "value"),
    State({"type": "wf-variable-field-from_2_pow", "name": dash.ALL}, "value"),
    State({"type": "wf-variable-field-to_2_pow", "name": dash.ALL}, "value"),
    State({"type": "wf-variable-field-from_type", "name": dash.ALL}, "value"),
    State({"type": "wf-variable-field-to_type", "name": dash.ALL}, "value"),
    State({"type": "wf-variable-field-step", "name": dash.ALL}, "value"),
    State({"type": "wf-variable-field-op", "name": dash.ALL}, "value"),
    State({"type": "wf-variable-field-list", "name": dash.ALL}, "value"),
    State({"type": "wf-variable-field-source", "name": dash.ALL}, "value"),
    State({"type": "wf-variable-field-sources", "name": dash.ALL}, "value"),
    prevent_initial_call=True,
)
def update_wf_variable_cards(
    new_click, duplicate_clicks, delete_clicks, cards,
    types, base_vals, from_vals, to_vals, from_2_pow_vals, to_2_pow_vals, from_type_vals, to_type_vals, step_vals, op_vals, list_vals, source_vals, sources_vals,
):
    trigger_id = ctx.triggered_id

    if cards is None:
        cards = []

    # Remove the Add card if present
    if cards and isinstance(cards[-1], dict) and cards[-1].get('props', {}).get('id') == "wf-variable-add-card":
        cards = cards[:-1]

    # Add new variable
    if trigger_id == "wf-new-variable" and new_click:
        existing_names = [card.get('props', {}).get('id', {}).get('name', '') for card in cards if isinstance(card.get('props', {}).get('id', {}), dict)]
        var_idx = 1
        while f"var{var_idx}" in existing_names:
            var_idx += 1
        new_name = f"var{var_idx}"
        cards.append(wf_variable_card(new_name))

    if isinstance(trigger_id, dict):
        trig_type = trigger_id.get("type")
        trig_name = trigger_id.get("name")

        idx = None
        for i, card in enumerate(cards):
            card_id = card.get('props', {}).get('id', {})
            if isinstance(card_id, dict) and card_id.get("type") == "wf-variable-card" and card_id.get("name") == trig_name:
                idx = i
                break

        # Delete (guard against spurious firing when cards are (re)mounted, e.g. on page load)
        if trig_type == "wf-delete-var" and idx is not None and idx < len(delete_clicks) and delete_clicks[idx]:
            cards = [
                card for card in cards
                if not (
                    isinstance(card.get('props', {}).get('id', {}), dict)
                    and card.get('props', {}).get('id', {}).get("type") == "wf-variable-card"
                    and card.get('props', {}).get('id', {}).get("name") == trig_name
                )
            ]
        # Duplicate (same guard)
        elif trig_type == "wf-duplicate-var" and idx is not None and idx < len(duplicate_clicks) and duplicate_clicks[idx]:
            existing_names = [card.get('props', {}).get('id', {}).get('name', '') for card in cards if isinstance(card.get('props', {}).get('id', {}), dict)]
            copy_idx = 1
            while f"{trig_name}_copy{copy_idx}" in existing_names:
                copy_idx += 1
            new_name = f"{trig_name}_copy{copy_idx}"

            cards.append(wf_variable_card(
                        name=new_name,
                        type_value=types[idx],
                        base_value=base_vals[idx],
                        from_value=from_vals[idx],
                        to_value=to_vals[idx],
                        from_2_pow_value=from_2_pow_vals[idx],
                        to_2_pow_value=to_2_pow_vals[idx],
                        from_type_value=from_vals[idx],
                        to_type_value=to_vals[idx],
                        step_value=step_vals[idx],
                        op_value=op_vals[idx],
                        list_value=list_vals[idx],
                        source_value=sources_vals[idx],
                        sources_value=sources_vals[idx],
                    ))

    cards.append(wf_add_card())
    return cards


######################################
# Layout
######################################

layout = html.Div(
    children=[
        dcc.Location(id=f"url_{page_path}"),
        html.Div(id={"page": page_path, "type": "workflow-title-div"}, style={"marginTop": "20px"}),
        html.Div(id="workflow-form-container"),
        html.Div(
            children=[
                ui.title_tile(text="Task Definition", id="wf-task-title", tooltip="Tasks can be used to define the steps of the workflow."),
                html.Div([
                    html.Div(
                        id="wf-task-cards-row",
                        children=[wf_add_card(prefix="wf-task", text="Add new task", mode="task")],
                        className="tiles-container config",
                        style={"display": "flex", "justifyContent": "flex-start", "alignItems": "flex-start", "flexWrap": "wrap", "marginBottom": "30px"},
                    ),
                ]),
                ui.title_tile(text="Variable Definition", id="wf-variable-title", tooltip="Variables can be used inside commands and can also be used to generate configurations."),
                html.Div([
                    html.Div(
                        id="wf-variable-cards-row",
                        children=[wf_add_card(prefix="wf-variable", text="Add new variable")],
                        className="card-matrix configs",
                        style={"marginLeft": "13px", "marginBottom": "30px"},
                    ),
                ]),
            ],
            style={"marginLeft": "-13px"}
        ),
        dcc.Store(id="workflow-initial-settings", data=None),
        dcc.Store(id="workflow-saved-settings", data=None),
    ],
    className="page-content",
    style={
        "display": "flex",
        "flexDirection": "column",
        "min-height": f"calc(100vh - {navigation.top_bar_height})",
    },
)