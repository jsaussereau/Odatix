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

import os
import dash
import shutil
import uuid
from dash import html, dcc, Input, Output, ctx, State

import odatix.gui.ui_components as ui
from odatix.gui.icons import icon
import odatix.gui.navigation as navigation
import odatix.components.workspace as workspace
import odatix.lib.hard_settings as hard_settings
from odatix.lib.settings import OdatixSettings

page_path = "/architectures"

dash.register_page(
    __name__,
    path=page_path,
    title='Odatix - Architectures',
    name='Architectures',
    order=2,
)


######################################
# UI Components
######################################

def normal_card(name, card_type: str = "arch"):
    unique_key = str(uuid.uuid4())
    return html.Div(
        [
            html.Div(name, style={"fontWeight": "bold", "fontSize": "1.2em", "textAlign": "center"}),
            html.Div([
                html.Div([
                    ui.icon_button(
                        id=f"button-edit-{card_type}-{name}",
                        icon=icon("gear", className="icon black"),
                        text="Settings",
                        color="transparent",
                        link=f"/{card_type}_editor?{card_type}={name}",
                        width="100px",
                    ),
                    ui.icon_button(
                        id=f"button-open-{card_type}-{name}",
                        icon=icon("edit", className="icon black"),
                        text="Edit Configs",
                        color="transparent",
                        link=f"/config_editor?{card_type}={name}",
                        multiline=True,
                        width="100px",
                    ),
                ], style={"display": "flex"}),
                html.Div([
                    ui.duplicate_button(id={"type": "button-duplicate", "card_type": card_type, "name": name}),
                    ui.delete_button(id={"type": "button-delete", "card_type": card_type, "name": name}),
                ], style={"display": "flex", "alignItems": "center"}),
            ], style={
                "marginTop": "8px",
                "display": "flex",
                "flexDirection": "row",
                "width": "100%",
                "justifyContent": "space-between",
            }),
        ],
        className="card",
        style={
            "padding": "18px",
            "margin": "10px",
            "width": "300px",
            "height": "100px",
        },
        key=unique_key
    )

def add_card(text: str, card_type: str = "arch"):
    return html.Div(
        dcc.Link(
            html.Div(
                children=[
                    html.Div(text, style={"fontWeight": "bold", "fontSize": "1.2em", "color": "var(--add-card-text-color)"}),
                    html.Div(
                        "+",
                        style={
                            "fontSize": "2.5em",
                            "lineHeight": "80px",
                            "height": "80px",
                        }
                    ),
                ], 
                style={"textAlign": "center"}
            ),
            href=f"/{card_type}_editor",
            style={"text-decoration": "none", "color": "var(--add-card-text-color)"},
        ),
        className="card add hover",
        style={
            "padding": "18px",
            "margin": "10px",
            "width": "300px",
            "height": "100px",
        },
    )


######################################
# Callbacks
######################################

# Update cards on page load
@dash.callback(
    Output("arch-cards-matrix", "children"),
    Output("sim-cards-matrix", "children"),
    Input("arch-cards-matrix", "children"),
    State("odatix-settings", "data"),
)
def update_cards(_, odatix_settings):
    arch_path = odatix_settings.get("arch_path", OdatixSettings.DEFAULT_ARCH_PATH)
    sim_path = odatix_settings.get("sim_path", OdatixSettings.DEFAULT_SIM_PATH)

    architectures = workspace.get_architectures(arch_path)
    simulations = workspace.get_simulations(sim_path)

    arch_cards = [normal_card(name, "arch") for name in architectures]
    arch_cards.append(add_card("Create New Architecture", "arch"))
    sim_cards = [normal_card(name, "sim") for name in simulations]
    sim_cards.append(add_card("Create New Simulation", "sim"))
    return arch_cards, sim_cards

@dash.callback(
    Output("arch-cards-matrix", "children", allow_duplicate=True),
    Output("sim-cards-matrix", "children", allow_duplicate=True),
    Input({"type": "button-duplicate", "card_type": dash.ALL, "name": dash.ALL}, "n_clicks_timestamp"),
    State({"type": "button-duplicate", "card_type": dash.ALL, "name": dash.ALL}, "id"),
    State("odatix-settings", "data"),
    prevent_initial_call=True
)
def direct_duplicate(dupl_timestamps, btn_ids, odatix_settings):
    triggered = ctx.triggered_id
    if not triggered or not isinstance(triggered, dict):
        return dash.no_update, dash.no_update

    if not dupl_timestamps or not btn_ids:
        return dash.no_update, dash.no_update
    
    arch_path = odatix_settings.get("arch_path", OdatixSettings.DEFAULT_ARCH_PATH)
    sim_path = odatix_settings.get("sim_path", OdatixSettings.DEFAULT_SIM_PATH)

    idx = max(range(len(dupl_timestamps)), key=lambda i: dupl_timestamps[i] or 0)
    btn_id = btn_ids[idx]

    if btn_id != triggered or not dupl_timestamps[idx]:
        return dash.no_update, dash.no_update

    card_type = btn_id["card_type"]
    name = btn_id["name"]

    path = arch_path if card_type == "arch" else sim_path

    base = name
    suffix = 1
    while True:
        new_name = f"{base}_copy{suffix}"
        if not workspace.instance_exists(path, new_name):
            break
        suffix += 1
        if suffix > 1000:
            return dash.no_update, dash.no_update

    try:
        workspace.duplicate_instance(path, name, new_name)
    except Exception:
        return dash.no_update, dash.no_update

    # Refresh the cards
    architectures = workspace.get_architectures(arch_path)
    simulations = workspace.get_simulations(sim_path)
    arch_cards = [normal_card(n, "arch") for n in architectures]
    arch_cards.append(add_card("Create New Architecture", "arch"))
    sim_cards = [normal_card(n, "sim") for n in simulations]
    sim_cards.append(add_card("Create New Simulation", "sim"))
    return arch_cards, sim_cards

