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

from odatix.gui.icons import icon
from odatix.gui.utils import get_key_from_url, get_workspace
from odatix.gui.css_helper import Style
import odatix.gui.ui_components as ui
import odatix.gui.navigation as navigation
import odatix.gui.builtin_variables as builtin_variables
import odatix.lib.hard_settings as hard_settings
import odatix.gui.variable_editor as ve
import odatix.gui.task_editor as te
from odatix.lib.config_generator import get_variables
from odatix.gui.page_scope import page_callback, scoped

# Scope anchoring the callbacks below: they are dispatched only on the pages
# embedding the matching anchor store (see odatix.gui.page_scope).
PAGE_SCOPE = "workflow_editor"

# Variable-editor id namespace for this page.
VE_PREFIX = "wf-"

page_path = "/workflow_editor"

dash.register_page(
    __name__,
    path=page_path,
    title="Odatix - Workflow editor",
    name="Workflow editor",
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

    # Variables are declared at the root of the settings file, but are still
    # read from where they used to be declared.
    variables, _legacy = get_variables(settings)

    try:
        vars_copy = {}
        for vname, vcfg in variables.items():
            if not isinstance(vcfg, dict):
                vars_copy[vname] = vcfg
                continue

            # Only keep canonical keys
            v_type = vcfg.get("type")
            v_format = vcfg.get("format") if "format" in vcfg else None
            v_group = vcfg.get("group") if "group" in vcfg else None
            vsettings = vcfg.get("settings", {}) if isinstance(vcfg.get("settings", {}), dict) else {}

            # Normalize list elements to strings when present
            if "list" in vsettings and isinstance(vsettings["list"], (list, tuple)):
                vsettings = dict(vsettings)
                vsettings["list"] = [str(x) for x in vsettings["list"]]

            new_vcfg = {"type": v_type, "settings": vsettings}
            if v_format:
                new_vcfg["format"] = v_format
            if v_group:
                new_vcfg["group"] = v_group

            vars_copy[vname] = new_vcfg

        variables = vars_copy
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
        "variables": variables,
    }

def format_tasks(tasks):
    if not isinstance(tasks, list) or len(tasks) == 0:
        return ""
    return yaml.safe_dump(tasks, sort_keys=False, default_flow_style=False).strip()

def wf_build_tasks_list(*field_values):
    """
    Build the workflow tasks list from the task card field values (one list per
    field of task_editor.TASK_FIELDS). A workflow always has its "main" task.
    """
    tasks = te.build_tasks_list(*field_values)
    if not any(task["name"] == "main" for task in tasks):
        tasks.insert(0, {"name": "main", "commands": []})
    return tasks

def wf_build_variables_dict(
    titles, types, base_vals, from_vals, to_vals, from_2_pow_vals, to_2_pow_vals, from_type_vals, to_type_vals, step_vals, op_vals, list_vals, source_vals, sources_vals, format_vals, group_vals
):
    """
    Build a "variables" dict from the variable card field values.
    """
    return ve.build_variables_dict(
        titles, types, base_vals, from_vals, to_vals, from_2_pow_vals, to_2_pow_vals,
        from_type_vals, to_type_vals, step_vals, op_vals, list_vals, source_vals, sources_vals,
        format_vals, group_vals,
    )


######################################
# UI Components
######################################

