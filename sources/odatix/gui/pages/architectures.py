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
from dash import html, dcc, Input, Output, ctx, State
import odatix.gui.ui_components as ui
import shutil
import uuid

import odatix.gui.ui_components as ui
from odatix.gui.icons import icon

dash.register_page(
    __name__,
    path='/architectures',
    title='Odatix - Architectures',
    name='Architectures',
    order=2,
)

ARCH_ROOT = "odatix_userconfig/architectures"
SIM_ROOT = "odatix_userconfig/simulations"

def get_architectures():
    if not os.path.exists(ARCH_ROOT):
        return []
    return sorted([
        d for d in os.listdir(ARCH_ROOT)
        if os.path.isdir(os.path.join(ARCH_ROOT, d))
    ])

def get_simulations():
    if not os.path.exists(SIM_ROOT):
        return []
    return sorted([
        d for d in os.listdir(SIM_ROOT)
        if os.path.isdir(os.path.join(SIM_ROOT, d))
    ])

def normal_card(name, card_type: str = "arch"):
    unique_key = str(uuid.uuid4())
    return html.Div(
        [
            html.Div(name, style={"fontWeight": "bold", "fontSize": "1.2em", "textAlign": "center"}),
            html.Div([
                html.Div([
                    ui.icon_button(
                        id=f"button-edit-{card_type}-{name}",
                        icon=icon("edit", className="icon black"),
                        text="Edit",
                        color="transparent",
                        link=f"/{card_type}_editor?{card_type}={name}",
                        width="80px",
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
                    html.Div(text, style={"fontWeight": "bold", "fontSize": "1.2em", "color": "black"}),
                    html.Div(
                        "+",
                        style={
                            "fontSize": "2.5em",
                            "color": "#888",
                            "lineHeight": "80px",
                            "height": "80px",
                        }
                    ),
                ], 
                style={"textAlign": "center"}
            ),
            href=f"/{card_type}_editor",
            style={"text-decoration": "none", "color": "black"},
        ),
        className="card hover",
        style={
            "backgroundColor": "rgba(255, 255, 255, 0.31)",
            "border": "1px dashed #bbb",
            "padding": "18px",
            "margin": "10px",
            "width": "300px",
            "height": "100px",
        },
    )

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
                    html.H3("Warning"),
                    html.Button("×", id="delete-cancel-btn", n_clicks=0, className="close"),
                    html.Div(id="delete-popup-message"),
                    html.Div("This action is irreversible.", style={"marginTop": "10px", "color": "#b00"}),
                    html.Div([
                        html.Button("Delete", id="delete-confirm-btn", n_clicks=0, style={"marginRight": "10px", "background": "#FA5252", "color": "white"}),
                    ], style={"marginTop": "18px"}),
                    html.Div(id="delete-error", style={"color": "red", "marginTop": "10px"}),
                ], className="popup-odatix")
            ]
        ),
    ],
    style={
        "background-color": "#f6f8fa",
        "padding": "20px 16%",
        "minHeight": "100vh",
        "display": "block",
    },
)

# Update cards on page load
@dash.callback(
    Output("arch-cards-matrix", "children"),
    Output("sim-cards-matrix", "children"),
    Input("arch-cards-matrix", "children"),
)
def update_cards(_):
    architectures = get_architectures()
    simulations = get_simulations()
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
    prevent_initial_call=True
)
def direct_duplicate(dupl_timestamps, btn_ids):
    triggered = ctx.triggered_id
    if not triggered or not isinstance(triggered, dict):
        raise dash.exceptions.PreventUpdate

    if not dupl_timestamps or not btn_ids:
        raise dash.exceptions.PreventUpdate
    idx = max(range(len(dupl_timestamps)), key=lambda i: dupl_timestamps[i] or 0)
    btn_id = btn_ids[idx]

    if btn_id != triggered or not dupl_timestamps[idx]:
        raise dash.exceptions.PreventUpdate

    card_type = btn_id["card_type"]
    name = btn_id["name"]

    base = name
    suffix = 1
    while True:
        new_name = f"{base}_copy{suffix}"
        root = ARCH_ROOT if card_type == "arch" else SIM_ROOT
        dst = os.path.join(root, new_name)
        if not os.path.exists(dst):
            break
        suffix += 1
        if suffix > 1000:
            raise dash.exceptions.PreventUpdate

    src = os.path.join(ARCH_ROOT if card_type == "arch" else SIM_ROOT, name)
    try:
        shutil.copytree(src, dst)
    except Exception:
        raise dash.exceptions.PreventUpdate

    # Refresh the cards
    architectures = get_architectures()
    simulations = get_simulations()
    arch_cards = [normal_card(n, "arch") for n in architectures]
    arch_cards.append(add_card("Create New Architecture", "arch"))
    sim_cards = [normal_card(n, "sim") for n in simulations]
    sim_cards.append(add_card("Create New Simulation", "sim"))
    return arch_cards, sim_cards

# Duplicate
@dash.callback(
    Output("duplicate-popup", "style", allow_duplicate=True),
    Output("duplicate-error", "children"),
    Output("arch-cards-matrix", "children", allow_duplicate=True),
    Output("sim-cards-matrix", "children", allow_duplicate=True),
    Input("duplicate-create-btn", "n_clicks"),
    State("duplicate-new-name", "value"),
    State("duplicate-info", "data"),
    prevent_initial_call=True
)
def do_duplicate(n_clicks, new_name, info):
    if not n_clicks or not info:
        raise dash.exceptions.PreventUpdate
    card_type = info["card_type"]
    old_name = info["name"]
    if not new_name or "/" in new_name or "\\" in new_name:
        return {"display": "flex"}, "Invalid name.", dash.no_update, dash.no_update
    src = os.path.join(ARCH_ROOT if card_type == "arch" else SIM_ROOT, old_name)
    dst = os.path.join(ARCH_ROOT if card_type == "arch" else SIM_ROOT, new_name)
    if os.path.exists(dst):
        return {"display": "flex"}, "A folder with this name already exists.", dash.no_update, dash.no_update
    try:
        shutil.copytree(src, dst)
    except Exception as e:
        return {"display": "flex"}, f"Error: {e}", dash.no_update, dash.no_update

    # Refresh the cards
    architectures = get_architectures()
    simulations = get_simulations()
    arch_cards = [normal_card(name, "arch") for name in architectures]
    arch_cards.append(add_card("Create New Architecture", "arch"))
    sim_cards = [normal_card(name, "sim") for name in simulations]
    sim_cards.append(add_card("Create New Simulation", "sim"))
    return {"display": "none"}, "", arch_cards, sim_cards

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
    prevent_initial_call=True
)
def do_delete(n_clicks, info):
    if not n_clicks or not info:
        raise dash.exceptions.PreventUpdate
    card_type = info["card_type"]
    name = info["name"]
    path = os.path.join(ARCH_ROOT if card_type == "arch" else SIM_ROOT, name)
    if not os.path.exists(path):
        return dash.no_update, "Item not found.", dash.no_update, dash.no_update
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
    except Exception as e:
        print("Error during deletion:", e)
        return dash.no_update, f"Error: {e}", dash.no_update, dash.no_update

    # Refresh the cards
    architectures = get_architectures()
    simulations = get_simulations()
    arch_cards = [normal_card(name, "arch") for name in architectures]
    arch_cards.append(add_card("Create New Architecture", "arch"))
    sim_cards = [normal_card(name, "sim") for name in simulations]
    sim_cards.append(add_card("Create New Simulation", "sim"))
    return "overlay-odatix", "", arch_cards, sim_cards
