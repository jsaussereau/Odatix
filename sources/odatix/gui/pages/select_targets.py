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

import dash
from dash import html, dcc, Input, Output, State, ctx, ALL, MATCH

import odatix.components.workspace as workspace
from odatix.gui.icons import icon
from odatix.gui.utils import get_key_from_url
import odatix.gui.ui_components as ui
from odatix.gui.css_helper import Style
import odatix.gui.navigation as navigation
from odatix.lib.settings import OdatixSettings

page_path = "/select_targets"

dash.register_page(
    __name__,
    path=page_path,
    title='Odatix - Target Selection',
    name='Select Targets',
    order=3,
)

tool_display_names = {
    "vivado": "Vivado",
    "design_compiler": "Design Compiler",
    "genus": "Genus",
    "openlane": "OpenLane",
}

save_button_disabled = "color-button disabled icon-button"
save_button_enabled = "color-button warning icon-button tooltip delay bottom auto caution"


def get_tool_display_name(tool):
    if not tool:
        return ""
    return tool_display_names.get(tool, tool.replace("_", " ").title())


######################################
# UI Components
######################################

def target_card(target):
    name = target["name"]
    enabled = target.get("enabled", True)
    extra_fields_open = bool(target.get("script_copy_enable", False)) or str(target.get("script_copy_source", "")).strip() != ""

    return html.Div([
        html.Div([
            dcc.Input(
                value=name,
                type="text",
                id={"type": "target-title", "name": name},
                className="title-input",
                style={
                    "width": "calc(100% - var(--tile-gap))",
                    "marginLeft": "5px",
                    "marginRight": "5px",
                    "fontWeight": "bold",
                    "fontSize": "1.1em",
                    "marginTop": "-5px",
                    "marginBottom": "2px",
                    "textAlign": "center",
                },
            )
        ]),
        dcc.Store(id={"type": "target-metadata", "name": name}, data=target),
        html.Div([
            html.Div([
                dcc.Checklist(
                    options=[{"label": "Enable", "value": True}],
                    value=[True] if enabled else [],
                    id={"type": "target-enable", "name": name},
                    className="checklist-switch",
                    style={"marginBottom": "12px", "marginTop": "10px", "marginLeft": "5px", "display": "inline-block"},
                ),
            ]),
            html.Div([
                html.Div([
                    ui.icon_button(
                        icon=icon(
                            "more",
                            className="icon normal rotate rotated" if extra_fields_open else "icon normal rotate",
                            id={"type": "target-more-icon", "name": name},
                        ),
                        color="default",
                        id={"type": "target-more", "name": name},
                        tooltip="Show/Hide extra fields",
                        tooltip_options="bottom small",
                    )
                ], style={"display": "flex", "alignItems": "center"}),
                ui.duplicate_button(id={"type": "target-duplicate", "name": name}),
                ui.delete_button(id={"type": "target-delete", "name": name}),
            ], style={"display": "flex", "alignItems": "center", "marginLeft": "0px"}, className="inline-flex-buttons"),
        ], style={
            "marginTop": "8px",
            "display": "flex",
            "flexDirection": "row",
            "width": "100%",
            "justifyContent": "space-between",
        }),
        # Extra fields: optional per-target settings (target_settings.<name> in the yaml)
        html.Div([
            html.Div([
                html.Label("Script copy", style={"fontWeight": "bold", "fontSize": "1em"}),
                dcc.Checklist(
                    options=[{"label": "Enable script copy", "value": True}],
                    value=[True] if target.get("script_copy_enable", False) else [],
                    id={"type": "target-script-copy-enable", "name": name},
                    className="checklist-switch",
                    style={"marginTop": "5px", "marginLeft": "5px"},
                ),
                html.Div("script_copy_source", style={"marginTop": "10px", "marginLeft": "5px", "marginBottom": "5px"}),
                dcc.Input(
                    value=target.get("script_copy_source", ""),
                    type="text",
                    placeholder="/path/to/script",
                    id={"type": "target-script-copy-source", "name": name},
                    className="value-input",
                    style={
                        "width": "calc(100% - var(--tile-gap))",
                        "marginLeft": "5px",
                        "marginRight": "5px",
                        "marginBottom": "5px",
                        "fontSize": "0.9em",
                        # "height": "10px",
                    },
                ),
            ], style={"marginTop": "5px", "textAlign": "left"}),
        ],
        id={"type": "target-extra-div", "name": name},
        style=Style.visible_div if extra_fields_open else Style.hidden,
        ),
    ],
    className="card configs" + ("" if enabled else " target-disabled"),
    id={"type": "target-card", "name": name},
    style={
        "padding": "10px",
        "margin": "5px",
        "display": "inline-block",
        "verticalAlign": "top",
        "boxSizing": "border-box",
    })


