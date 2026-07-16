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

import uuid
import dash
from dash import html, dcc, Input, Output, ctx, State

import odatix.gui.ui_components as ui
from odatix.gui.icons import icon
import odatix.gui.navigation as navigation
import odatix.components.workspace as workspace
from odatix.lib.settings import OdatixSettings

page_path = "/workflows"

dash.register_page(
    __name__,
    path=page_path,
    title="Odatix - Workflows",
    name="Workflows",
    order=4,
)


######################################
# Helpers
######################################

def get_workflow_path(odatix_settings):
    workflow_path = odatix_settings.get("workflow_path", "")
    if workflow_path:
        return workflow_path

    settings_data = OdatixSettings.get_settings_file_dict(silent=True)
    if isinstance(settings_data, dict):
        return settings_data.get("workflow_path", OdatixSettings.DEFAULT_WORKFLOW_PATH)

    return OdatixSettings.DEFAULT_WORKFLOW_PATH

def build_workflow_cards(workflow_path):
    workflows = workspace.get_workflows(workflow_path)
    workflow_cards = [normal_card(name) for name in workflows]
    workflow_cards.append(add_card("Create New Workflow"))
    return workflow_cards


######################################
# UI Components
######################################

def normal_card(name):
    unique_key = str(uuid.uuid4())
    return html.Div(
        [
            html.Div(name, title=name, style={"fontWeight": "bold", "fontSize": "1.05em", "textAlign": "center", "textOverflow": "ellipsis", "overflow": "hidden", "whiteSpace": "nowrap"}),
            html.Div(
                [
                    html.Div(
                        [
                            ui.icon_button(
                                id=f"button-edit-workflow-{name}",
                                icon=icon("gear", className="icon black"),
                                text="Settings",
                                color="default",
                                link=f"/workflow_editor?workflow={name}",
                                width="auto",
                            ),
                            ui.icon_button(
                                id=f"button-open-workflow-{name}",
                                icon=icon("edit", className="icon black"),
                                text="Edit Configs",
                                color="default",
                                link=f"/config_editor?workflow={name}",
                                width="auto",
                            ),
                        ],
                        style={"display": "flex", "gap": "4px"},
                    ),
                    html.Div(
                        [
                            ui.duplicate_button(id={"type": "workflow-button-duplicate", "name": name}),
                            ui.delete_button(id={"type": "workflow-button-delete", "name": name}),
                        ],
                        style={"display": "flex", "alignItems": "center", "gap": "4px"},
                    ),
                ],
                style={
                    "marginTop": "14px",
                    "display": "flex",
                    "flexDirection": "row",
                    "width": "100%",
                    "alignItems": "center",
                    "gap": "4px",
                    "justifyContent": "space-between",
                },
            ),
        ],
        className="card",
        style={
            "padding": "18px 20px",
            "margin": "0",
            "width": "100%",
            "boxSizing": "border-box",
        },
        key=unique_key,
    )

def add_card(text: str):
    btn_id = {"type": "workflow-button-add"}
    return html.Div(
        html.Div(
            html.Div(
                children=[
                    html.Div(text, style={"fontWeight": "bold", "fontSize": "1.05em", "color": "var(--add-card-text-color)"}),
                    html.Div(
                        "+",
                        style={
                            "fontSize": "2em",
                            "lineHeight": "1",
                            "marginTop": "8px",
                        },
                    ),
                ],
                style={"textAlign": "center"},
            ),
            id=btn_id,
            n_clicks=0,
            style={"textDecoration": "none", "color": "var(--add-card-text-color)", "display": "flex", "flexDirection": "column", "alignItems": "center", "justifyContent": "center", "height": "100%"},
        ),
        className="card add hover",
        style={
            "padding": "18px 20px",
            "margin": "0",
            "width": "100%",
            "boxSizing": "border-box",
        },
    )


######################################
# Callbacks
######################################

@dash.callback(
    Output("workflow-cards-matrix", "children"),
    Input("workflow-cards-matrix", "children"),
    State("odatix-settings", "data"),
)
def update_cards(_, odatix_settings):
    workflow_path = get_workflow_path(odatix_settings)
    return build_workflow_cards(workflow_path)

@dash.callback(
    Output("workflow-cards-matrix", "children", allow_duplicate=True),
    Input({"type": "workflow-button-duplicate", "name": dash.ALL}, "n_clicks_timestamp"),
    State({"type": "workflow-button-duplicate", "name": dash.ALL}, "id"),
    State("odatix-settings", "data"),
    prevent_initial_call=True,
)
def direct_duplicate(dupl_timestamps, btn_ids, odatix_settings):
    triggered = ctx.triggered_id
    if not triggered or not isinstance(triggered, dict):
        return dash.no_update

    if not dupl_timestamps or not btn_ids:
        return dash.no_update

    idx = max(range(len(dupl_timestamps)), key=lambda i: dupl_timestamps[i] or 0)
    btn_id = btn_ids[idx]
    if btn_id != triggered or not dupl_timestamps[idx]:
        return dash.no_update

    workflow_path = get_workflow_path(odatix_settings)
    name = btn_id["name"]

    base = name
    suffix = 1
    while True:
        new_name = f"{base}_copy{suffix}"
        if not workspace.workflow_exists(workflow_path, new_name):
            break
        suffix += 1
        if suffix > 1000:
            return dash.no_update

    try:
        workspace.duplicate_workflow(workflow_path, name, new_name)
    except Exception:
        return dash.no_update

    return build_workflow_cards(workflow_path)