# Open deletion popup
@dash.callback(
    Output("delete-popup", "className"),
    Output("delete-popup-message", "children"),
    Output("delete-info", "data"),
    Input({"type": "button-delete", "card_type": dash.ALL, "name": dash.ALL}, "n_clicks"),
    State({"type": "button-delete", "card_type": dash.ALL, "name": dash.ALL}, "id"),
    prevent_initial_call=True
)
def show_delete_popup(n_clicks, btn_ids):
    if not ctx.triggered_id or not isinstance(ctx.triggered_id, dict) or all(n == 0 for n in n_clicks):
        return dash.no_update, dash.no_update, dash.no_update
    
    card_type = ctx.triggered_id["card_type"]
    name = ctx.triggered_id["name"]
    msg = f"Do you really want to delete {card_type} '{name}'?"
    return "overlay-odatix visible", msg, {"card_type": card_type, "name": name}

# Popup close
@dash.callback(
    Output("delete-popup", "className", allow_duplicate=True),
    Input("delete-cancel-btn", "n_clicks"),
    prevent_initial_call=True
)
def close_delete_popup(n):
    return "overlay-odatix"

# Delete
@dash.callback(
    Output("delete-popup", "className", allow_duplicate=True),
    Output("delete-error", "children"),
    Output("arch-cards-matrix", "children", allow_duplicate=True),
    Output("sim-cards-matrix", "children", allow_duplicate=True),
    Input("delete-confirm-btn", "n_clicks"),
    State("delete-info", "data"),
    State("odatix-settings", "data"),
    prevent_initial_call=True
)
def do_delete(n_clicks, info, odatix_settings):
    if not n_clicks or not info:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    arch_path = odatix_settings.get("arch_path", OdatixSettings.DEFAULT_ARCH_PATH)
    sim_path = odatix_settings.get("sim_path", OdatixSettings.DEFAULT_SIM_PATH)
    
    card_type = info["card_type"]
    name = info["name"]
    path = arch_path if card_type == "arch" else sim_path
    if not workspace.instance_exists(path, name):
        return dash.no_update, "Item not found.", dash.no_update, dash.no_update
    try:
        workspace.delete_instance(path, name)
    except Exception as e:
        print("Error during deletion:", e)
        return dash.no_update, f"Error: {e}", dash.no_update, dash.no_update

    # Refresh the cards
    architectures = workspace.get_architectures(arch_path)
    simulations = workspace.get_simulations(sim_path)
    arch_cards = [normal_card(name, "arch") for name in architectures]
    arch_cards.append(add_card("Create New Architecture", "arch"))
    sim_cards = [normal_card(name, "sim") for name in simulations]
    sim_cards.append(add_card("Create New Simulation", "sim"))
    return "overlay-odatix", "", arch_cards, sim_cards


######################################
# Layout
######################################

layout = html.Div(
    children=[
        html.Div(
            children=[
                html.H2("Architectures", style={"textAlign": "center"}),
                html.Div(id="arch-cards-matrix", className="card-matrix"),
                html.H2("Simulations", style={"textAlign": "center", "marginTop": "40px"}),
                html.Div(id="sim-cards-matrix", className="card-matrix"),
            ],
            style={
                "display": "block",
                "width": "auto",
                "textAlign": "center",
                "marginBottom": "10px",
            },
        ),
        dcc.Store(id="duplicate-info"),
        html.Div(
            id="duplicate-popup",
            className="overlay-odatix",
            children=[
                html.Div([
                    html.H3("Duplicate"),
                    html.Button("×", id="duplicate-cancel-btn", n_clicks=0, className="close"),
                    html.Div(id="duplicate-popup-message"),
                    dcc.Input(id="duplicate-new-name", placeholder="New name", type="text", style={"width": "90%", "marginTop": "10px"}),
                    html.Div([
                        html.Button("Create", id="duplicate-create-btn", n_clicks=0, style={"marginRight": "10px"}),
                    ], style={"marginTop": "18px"}),
                    html.Div(id="duplicate-error", style={"color": "red", "marginTop": "10px"}),
                ], className="popup-odatix")
            ]
        ),
        dcc.Store(id="delete-info"),
        html.Div(
            id="delete-popup",
            className="overlay-odatix",
            children=[
                html.Div([
                    html.H2("Warning"),
                    html.Div(id="delete-popup-message"),
                    html.Div("This action is irreversible.", style={"marginTop": "10px", "color": "#FA5252", "fontWeight": "bold"}),
                    html.Div([
                        ui.icon_button(
                            icon=icon("delete", className="icon red"),
                            color="red", 
                            text="Delete", 
                            width="90px",
                            id="delete-confirm-btn",
                        ),
                        html.Button("Cancel", id="delete-cancel-btn", n_clicks=0, style={"marginLeft": "10px", "width": "90px"}),
                    ], style={"marginTop": "18px", "display": "flex", "justifyContent": "center"}),
                    html.Div(id="delete-error", style={"color": "red", "marginTop": "10px"}),
                ], className="popup-odatix")
            ]
        ),
    ],
    className="page-content",
    style={
        "padding": "0 16%",
        "display": "flex",  
        "flexDirection": "column",
        "min-height": f"calc(100vh - {navigation.top_bar_height})",
    },
)