def add_card(text: str = "Add new target"):
    return html.Div(
        html.Div(
            html.Div(
                children=[
                    html.Div(text, style={"fontWeight": "bold", "fontSize": "1.2em", "paddingTop": "0px"}),
                    html.Div(
                        "+",
                        style={
                            "fontSize": "2.5em",
                            "lineHeight": "80px",
                            "height": "80px",
                            "marginTop": "-15px",
                            "marginBottom": "-15px",
                        }
                    ),
                ],
                style={"display": "flex", "flexDirection": "column", "alignItems": "center", "justifyContent": "center", "height": "100%"}
            ),
            id="add-target-card",
            n_clicks=0,
            style={"textDecoration": "none", "height": "100%"},
        ),
        className="card configs add hover",
        style={
            "padding": "10px",
            "margin": "5px",
            "display": "inline-block",
            "verticalAlign": "top",
            "boxSizing": "border-box",
        },
    )


def build_cards(search, odatix_settings):
    tool = get_key_from_url(search, "tool")
    if not tool:
        return [html.Div(
            "No EDA tool selected. Open this page with ?tool=<tool> (e.g. from the Run Jobs page).",
            className="error-message",
            style={"width": "100%", "marginTop": "20px"},
        )]
    target_path = (odatix_settings or {}).get("target_path", OdatixSettings.DEFAULT_TARGET_PATH)
    targets = workspace.get_targets(target_path, tool)
    cards = [target_card(target) for target in targets]
    cards.append(add_card())
    return cards


######################################
# Callbacks
######################################

# Load the page content from the url (?tool=<tool>)
@dash.callback(
    Output("target-cards-row", "children"),
    Output("select-targets-title", "children"),
    Input(f"url_{page_path}", "search"),
    State("odatix-settings", "data"),
)
def load_page(search, odatix_settings):
    tool = get_key_from_url(search, "tool")
    title = f"{get_tool_display_name(tool)} Targets" if tool else "Targets"
    return build_cards(search, odatix_settings), title


# Show/hide the extra fields of a target card
@dash.callback(
    Output({"type": "target-extra-div", "name": MATCH}, "style"),
    Output({"type": "target-more-icon", "name": MATCH}, "className"),
    Input({"type": "target-more", "name": MATCH}, "n_clicks"),
    State({"type": "target-extra-div", "name": MATCH}, "style"),
    prevent_initial_call=True,
)
def toggle_extra_fields(n_clicks, current_style):
    # Based on the current state (not n_clicks parity): extra fields may
    # start open by default (e.g. script copy already configured).
    is_open = current_style == Style.visible_div
    if is_open:
        return Style.hidden, "icon normal rotate"
    return Style.visible_div, "icon normal rotate rotated"


# Dim the card when the target is disabled
@dash.callback(
    Output({"type": "target-card", "name": MATCH}, "className"),
    Input({"type": "target-enable", "name": MATCH}, "value"),
    prevent_initial_call=True,
)
def update_card_enabled_style(enable_value):
    return "card configs" if enable_value else "card configs target-disabled"


