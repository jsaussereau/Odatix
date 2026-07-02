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

import odatix.components.workspace as workspace
from odatix.gui.icons import icon
from odatix.gui.utils import get_key_from_url
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
    }

def format_tasks(tasks):
    if not isinstance(tasks, list) or len(tasks) == 0:
        return ""
    return yaml.safe_dump(tasks, sort_keys=False, default_flow_style=False).strip()


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
            html.Div(
                [
                    html.H3("Tasks (YAML List)"),
                    ui.tooltip_icon("List of workflow tasks (name, dependencies, commands, optional path/platforms)."),
                    dcc.Textarea(
                        id="wf-tasks-yaml",
                        value=format_tasks(defval("tasks", [])),
                        className="auto-resize-textarea",
                        style={
                            "width": "100%",
                            "minHeight": "220px",
                            "resize": "vertical",
                            "fontFamily": "monospace",
                            "fontWeight": "500",
                        },
                    ),
                ],
                className="tile config",
            ),
        ],
        className="tiles-container config",
        style={"marginTop": "-10px", "marginBottom": "20px"},
    )


######################################
# Callbacks
######################################

@dash.callback(
    Output("workflow-form-container", "children"),
    Output("workflow-initial-settings", "data"),
    Input(f"url_{page_path}", "search"),
    State(f"url_{page_path}", "pathname"),
    State("odatix-settings", "data"),
)
def init_form(search, page, odatix_settings):
    if page != page_path:
        return dash.no_update, dash.no_update

    workflow_name = get_key_from_url(search, "workflow")
    if not workflow_name:
        return workflow_form({}), {}

    workflow_path = _get_workflow_path(odatix_settings)
    settings = normalize_workflow_settings(workspace.load_workflow_settings(workflow_path, workflow_name))
    return workflow_form(settings), settings

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
    Input("wf-tasks-yaml", "value"),
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
    tasks_yaml,
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

    try:
        parsed_tasks = yaml.safe_load(tasks_yaml) if tasks_yaml and tasks_yaml.strip() else []
    except Exception:
        return (
            "color-button error-status icon-button tooltip bottom",
            "Invalid YAML in tasks section",
            dash.no_update,
            saved_settings,
        )

    if parsed_tasks is None:
        parsed_tasks = []

    if not isinstance(parsed_tasks, list):
        return (
            "color-button error-status icon-button tooltip bottom",
            "Tasks must be a YAML list",
            dash.no_update,
            saved_settings,
        )

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


######################################
# Layout
######################################

layout = html.Div(
    children=[
        dcc.Location(id=f"url_{page_path}"),
        html.Div(id={"page": page_path, "type": "workflow-title-div"}, style={"marginTop": "20px"}),
        html.Div(id="workflow-form-container"),
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