@dash.callback(
    Output("workflow-delete-popup", "className"),
    Output("workflow-delete-popup-message", "children"),
    Output("workflow-delete-info", "data"),
    Input({"type": "workflow-button-delete", "name": dash.ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def show_delete_popup(n_clicks):
    if not ctx.triggered_id or not isinstance(ctx.triggered_id, dict) or all(n == 0 for n in n_clicks):
        return dash.no_update, dash.no_update, dash.no_update

    name = ctx.triggered_id["name"]
    msg = f"Do you really want to delete workflow '{name}'?"
    return "overlay-odatix visible", msg, {"name": name}

@dash.callback(
    Output("workflow-delete-popup", "className", allow_duplicate=True),
    Input("workflow-delete-cancel-btn", "n_clicks"),
    prevent_initial_call=True,
)
def close_delete_popup(_):
    return "overlay-odatix"

@dash.callback(
    Output("workflow-delete-popup", "className", allow_duplicate=True),
    Output("workflow-delete-error", "children"),
    Output("workflow-cards-matrix", "children", allow_duplicate=True),
    Input("workflow-delete-confirm-btn", "n_clicks"),
    State("workflow-delete-info", "data"),
    State("odatix-settings", "data"),
    prevent_initial_call=True,
)
def do_delete(n_clicks, info, odatix_settings):
    if not n_clicks or not info:
        return dash.no_update, dash.no_update, dash.no_update

    workflow_path = get_workflow_path(odatix_settings)
    name = info["name"]
    if not workspace.workflow_exists(workflow_path, name):
        return dash.no_update, "Workflow not found.", dash.no_update

    try:
        workspace.delete_workflow(workflow_path, name)
    except Exception as e:
        return dash.no_update, f"Error: {e}", dash.no_update

    return "overlay-odatix", "", build_workflow_cards(workflow_path)

@dash.callback(
    Output({"type": "update_url", "id": page_path}, "data"),
    Input({"type": "workflow-button-add"}, "n_clicks_timestamp"),
    State("odatix-settings", "data"),
    prevent_initial_call=True,
)
def handle_add_card(n_click_timestamp, odatix_settings):
    if not n_click_timestamp:
        return dash.no_update

    workflow_path = get_workflow_path(odatix_settings)
    base_name = "New_Workflow"

    for i in range(1, 1001):
        candidate = f"{base_name}{i}"
        if not workspace.workflow_exists(workflow_path, candidate):
            return {"href": f"/workflow_editor?workflow={candidate}", "id": page_path}

    return {"href": "/workflow_editor", "id": page_path}


######################################
# Layout
######################################

layout = html.Div(
    children=[
        dcc.Location(id="url", refresh="callback-nav"),
        html.Div(
            children=[
                ui.page_header("Workflows", "Configure your workflows and their configurations."),
                html.Div(id="workflow-cards-matrix", className="card-matrix configs", style={"gap": "var(--tile-gap)"}),
            ],
            style={
                "display": "block",
                "width": "auto",
                "textAlign": "center",
                "marginBottom": "10px",
            },
        ),
        dcc.Store(id="workflow-delete-info"),
        html.Div(
            id="workflow-delete-popup",
            className="overlay-odatix",
            children=[
                html.Div(
                    [
                        html.H2("Warning"),
                        html.Div(id="workflow-delete-popup-message"),
                        html.Div("This action is irreversible.", style={"marginTop": "10px", "color": "#FA5252", "fontWeight": "bold"}),
                        html.Div(
                            [
                                ui.icon_button(
                                    icon=icon("delete", className="icon"),
                                    color="caution",
                                    text="Delete",
                                    width="90px",
                                    id="workflow-delete-confirm-btn",
                                ),
                                html.Button("Cancel", id="workflow-delete-cancel-btn", n_clicks=0, style={"marginLeft": "10px", "width": "90px"}),
                            ],
                            style={"marginTop": "18px", "display": "flex", "justifyContent": "center"},
                        ),
                        html.Div(id="workflow-delete-error", style={"color": "red", "marginTop": "10px"}),
                    ],
                    className="popup-odatix",
                )
            ],
        ),
        dcc.Store(id={"type": "update_url", "id": page_path}),
    ],
    className="page-content",
    style={
        "padding": "0 32px 24px",
        "display": "flex",
        "flexDirection": "column",
        "min-height": f"calc(100vh - {navigation.top_bar_height})",
    },
)