# Enable the save button on any edit, save all changes on click
@dash.callback(
    Output({"page": page_path, "action": "save-all"}, "className"),
    Output("target-cards-row", "children", allow_duplicate=True),
    Input({"page": page_path, "action": "save-all"}, "n_clicks"),
    Input({"type": "target-title", "name": ALL}, "value"),
    Input({"type": "target-enable", "name": ALL}, "value"),
    Input({"type": "target-script-copy-enable", "name": ALL}, "value"),
    Input({"type": "target-script-copy-source", "name": ALL}, "value"),
    State({"type": "target-metadata", "name": ALL}, "data"),
    State(f"url_{page_path}", "search"),
    State("odatix-settings", "data"),
    prevent_initial_call=True,
)
def save_or_mark_dirty(save_n_clicks, titles, enables, script_copy_enables, script_copy_sources, metadata, search, odatix_settings):
    trigger_id = ctx.triggered_id

    if trigger_id == {"page": page_path, "action": "save-all"}:
        if not save_n_clicks:
            return dash.no_update, dash.no_update
        tool = get_key_from_url(search, "tool")
        if not tool:
            return dash.no_update, dash.no_update
        target_path = (odatix_settings or {}).get("target_path", OdatixSettings.DEFAULT_TARGET_PATH)

        targets = []
        for i, meta in enumerate(metadata):
            targets.append({
                "name": str(titles[i] or "").strip(),
                "original_name": meta.get("name", ""),
                "enabled": bool(enables[i]),
                "script_copy_enable": bool(script_copy_enables[i]),
                "script_copy_source": str(script_copy_sources[i] or ""),
            })
        workspace.save_target_selection(target_path, tool, targets)
        return save_button_disabled, build_cards(search, odatix_settings)

    # Any other trigger: compare current values against the loaded metadata
    for i, meta in enumerate(metadata):
        if str(titles[i] or "") != str(meta.get("name", "")):
            return save_button_enabled, dash.no_update
        if bool(enables[i]) != bool(meta.get("enabled", True)):
            return save_button_enabled, dash.no_update
        if bool(script_copy_enables[i]) != bool(meta.get("script_copy_enable", False)):
            return save_button_enabled, dash.no_update
        if str(script_copy_sources[i] or "") != str(meta.get("script_copy_source", "")):
            return save_button_enabled, dash.no_update
    return save_button_disabled, dash.no_update


# Add a new target
@dash.callback(
    Output("target-cards-row", "children", allow_duplicate=True),
    Input("add-target-card", "n_clicks"),
    State(f"url_{page_path}", "search"),
    State("odatix-settings", "data"),
    prevent_initial_call=True,
)
def handle_add_target(n_clicks, search, odatix_settings):
    if not n_clicks:
        return dash.no_update
    tool = get_key_from_url(search, "tool")
    if not tool:
        return dash.no_update
    target_path = (odatix_settings or {}).get("target_path", OdatixSettings.DEFAULT_TARGET_PATH)

    for i in range(1, 1001):
        candidate = f"new_target_{i}"
        if not workspace.target_exists(target_path, tool, candidate):
            break
    else:
        return dash.no_update

    try:
        workspace.add_target(target_path, tool, candidate)
    except Exception:
        return dash.no_update
    return build_cards(search, odatix_settings)


# Duplicate a target
@dash.callback(
    Output("target-cards-row", "children", allow_duplicate=True),
    Input({"type": "target-duplicate", "name": ALL}, "n_clicks_timestamp"),
    State({"type": "target-duplicate", "name": ALL}, "id"),
    State(f"url_{page_path}", "search"),
    State("odatix-settings", "data"),
    prevent_initial_call=True,
)
def handle_duplicate_target(timestamps, btn_ids, search, odatix_settings):
    triggered = ctx.triggered_id
    if not triggered or not isinstance(triggered, dict) or not timestamps or not btn_ids:
        return dash.no_update

    idx = max(range(len(timestamps)), key=lambda i: timestamps[i] or 0)
    if btn_ids[idx] != triggered or not timestamps[idx]:
        return dash.no_update

    tool = get_key_from_url(search, "tool")
    if not tool:
        return dash.no_update
    target_path = (odatix_settings or {}).get("target_path", OdatixSettings.DEFAULT_TARGET_PATH)

    name = triggered["name"]
    for i in range(1, 1001):
        candidate = f"{name}_copy{i}"
        if not workspace.target_exists(target_path, tool, candidate):
            break
    else:
        return dash.no_update

    try:
        workspace.duplicate_target(target_path, tool, name, candidate)
    except Exception:
        return dash.no_update
    return build_cards(search, odatix_settings)


