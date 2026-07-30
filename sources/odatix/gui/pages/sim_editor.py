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
Simulation Editor page (/sim_editor?sim=<name>).

Edits a simulation's "_settings.yml": how the architecture parameters are
replaced in the testbench sources, how the run reports its progress, and the
tasks it runs.

Simulations converged with workflows (see /workflow_editor): a simulation runs a
task graph, not a single hard-coded command. A simulation that defines no task
keeps running "make sim" through its Makefile, which is what every simulation
written before tasks existed does -- the Tasks section then starts empty and
says so.

What a simulation does *not* have is its own configurations: it always runs on
the configurations of the architectures it is paired with (chosen on
/run_jobs?type=simulation), so this page has no configuration or variable
section, unlike the Workflow Editor.
"""

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

page_path = "/sim_editor"

dash.register_page(
    __name__,
    path=page_path,
    title="Odatix - Simulation Editor",
    name="Simulation Editor",
    order=7,
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

def get_sim_path(odatix_settings):
    sim_path = (odatix_settings or {}).get("sim_path", "")
    if sim_path:
        return sim_path

    settings_data = OdatixSettings.get_settings_file_dict(silent=True)
    if isinstance(settings_data, dict):
        return settings_data.get("sim_path", OdatixSettings.DEFAULT_SIM_PATH)

    return OdatixSettings.DEFAULT_SIM_PATH

def normalize_simulation_settings(settings):
    """
    Reduce a simulation settings file to the keys this page edits, with stable
    types, so the current state and the saved one can be compared field by field
    (that comparison is what drives the "unsaved changes" state of Save).
    """
    if not isinstance(settings, dict):
        settings = {}

    progress = settings.get("progress", {})
    if not isinstance(progress, dict):
        progress = {}

    tasks = settings.get("tasks", [])
    if not isinstance(tasks, list):
        tasks = []

    return {
        "use_parameters": _parse_bool(settings.get("use_parameters", True), True),
        "param_target_file": str(settings.get("param_target_file", "") or ""),
        "start_delimiter": str(settings.get("start_delimiter", "") or ""),
        "stop_delimiter": str(settings.get("stop_delimiter", "") or ""),
        "override_parameters": _parse_bool(settings.get("override_parameters", False), False),
        "override_param_file": str(settings.get("override_param_file", "") or ""),
        "override_param_target_file": str(settings.get("override_param_target_file", "") or ""),
        "override_start_delimiter": str(settings.get("override_start_delimiter", "") or ""),
        "override_stop_delimiter": str(settings.get("override_stop_delimiter", "") or ""),
        "progress": {
            "file": str(progress.get("file", "") or ""),
            "regex": str(progress.get("regex", "") or ""),
        },
        "tasks": tasks,
    }

def build_tasks_list(names, dependencies_vals, commands_vals, path_vals, platforms_vals):
    """
    Build the simulation task list from the task card field values.

    Unlike a workflow, a simulation may legitimately define no task at all: it
    then falls back to the historical "make sim" command, so an empty list is
    kept empty instead of being seeded with a "main" task.
    """
    tasks = []
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

        task = {"name": name, "commands": commands}
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

    return tasks


######################################
# UI Components
######################################

def simulation_title(sim_name):
    title_buttons = html.Div(
        children=[
            ui.icon_button(
                id="button-open-sim-metric-editor",
                icon=icon("metrics", className="icon blue"),
                text="Edit Metrics",
                tooltip="Open the Exported Metrics Editor for this simulation",
                tooltip_options="bottom delay",
                color="default",
                link=f"/metric_editor?simulation={sim_name}",
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
                                    value=f"{sim_name}",
                                    type="text",
                                    id="sim-title",
                                    placeholder="Simulation Name...",
                                    className="title-input",
                                    style={"width": "100%", "transform": "translate(-5px, 5px)"},
                                )
                            ],
                            id="sim-title-container",
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
                ui.back_button(link="/architectures"),
            ],
            className="tile title",
            style={"position": "relative"},
        ),
        className="card-matrix config",
        style={"marginTop": "0px", "marginBottom": "10px"},
    )

def sim_form_field(label, id, value="", tooltip="", placeholder="", tooltip_options="secondary"):
    return html.Div(
        children=[
            html.Label(label),
            ui.tooltip_icon(tooltip, tooltip_options),
            dcc.Input(id=id, value=value, type="text", placeholder=placeholder, style={"width": "100%"}),
        ],
        style={"marginBottom": "12px"},
    )

def sim_form(settings):
    defval = lambda k, v=None: settings.get(k, v)

    progress = defval("progress", {}) or {}
    use_parameters = True if defval("use_parameters", True) else False
    override_parameters = True if defval("override_parameters", False) else False

    return html.Div(
        children=[
            html.Div(
                [
                    html.H3("Parameters Replacement"),
                    html.Div(
                        children=[
                            dcc.Checklist(
                                options=[{"label": "Enable parameter replacement", "value": True}],
                                value=[True] if use_parameters else [],
                                id="sim-use-parameters",
                                className="checklist-switch",
                                style={"marginBottom": "12px", "marginTop": "5px", "display": "inline-block"},
                            ),
                            ui.tooltip_icon(
                                "Replace values in a testbench file using the configuration files of the "
                                "architecture the simulation runs on."
                            ),
                        ],
                        style={"marginBottom": "12px"},
                    ),
                    html.Div(
                        children=[
                            sim_form_field(
                                label="Parameter Target File",
                                id="sim-param-target-file",
                                value=defval("param_target_file", ""),
                                placeholder="tb/tb_counter.vhdl",
                                tooltip="File of the simulation sources where replacements are applied.",
                            ),
                            sim_form_field(
                                label="Start Delimiter",
                                id="sim-start-delimiter",
                                value=defval("start_delimiter", ""),
                                tooltip="Start marker for replacement.",
                            ),
                            sim_form_field(
                                label="Stop Delimiter",
                                id="sim-stop-delimiter",
                                value=defval("stop_delimiter", ""),
                                tooltip="Stop marker for replacement.",
                            ),
                        ],
                        id="sim-params-config-fields",
                        className="animated-section" if use_parameters else "animated-section hide",
                        style={"overflow": "visible"},
                    ),
                ],
                className="tile config",
            ),
            html.Div(
                [
                    html.H3("Parameters Override"),
                    html.Div(
                        children=[
                            dcc.Checklist(
                                options=[{"label": "Enable parameter override", "value": True}],
                                value=[True] if override_parameters else [],
                                id="sim-override-parameters",
                                className="checklist-switch",
                                style={"marginBottom": "12px", "marginTop": "5px", "display": "inline-block"},
                            ),
                            ui.tooltip_icon(
                                "Apply a second replacement pass, from a file of the simulation itself, on top "
                                "of the architecture configuration (e.g. to force testbench-only parameters)."
                            ),
                        ],
                        style={"marginBottom": "12px"},
                    ),
                    html.Div(
                        children=[
                            sim_form_field(
                                label="Override Parameter File",
                                id="sim-override-param-file",
                                value=defval("override_param_file", ""),
                                tooltip="File of the simulation holding the overriding values.",
                            ),
                            sim_form_field(
                                label="Override Parameter Target File",
                                id="sim-override-param-target-file",
                                value=defval("override_param_target_file", ""),
                                tooltip="File where the overriding values are written.",
                            ),
                            sim_form_field(
                                label="Override Start Delimiter",
                                id="sim-override-start-delimiter",
                                value=defval("override_start_delimiter", ""),
                                tooltip="Start marker for the override replacement.",
                            ),
                            sim_form_field(
                                label="Override Stop Delimiter",
                                id="sim-override-stop-delimiter",
                                value=defval("override_stop_delimiter", ""),
                                tooltip="Stop marker for the override replacement.",
                            ),
                        ],
                        id="sim-override-config-fields",
                        className="animated-section" if override_parameters else "animated-section hide",
                        style={"overflow": "visible"},
                    ),
                ],
                className="tile config",
            ),
            html.Div(
                [
                    html.H3("Progress Tracking"),
                    sim_form_field(
                        label="Progress File",
                        id="sim-progress-file",
                        value=progress.get("file", ""),
                        placeholder=f"{hard_settings.work_log_path}/{hard_settings.sim_progress_filename}",
                        tooltip="Path of the progress file written by the simulation.",
                    ),
                    sim_form_field(
                        label="Progress Regex",
                        id="sim-progress-regex",
                        value=progress.get("regex", ""),
                        placeholder=hard_settings.sim_status_pattern.pattern,
                        tooltip="Regex containing one capture group for the completion percentage.",
                    ),
                ],
                className="tile config",
            ),
        ],
        className="tiles-container config",
        style={"marginTop": "-10px", "marginBottom": "20px"},
    )

def sim_task_card(name="main", dependencies_value="", commands_value="", path_value="", platforms_value=""):
    is_main = str(name).strip() == "main"
    return html.Div([
        html.Div(
            children=[
                dcc.Input(
                    value=name,
                    type="text",
                    id={"type": "sim-task-field-name", "name": name},
                    className="title-input",
                    disabled=is_main,
                    style={
                        "width": "100%",
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
                    id={"type": "sim-task-field-dependencies", "name": name},
                    className="value-input",
                    style={"width": "100%", "marginBottom": "8px"},
                ),
                html.Label("Commands (one per line)", style={"fontWeight": "bold", "fontSize": "1em"}),
                dcc.Textarea(
                    value=commands_value,
                    id={"type": "sim-task-field-commands", "name": name},
                    className="auto-resize-textarea odatix-command-field",
                    style={
                        "width": "100%",
                        "minHeight": "110px",
                        "resize": "vertical",
                        "fontFamily": "monospace",
                        "fontWeight": "500",
                        "marginBottom": "8px",
                        "boxSizing": "border-box",
                    },
                ),
                html.Div(
                    children=[
                        html.Label("Path (optional)", style={"fontWeight": "bold", "fontSize": "1em"}),
                        dcc.Input(
                            value=path_value,
                            type="text",
                            id={"type": "sim-task-field-path", "name": name},
                            className="value-input",
                            style={"width": "100%", "marginBottom": "8px"},
                        ),
                        html.Label("Platforms (optional)", style={"fontWeight": "bold", "fontSize": "1em"}),
                        dcc.Input(
                            value=platforms_value,
                            type="text",
                            placeholder="linux, win32",
                            id={"type": "sim-task-field-platforms", "name": name},
                            className="value-input",
                            style={"width": "100%", "marginBottom": "8px"},
                        ),
                    ],
                    id={"type": "sim-more-task-field-div", "name": name},
                    className="expandable-area",
                    style=Style.hidden,
                ),
            ],
            style={"width": "100%"}
        ),
        html.Div([
            html.Div([
                ui.icon_button(
                    icon=icon("more", className="icon normal rotate", id={"type": "sim-more-task-fields-icon", "name": name}),
                    color="default",
                    id={"type": "sim-more-fields-task", "name": name},
                    tooltip="Show/Hide extra fields",
                    tooltip_options="bottom small",
                )
            ], id={"type": "sim-more-fields-task-div", "name": name}, style={"display": "flex", "alignItems": "center"}),
            html.Div([
                ui.duplicate_button(id={"type": "sim-duplicate-task", "name": name}),
                ui.delete_button(id={"type": "sim-delete-task", "name": name}),
            ], style={"display": "flex", "flexDirection": "horizontal", "alignItems": "center", "gap": "5px"}),
        ], style={
            "marginTop": "8px",
            "display": "flex",
            "flexDirection": "row",
            "width": "100%",
            "justifyContent": "space-between",
        }),
    ],
    className="tile config",
    id={"type": "sim-task-card", "name": name},
)

def sim_add_task_card():
    return html.Div(
        html.Div(
            html.Div(
                children=[
                    html.Div("Add new task", style={"fontWeight": "bold", "fontSize": "1.2em", "paddingTop": "20px"}),
                    html.Div("+", style={"fontSize": "2.5em", "lineHeight": "80px", "height": "80px"}),
                ],
                style={"display": "flex", "flexDirection": "column", "alignItems": "center", "justifyContent": "center", "height": "100%"}
            ),
            id="sim-task-new",
            n_clicks=0,
            style={"textDecoration": "none", "height": "100%"},
        ),
        className="tile config add hover",
        id="sim-task-add-card",
    )

def sim_default_task_note():
    """
    Shown instead of task cards when the simulation defines none: the run then
    falls back to the Makefile's "sim" rule.
    """
    return html.Div(
        [
            html.Div("No task defined", style={"fontWeight": "bold", "marginBottom": "6px"}),
            html.Div(
                'This simulation runs "make sim" from its Makefile, the default since before tasks existed. '
                "Add a task to take over: the Makefile is then no longer required.",
                className="odx-panel-note",
            ),
        ],
        id="sim-default-task-note",
        className="tile config",
    )

def sim_cards_from_tasks(tasks):
    cards = []
    if isinstance(tasks, list):
        for idx, task in enumerate(tasks):
            if not isinstance(task, dict):
                continue
            name = str(task.get("name", "")).strip()
            if name == "":
                name = f"task{idx + 1}"

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
                sim_task_card(
                    name=name,
                    dependencies_value=dependencies_value,
                    commands_value=commands_value,
                    path_value=path_value,
                    platforms_value=platforms_value,
                )
            )

    if not cards:
        cards.append(sim_default_task_note())
    cards.append(sim_add_task_card())
    return cards


######################################
# Callbacks
######################################

@dash.callback(
    Output("sim-task-cards-row", "children", allow_duplicate=True),
    Input("sim-task-new", "n_clicks"),
    Input({"type": "sim-duplicate-task", "name": dash.ALL}, "n_clicks"),
    Input({"type": "sim-delete-task", "name": dash.ALL}, "n_clicks"),
    State("sim-task-cards-row", "children"),
    State({"type": "sim-task-field-name", "name": dash.ALL}, "value"),
    State({"type": "sim-task-field-dependencies", "name": dash.ALL}, "value"),
    State({"type": "sim-task-field-commands", "name": dash.ALL}, "value"),
    State({"type": "sim-task-field-path", "name": dash.ALL}, "value"),
    State({"type": "sim-task-field-platforms", "name": dash.ALL}, "value"),
    prevent_initial_call=True,
)
def update_sim_task_cards(
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

    def card_id_of(card):
        return card.get("props", {}).get("id") if isinstance(card, dict) else None

    # Drop the trailing "Add" card and the "no task" note; both are rebuilt below.
    cards = [
        card for card in cards
        if card_id_of(card) not in ("sim-task-add-card", "sim-default-task-note")
    ]

    if trigger_id == "sim-task-new" and new_click:
        existing_names = [
            cid.get("name", "") for cid in map(card_id_of, cards) if isinstance(cid, dict)
        ]
        # The first task of a simulation is its entry point, and the task graph
        # always starts at "main".
        if not existing_names:
            cards.append(sim_task_card(name="main"))
        else:
            idx = 1
            while f"task{idx}" in existing_names:
                idx += 1
            cards.append(sim_task_card(name=f"task{idx}"))

    if isinstance(trigger_id, dict):
        trig_type = trigger_id.get("type")
        trig_name = trigger_id.get("name")

        idx = None
        for i, card in enumerate(cards):
            cid = card_id_of(card)
            if isinstance(cid, dict) and cid.get("type") == "sim-task-card" and cid.get("name") == trig_name:
                idx = i
                break

        if trig_type == "sim-delete-task" and idx is not None and idx < len(delete_clicks) and delete_clicks[idx]:
            cards = [
                card for card in cards
                if not (
                    isinstance(card_id_of(card), dict)
                    and card_id_of(card).get("type") == "sim-task-card"
                    and card_id_of(card).get("name") == trig_name
                )
            ]
        elif trig_type == "sim-duplicate-task" and idx is not None and idx < len(duplicate_clicks) and duplicate_clicks[idx]:
            existing_names = [
                cid.get("name", "") for cid in map(card_id_of, cards) if isinstance(cid, dict)
            ]
            copy_idx = 1
            while f"{trig_name}_copy{copy_idx}" in existing_names:
                copy_idx += 1

            cards.append(
                sim_task_card(
                    name=f"{trig_name}_copy{copy_idx}",
                    dependencies_value=task_dependencies[idx] if idx < len(task_dependencies) else "",
                    commands_value=task_commands[idx] if idx < len(task_commands) else "",
                    path_value=task_paths[idx] if idx < len(task_paths) else "",
                    platforms_value=task_platforms[idx] if idx < len(task_platforms) else "",
                )
            )

    if not cards:
        cards.append(sim_default_task_note())
    cards.append(sim_add_task_card())
    return cards


@dash.callback(
    Output("sim-form-container", "children"),
    Output("sim-initial-settings", "data"),
    Output("sim-task-cards-row", "children"),
    Input(f"url_{page_path}", "search"),
    State(f"url_{page_path}", "pathname"),
    State("odatix-settings", "data"),
)
def init_form(search, page, odatix_settings):
    if page != page_path:
        return dash.no_update, dash.no_update, dash.no_update

    sim_name = get_key_from_url(search, "sim")
    if not sim_name:
        settings = normalize_simulation_settings({})
        return sim_form(settings), settings, sim_cards_from_tasks([])

    sim_path = get_sim_path(odatix_settings)
    settings = normalize_simulation_settings(workspace.load_simulation_settings(sim_path, sim_name))
    return sim_form(settings), settings, sim_cards_from_tasks(settings.get("tasks", []))


@dash.callback(
    Output({"page": page_path, "action": "save-all"}, "className"),
    Output({"page": page_path, "action": "save-all"}, "data-tooltip"),
    Output(f"url_{page_path}", "search"),
    Output("sim-saved-settings", "data"),
    Input({"page": page_path, "action": "save-all"}, "n_clicks"),
    Input("sim-title", "value"),
    Input("sim-use-parameters", "value"),
    Input("sim-param-target-file", "value"),
    Input("sim-start-delimiter", "value"),
    Input("sim-stop-delimiter", "value"),
    Input("sim-override-parameters", "value"),
    Input("sim-override-param-file", "value"),
    Input("sim-override-param-target-file", "value"),
    Input("sim-override-start-delimiter", "value"),
    Input("sim-override-stop-delimiter", "value"),
    Input("sim-progress-file", "value"),
    Input("sim-progress-regex", "value"),
    Input({"type": "sim-task-field-name", "name": dash.ALL}, "value"),
    Input({"type": "sim-task-field-dependencies", "name": dash.ALL}, "value"),
    Input({"type": "sim-task-field-commands", "name": dash.ALL}, "value"),
    Input({"type": "sim-task-field-path", "name": dash.ALL}, "value"),
    Input({"type": "sim-task-field-platforms", "name": dash.ALL}, "value"),
    State(f"url_{page_path}", "search"),
    State(f"url_{page_path}", "pathname"),
    State("sim-initial-settings", "data"),
    State("sim-saved-settings", "data"),
    State("odatix-settings", "data"),
    prevent_initial_call=True,
)
def save_and_status(
    n_clicks,
    sim_title_value,
    use_parameters,
    param_target_file,
    start_delimiter,
    stop_delimiter,
    override_parameters,
    override_param_file,
    override_param_target_file,
    override_start_delimiter,
    override_stop_delimiter,
    progress_file,
    progress_regex,
    task_names,
    task_dependencies,
    task_commands,
    task_paths,
    task_platforms,
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
        reference_settings = normalize_simulation_settings(initial_settings)
    else:
        reference_settings = normalize_simulation_settings(saved_settings)

    current_settings = normalize_simulation_settings(
        {
            "use_parameters": True if use_parameters else False,
            "param_target_file": param_target_file or "",
            "start_delimiter": start_delimiter or "",
            "stop_delimiter": stop_delimiter or "",
            "override_parameters": True if override_parameters else False,
            "override_param_file": override_param_file or "",
            "override_param_target_file": override_param_target_file or "",
            "override_start_delimiter": override_start_delimiter or "",
            "override_stop_delimiter": override_stop_delimiter or "",
            "progress": {
                "file": progress_file or "",
                "regex": progress_regex or "",
            },
            "tasks": build_tasks_list(
                task_names, task_dependencies, task_commands, task_paths, task_platforms
            ),
        }
    )

    sim_name = get_key_from_url(search, "sim")
    sim_path = get_sim_path(odatix_settings)

    if not sim_title_value:
        return (
            "color-button error-status icon-button tooltip bottom",
            "Simulation name cannot be empty",
            dash.no_update,
            saved_settings,
        )

    for character in hard_settings.invalid_filename_characters:
        if character in sim_title_value:
            label = "' ' (space)" if character == " " else f"'{character}'"
            return (
                "color-button error-status icon-button tooltip bottom",
                f"Unauthorized character in simulation name: {label}",
                dash.no_update,
                saved_settings,
            )

    if triggered_id == {"page": page_path, "action": "save-all"}:
        new_search = dash.no_update

        if sim_name and sim_title_value != sim_name:
            if workspace.simulation_exists(sim_path, sim_title_value):
                return (
                    "color-button error-status icon-button tooltip bottom",
                    f"'{sim_title_value}' already exists",
                    dash.no_update,
                    saved_settings,
                )
            if workspace.simulation_exists(sim_path, sim_name):
                workspace.rename_simulation(sim_path, sim_name, sim_title_value)
            sim_name = sim_title_value
            new_search = f"?sim={sim_name}"
        elif not sim_name:
            sim_name = sim_title_value
            new_search = f"?sim={sim_name}"

        if not workspace.simulation_exists(sim_path, sim_name):
            workspace.create_simulation(sim_path, sim_name)

        try:
            workspace.save_simulation_settings(sim_path, sim_name, current_settings)
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

    if current_settings != reference_settings or sim_title_value != (sim_name or ""):
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
    Output("sim-params-config-fields", "className"),
    Input("sim-use-parameters", "value"),
)
def toggle_parameter_fields(use_parameters):
    return "animated-section" if use_parameters else "animated-section hide"


@dash.callback(
    Output("sim-override-config-fields", "className"),
    Input("sim-override-parameters", "value"),
)
def toggle_override_fields(override_parameters):
    return "animated-section" if override_parameters else "animated-section hide"


@dash.callback(
    Output({"page": page_path, "type": "sim-title-div"}, "children"),
    Input(f"url_{page_path}", "search"),
)
def update_sim_title(search):
    return simulation_title(get_key_from_url(search, "sim") or "")


@dash.callback(
    Output({"type": "sim-more-task-field-div", "name": dash.ALL}, "style"),
    Output({"type": "sim-more-task-fields-icon", "name": dash.ALL}, "className"),
    Input({"type": "sim-more-fields-task", "name": dash.ALL}, "n_clicks"),
    State({"type": "sim-more-task-field-div", "name": dash.ALL}, "style"),
    State({"type": "sim-more-task-fields-icon", "name": dash.ALL}, "className"),
    State({"type": "sim-task-field-name", "name": dash.ALL}, "value"),
)
def toggle_sim_task_more_fields(n_clicks, expandable_area_styles, icon_classes, task_names):
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


######################################
# Layout
######################################

layout = html.Div(
    children=[
        dcc.Location(id=f"url_{page_path}"),
        html.Div(id={"page": page_path, "type": "sim-title-div"}, style={"marginTop": "20px"}),
        html.Div(id="sim-form-container"),
        html.Div(
            children=[
                ui.title_tile(
                    text="Task Definition",
                    id="sim-task-title",
                    tooltip=(
                        "Tasks define the steps of the simulation. Without any task, the simulation runs "
                        '"make sim" from its Makefile. Commands can use ${architecture}, ${configuration}, '
                        "${top_level_module}, ${clock_signal}, ${rtl_dir} and one placeholder per parameter domain."
                    ),
                ),
                html.Div([
                    html.Div(
                        id="sim-task-cards-row",
                        children=[sim_add_task_card()],
                        className="tiles-container config",
                        style={
                            "display": "flex",
                            "justifyContent": "flex-start",
                            "alignItems": "flex-start",
                            "flexWrap": "wrap",
                            "marginBottom": "30px",
                            "columnGap": "var(--tile-gap)",
                        },
                    ),
                ]),
            ],
        ),
        dcc.Store(id="sim-initial-settings", data=None),
        dcc.Store(id="sim-saved-settings", data=None),
    ],
    className="page-content",
    style={
        "display": "flex",
        "flexDirection": "column",
        "min-height": f"calc(100vh - {navigation.top_bar_height})",
    },
)