def workflow_title(workflow_name):
    title_buttons = html.Div(
        children=[
            ui.icon_button(
                id=f"button-open-metric-editor",
                icon=icon("metrics", className="icon blue"),
                text="Edit metrics",
                tooltip="Open the exported metrics editor for this workflow",
                tooltip_options="bottom delay",
                color="default",
                link=f"/metric_editor?workflow={workflow_name}",
                multiline=False,
                width="135px",
            ),
            ui.icon_button(
                id=f"button-open-config-editor",
                icon=icon("edit", className="icon blue"),
                text="Edit configs",
                tooltip="Open the configuration editor for this workflow",
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
                                    placeholder="Workflow name...",
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
        style={"marginTop": "0px", "marginBottom": "10px"},
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
                    html.H3("Workflow sources"),
                    workflow_form_field(
                        label="Source path",
                        id="wf-source-path",
                        value=sources.get("path", ""),
                        tooltip="Directory copied in each workflow work directory before running tasks.",
                    ),
                    workflow_form_field(
                        label="Source whitelist",
                        id="wf-source-whitelist",
                        value=", ".join(sources.get("whitelist", [])),
                        placeholder="src/**, scripts/**",
                        tooltip="Optional comma-separated inclusion patterns.",
                    ),
                    workflow_form_field(
                        label="Source blacklist",
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
                    html.H3("Parameters replacement"),
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
                                label="Parameter target file",
                                id="wf-param-target-file",
                                value=defval("param_target_file", ""),
                                tooltip="File in the copied sources where replacements are applied.",
                            ),
                            workflow_form_field(
                                label="Start delimiter",
                                id="wf-start-delimiter",
                                value=defval("start_delimiter", ""),
                                tooltip="Start marker for replacement. Escape sequences such as \\n are supported.",
                            ),
                            workflow_form_field(
                                label="Stop delimiter",
                                id="wf-stop-delimiter",
                                value=defval("stop_delimiter", ""),
                                tooltip="Stop marker for replacement. Escape sequences such as \\n are supported.",
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
                    html.H3("Progress tracking"),
                    workflow_form_field(
                        label="Progress file",
                        id="wf-progress-file",
                        value=progress.get("file", ""),
                        tooltip="Path of the progress file generated by tasks.",
                    ),
                    workflow_form_field(
                        label="Progress regex",
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

def wf_task_card(name="main", **values):
    return te.task_card("wf", name=name, values=values)

def wf_add_card(prefix: str = "wf-variable", text: str = "Add new variable", mode="variable"):
    return html.Div(
        html.Div(
            html.Div(
                children=[
                    html.Div("+", style={"fontSize": "2.5em", "lineHeight": "80px", "height": "80px", "marginTop": "-2px", "marginBottom": "-16px"}),
                    html.Div(text, style={"fontWeight": "bold", "fontSize": "1.2em", "paddingBottom": "20px"}),
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
        } if mode == "task" else {
            "padding": "10px",
            "margin": "5px",
            "display": "inline-block",
            "verticalAlign": "top",
            "boxSizing": "border-box"
        },
    )

def wf_cards_from_tasks(tasks):
    cards = te.cards_from_tasks("wf", tasks)
    if not any(card.id.get("name") == "main" for card in cards):
        cards.insert(0, wf_task_card(name="main"))
    cards.append(wf_add_card(prefix="wf-task", text="Add new task", mode="task"))
    return cards

def wf_cards_from_variables(variables):
    cards = ve.variable_cards_from_dict(VE_PREFIX, variables)
    cards.append(wf_add_card(prefix="wf-variable", text="Add new variable"))
    return cards

@dash.callback(
    Output("wf-task-cards-row", "children", allow_duplicate=True),
    Input("wf-task-new", "n_clicks"),
    Input({"type": "wf-duplicate-task", "name": dash.ALL}, "n_clicks"),
    Input({"type": "wf-delete-task", "name": dash.ALL}, "n_clicks"),
    State("wf-task-cards-row", "children"),
    *te.task_field_dependencies("wf", State),
    prevent_initial_call=True,
)
def update_wf_task_cards(new_click, duplicate_clicks, delete_clicks, cards, *task_fields):
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
                cards.append(wf_add_card(prefix="wf-task", text="Add new task", mode="task"))
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

            cards.append(wf_task_card(name=new_name, **te.card_values(task_fields, idx)))

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

    workflows = get_workspace(odatix_settings).workflows
    settings = normalize_workflow_settings(workflows.entry(workflow_name).settings.to_dict())
    variables = settings.get("variables", {})
    tasks = settings.get("tasks", [])
    return workflow_form(settings), settings, wf_cards_from_tasks(tasks), wf_cards_from_variables(variables)

@dash.callback(
    Output("wf-hl-param-domains", "data"),
    Input(f"url_{page_path}", "search"),
    State(f"url_{page_path}", "pathname"),
    State("odatix-settings", "data"),
)
def update_wf_param_domains(search, page, odatix_settings):
    """
    The workflow's parameter domains (its subdirectories), so the command
    highlighter can color them apart from defined variables. Empty for a new,
    unsaved workflow.
    """
    if page != page_path:
        return dash.no_update
    workflow_name = get_key_from_url(search, "workflow")
    if not workflow_name:
        return []
    try:
        return get_workspace(odatix_settings).workflows.entry(workflow_name).domains.sub_names()
    except Exception:
        return []


# Push the parameter domains to the client and ask the highlighter to redraw.
dash.clientside_callback(
    dash.ClientsideFunction(namespace="odatix_highlight", function_name="push_names"),
    Output("wf-hl-dummy", "data"),
    Input("wf-hl-param-domains", "data"),
)


@dash.callback(
    Output({"page": page_path, "action": "save-all"}, "className"),
    Output({"page": page_path, "action": "save-all"}, "data-tooltip"),
    Output(f"url_{page_path}", "search"),
    Output("workflow-saved-settings", "data"),
    Output("workflow-save-feedback", "children"),
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
    *te.task_field_dependencies("wf", Input),
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
    Input({"type": "wf-variable-field-group", "name": dash.ALL}, "value"),
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
    task_on_failure_commands,
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
    variable_group_vals,
    search,
    page,
    initial_settings,
    saved_settings,
    odatix_settings,
):
    triggered_id = ctx.triggered_id
    saving = triggered_id == {"page": page_path, "action": "save-all"}
    if triggered_id == f"url_{page_path}" and page != page_path:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update

    if saved_settings is None:
        reference_settings = normalize_workflow_settings(initial_settings)
    else:
        reference_settings = normalize_workflow_settings(saved_settings)

    parsed_tasks = wf_build_tasks_list(
        task_names,
        task_dependencies,
        task_commands,
        task_on_failure_commands,
        task_paths,
        task_platforms,
    )

    variables = wf_build_variables_dict(
        variable_titles, variable_types, variable_base_vals, variable_from_vals, variable_to_vals,
        variable_from_2_pow_vals, variable_to_2_pow_vals, variable_from_type_vals, variable_to_type_vals,
        variable_step_vals, variable_op_vals, variable_list_vals, variable_source_vals, variable_sources_vals,
        variable_format_vals, variable_group_vals,
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
            "variables": variables,
            "tasks": parsed_tasks,
        }
    )

    workflow_name = get_key_from_url(search, "workflow")
    workflows = get_workspace(odatix_settings).workflows

    if not workflow_title_value:
        return (
            "color-button error-status icon-button tooltip bottom",
            "Workflow name cannot be empty",
            dash.no_update,
            saved_settings,
            (ui.error("Not saved: Workflow name cannot be empty") if saving else dash.no_update),
        )

    for character in hard_settings.invalid_filename_characters:
        if character in workflow_title_value:
            label = "' ' (space)" if character == " " else f"'{character}'"
            return (
                "color-button error-status icon-button tooltip bottom",
                f"Unauthorized character in workflow name: {label}",
                dash.no_update,
                saved_settings,
                (ui.error(f"Not saved: Unauthorized character in workflow name: {label}") if saving else dash.no_update),
            )

    if triggered_id == {"page": page_path, "action": "save-all"}:
        new_search = dash.no_update

        if workflow_name and workflow_title_value != workflow_name:
            if workflow_title_value in workflows:
                return (
                    "color-button error-status icon-button tooltip bottom",
                    f"'{workflow_title_value}' already exists",
                    dash.no_update,
                    saved_settings,
                    (ui.error(f"Not saved: '{workflow_title_value}' already exists") if saving else dash.no_update),
                )
            if workflow_name in workflows:
                workflows.rename(workflow_name, workflow_title_value)
            workflow_name = workflow_title_value
            new_search = f"?workflow={workflow_name}"
        elif not workflow_name:
            workflow_name = workflow_title_value
            new_search = f"?workflow={workflow_name}"

        workflow = workflows.get(workflow_name)
        if workflow is None:
            workflow = workflows.create(workflow_name)

        try:
            workflow.update(current_settings)
            return (
                "color-button disabled icon-button tooltip delay bottom small",
                "Nothing to save",
                new_search,
                current_settings,
                ui.success(),
            )
        except Exception as e:
            return (
                "color-button error-status icon-button tooltip bottom small",
                "Failed to save...",
                dash.no_update,
                saved_settings,
                ui.error(f"Not saved: {e}"),
            )

    if current_settings != reference_settings or workflow_title_value != (workflow_name or ""):
        return (
            "color-button warning icon-button tooltip bottom small tooltip",
            "Unsaved changes!",
            dash.no_update,
            dash.no_update,
            dash.no_update,
        )

    return (
        "color-button disabled icon-button tooltip delay bottom small",
        "Nothing to save",
        dash.no_update,
        saved_settings,
        dash.no_update,
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

@page_callback(PAGE_SCOPE,
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
        Output({"type": "wf-variable-field-group-div", "name": dash.ALL}, "style"),
    ],
    Input({"type": "wf-variable-type", "name": dash.ALL}, "value"),
)
def update_wf_variable_fields_visibility(types):
    styles_by_field = ve.field_styles_for_types(types)
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
        styles_by_field["group"],
    )

# Folding the extra fields away is done on the client, on the document, by the
# handler in assets/folds.js: nothing outside the browser reads whether a fold
# is open, and a fold answered by Dash costs a walk over every pattern-matched
# component of the page.

@dash.callback(
    Output("wf-variable-cards-row", "children", allow_duplicate=True),
    Input("wf-variable-new", "n_clicks"),
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
    State({"type": "wf-variable-field-group", "name": dash.ALL}, "value"),
    prevent_initial_call=True,
)
def update_wf_variable_cards(
    new_click, duplicate_clicks, delete_clicks, cards,
    types, base_vals, from_vals, to_vals, from_2_pow_vals, to_2_pow_vals, from_type_vals, to_type_vals, step_vals, op_vals, list_vals, source_vals, sources_vals, group_vals,
):
    trigger_id = ctx.triggered_id

    if cards is None:
        cards = []

    # Remove the Add card if present
    if cards and isinstance(cards[-1], dict) and cards[-1].get('props', {}).get('id') == "wf-variable-add-card":
        cards = cards[:-1]

    # Add new variable
    if trigger_id == "wf-variable-new" and new_click:
        existing_names = [card.get('props', {}).get('id', {}).get('name', '') for card in cards if isinstance(card.get('props', {}).get('id', {}), dict)]
        var_idx = 1
        while f"var{var_idx}" in existing_names:
            var_idx += 1
        new_name = f"var{var_idx}"
        cards.append(ve.variable_card(VE_PREFIX, new_name))

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

            cards.append(ve.variable_card(
                        VE_PREFIX,
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
                        group_value=group_vals[idx],
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
        html.Div(ui.feedback("workflow-save-feedback"), className="card-matrix config"),
        html.Div(id="workflow-form-container"),
        html.Div(
            children=[
                ui.title_tile(
                    text="Task definition", id="wf-task-title",
                    tooltip="Tasks can be used to define the steps of the workflow.",
                    buttons=builtin_variables.variable_list("workflow", id="wf-builtin-variables"),
                ),
                html.Div([
                    html.Div(
                        id="wf-task-cards-row",
                        children=[wf_add_card(prefix="wf-task", text="Add new task", mode="task")],
                        className="tiles-container config",
                        style={"display": "flex", "justifyContent": "flex-start", "alignItems": "flex-start", "flexWrap": "wrap", "marginBottom": "30px", "columnGap": "var(--tile-gap)"},
                    ),
                ]),
                ui.title_tile(text="Variable definition", id="wf-variable-title", tooltip="Variables can be used inside commands and can also be used to generate configurations."),
                html.Div([
                    html.Div(
                        id="wf-variable-cards-row",
                        children=[wf_add_card(prefix="wf-variable", text="Add new variable")],
                        className="card-matrix configs",
                        style={"marginBottom": "30px"},
                    ),
                ]),
            ],
        ),
        dcc.Store(id="workflow-initial-settings", data=None),
        dcc.Store(id="workflow-saved-settings", data=None),
        # Physical parameter domains of the workflow (directory names), pushed to
        # the client so the command highlighter can tell them apart from defined
        # variables (which it reads live from the variable cards).
        dcc.Store(id="wf-hl-param-domains", data=[]),
        dcc.Store(id="wf-hl-dummy", data=""),
        # A workflow command has no built-in variable, but declaring the (empty)
        # list keeps a stale one from another editor out of this page.
        builtin_variables.highlight_data("workflow", id="wf-hl-builtins", declares_variables=True),
    ],
    className="page-content",
    style={
        "display": "flex",
        "flexDirection": "column",
        "min-height": f"calc(100vh - {navigation.top_bar_height})",
    },
)

# Anchor of PAGE_SCOPE: makes this page the only one dispatching its callbacks.
layout = scoped(PAGE_SCOPE, layout)