# Open the delete confirmation popup
@dash.callback(
    Output("target-delete-popup", "className"),
    Output("target-delete-popup-message", "children"),
    Output("target-delete-info", "data"),
    Input({"type": "target-delete", "name": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def show_delete_popup(n_clicks):
    if not ctx.triggered_id or not isinstance(ctx.triggered_id, dict) or all(not n for n in n_clicks):
        return dash.no_update, dash.no_update, dash.no_update
    name = ctx.triggered_id["name"]
    msg = f"Do you really want to delete target '{name}'?"
    return "overlay-odatix visible", msg, {"name": name}


# Close the delete confirmation popup
@dash.callback(
    Output("target-delete-popup", "className", allow_duplicate=True),
    Input("target-delete-cancel-btn", "n_clicks"),
    prevent_initial_call=True,
)
def close_delete_popup(n_clicks):
    return "overlay-odatix"


# Delete a target
@dash.callback(
    Output("target-delete-popup", "className", allow_duplicate=True),
    Output("target-delete-error", "children"),
    Output("target-cards-row", "children", allow_duplicate=True),
    Input("target-delete-confirm-btn", "n_clicks"),
    State("target-delete-info", "data"),
    State(f"url_{page_path}", "search"),
    State("odatix-settings", "data"),
    prevent_initial_call=True,
)
def do_delete_target(n_clicks, info, search, odatix_settings):
    if not n_clicks or not info:
        return dash.no_update, dash.no_update, dash.no_update

    tool = get_key_from_url(search, "tool")
    if not tool:
        return dash.no_update, dash.no_update, dash.no_update
    target_path = (odatix_settings or {}).get("target_path", OdatixSettings.DEFAULT_TARGET_PATH)

    name = info["name"]
    if not workspace.target_exists(target_path, tool, name):
        return dash.no_update, "Target not found.", dash.no_update
    try:
        workspace.remove_target(target_path, tool, name)
    except Exception as e:
        return dash.no_update, f"Error: {e}", dash.no_update
    return "overlay-odatix", "", build_cards(search, odatix_settings)


######################################
# Layout
######################################

title_buttons = html.Div(
    children=[
        ui.save_button(
            id={"page": page_path, "action": "save-all"},
            tooltip="Save all changes",
            disabled=True,
        ),
    ],
    className="inline-flex-buttons",
)


layout = html.Div(
    children=[
        dcc.Location(id=f"url_{page_path}", refresh=False),
        ui.title_tile("Targets", id="select-targets-title", buttons=title_buttons, style={"marginTop": "10px", "marginBottom": "20px"}),
        html.Div(id="target-section", style={"marginBottom": "10px"}, children=[
            html.Div(
                id="target-cards-row",
                className="card-matrix configs",
            ),
        ]),
        dcc.Store(id="target-delete-info"),
        html.Div(
            id="target-delete-popup",
            className="overlay-odatix",
            children=[
                html.Div([
                    html.H2("Warning"),
                    html.Div(id="target-delete-popup-message"),
                    html.Div(
                        "The target and its settings will be removed from the target file. "
                        "Disable it instead if you may need it later.",
                        style={"marginTop": "10px", "color": "#FA5252", "fontWeight": "bold"},
                    ),
                    html.Div([
                        ui.icon_button(
                            icon=icon("delete", className="icon"),
                            color="caution",
                            text="Delete",
                            width="90px",
                            id="target-delete-confirm-btn",
                        ),
                        html.Button("Cancel", id="target-delete-cancel-btn", n_clicks=0, style={"marginLeft": "10px", "width": "90px"}),
                    ], style={"marginTop": "18px", "display": "flex", "justifyContent": "center"}),
                    html.Div(id="target-delete-error", style={"color": "red", "marginTop": "10px"}),
                ], className="popup-odatix")
            ]
        ),
    ],
    className="page-content",
    style={
        "display": "flex",
        "flexDirection": "column",
        "min-height": f"calc(100vh - {navigation.top_bar_height})",
    },
)
