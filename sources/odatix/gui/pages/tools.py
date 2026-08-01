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
EDA Tools page.

Lists the workspace EDA tools (directories under the workspace tools directory,
odatix_userconfig/tools by default) and lets the user add, edit, duplicate and
delete them. Built-in tools shipped with Odatix are listed apart: their flows are
read-only, but their settings and metrics can be overridden in the workspace (see
/tool_editor), and they can be duplicated into it to be edited as a whole.

Each tool is edited through the Tool Editor (/tool_editor?tool=...) for its
tool.yml, and the Exported Metrics Editor (/metric_editor?tool=...) for its
metrics.yml.
"""

import os
import uuid
import dash
from dash import html, dcc, Input, Output, ctx, State

import odatix.gui.ui_components as ui
from odatix.gui.icons import icon
import odatix.gui.navigation as navigation
import odatix.lib.eda_tools as eda_tools
from odatix.gui.utils import get_workspace
from odatix.lib.utils import open_path_in_explorer

page_path = "/tools"

dash.register_page(
    __name__,
    path=page_path,
    title="Odatix - EDA Tools",
    name="EDA Tools",
    order=4,
)


######################################
# Helpers
######################################

# Fallback icon used when a tool.yml does not define an "icon" key.
DEFAULT_TOOL_ICON = "assets/icons/workflow.png"

def get_builtin_tools(tools):
    """
    Names of built-in tools not shadowed by a workspace tool. A workspace file
    that only adds flows to a built-in tool does not shadow it: it is listed
    here, with the flows it adds.
    """
    workspace_tools = set(tools.names())
    return [name for name in tools.builtin_names() if name not in workspace_tools]

def tool_icon_image(meta):
    """Return the tool's tool.yml "icon" as an <img>, falling back to a default
    icon when none is defined, mirroring the image handling of /choose_eda_tool.
    Wrapped in a fixed-height box so tool names line up regardless of each
    logo's own aspect ratio."""
    tool_icon = meta.get("icon") if isinstance(meta.get("icon"), str) else None
    return html.Div(
        html.Img(
            src=tool_icon or DEFAULT_TOOL_ICON,
            className="card-img",
            style={"maxHeight": "100%", "maxWidth": "60%"},
        ),
        className="card-pictogram-wrap",
    )

def flows_line(name):
    """Small subtitle listing the flows a tool declares (see the "flows" section
    of tool.yml). Returns None for a tool with a single flow, which is the
    common case and would only add noise."""
    try:
        flows = eda_tools.list_flows(name)
    except Exception:
        return None
    if len(flows) < 2:
        return None
    labels = ", ".join(flow["label"] for flow in flows.values())
    return html.Div(
        f"{len(flows)} flows: {labels}",
        title=labels,
        style={
            "fontSize": "0.8em",
            "opacity": "0.6",
            "textAlign": "center",
            "marginTop": "2px",
            "textOverflow": "ellipsis",
            "overflow": "hidden",
            "whiteSpace": "nowrap",
        },
    )


def build_tool_cards(tools):
    cards = [workspace_tool_card(tools.entry(name)) for name in tools.names()]
    cards.append(add_card("Create New Tool"))
    return cards

def build_builtin_cards(tools):
    return [builtin_tool_card(tools.entry(name)) for name in get_builtin_tools(tools)]


######################################
# UI Components
######################################

def workspace_tool_card(tool):
    name = tool.name
    unique_key = str(uuid.uuid4())
    visual = tool_icon_image(tool.document)
    flows = flows_line(name)
    return html.Div(
        [
            *([visual] if visual is not None else []),
            html.Div(name, title=name, style={"fontWeight": "bold", "fontSize": "1.05em", "textAlign": "center", "textOverflow": "ellipsis", "overflow": "hidden", "whiteSpace": "nowrap"}),
            *([flows] if flows is not None else []),
            html.Div(
                [
                    html.Div(
                        [
                            ui.icon_button(
                                id=f"button-edit-tool-{name}",
                                icon=icon("gear", className="icon black"),
                                text="Settings",
                                color="default",
                                link=f"/tool_editor?tool={name}",
                                width="auto",
                                bold=False,
                            ),
                            ui.icon_button(
                                id=f"button-metrics-tool-{name}",
                                icon=icon("metrics", className="icon black"),
                                text="Metrics",
                                color="default",
                                link=f"/metric_editor?tool={name}",
                                width="auto",
                                bold=False,
                            ),
                        ],
                        style={"display": "flex", "gap": "4px"},
                    ),
                    html.Div(
                        [
                            ui.icon_button(
                                id={"type": "tool-button-open", "name": name},
                                icon=icon("folder_open", className="icon"),
                                color="secondary",
                                width="auto",
                                tooltip="Open tool directory",
                                tooltip_options="bottom",
                            ),
                            ui.duplicate_button(id={"type": "tool-button-duplicate", "name": name}),
                            ui.delete_button(id={"type": "tool-button-delete", "name": name}),
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
        style={"padding": "18px 20px", "margin": "0", "width": "100%", "boxSizing": "border-box"},
        key=unique_key,
    )

def builtin_tool_card(tool):
    name = tool.name
    unique_key = str(uuid.uuid4())
    label = eda_tools.get_tool_label(name)
    visual = tool_icon_image(eda_tools.load_tool_settings(name))
    flows = flows_line(name)
    # A built-in tool the workspace already adds flows to or overrides settings of
    # says so: the card is still the built-in one, its flows are not owned by the
    # workspace.
    extended = tool.has_overlay
    return html.Div(
        [
            *([visual] if visual is not None else []),
            html.Div(label, title=name, style={"fontWeight": "bold", "fontSize": "1.05em", "textAlign": "center", "textOverflow": "ellipsis", "overflow": "hidden", "whiteSpace": "nowrap"}),
            html.Div(
                "built-in + your changes" if extended else "built-in",
                style={"fontSize": "0.8em", "opacity": "0.6", "textAlign": "center", "marginTop": "2px"},
            ),
            *([flows] if flows is not None else []),
            html.Div(
                [
                    ui.icon_button(
                        id=f"button-flows-tool-{name}",
                        icon=icon("gear", className="icon black"),
                        text="Settings",
                        tooltip="Override this built-in tool's settings and add flows of your own to it, "
                                "without copying it",
                        tooltip_options="bottom delay",
                        color="default",
                        link=f"/tool_editor?tool={name}",
                        width="auto",
                        bold=False,
                    ),
                    ui.icon_button(
                        id=f"button-metrics-builtin-tool-{name}",
                        icon=icon("metrics", className="icon black"),
                        text="Metrics",
                        tooltip="See the metrics of this built-in tool, and complete or override them in your workspace",
                        tooltip_options="bottom delay",
                        color="default",
                        link=f"/metric_editor?tool={name}",
                        width="auto",
                        bold=False,
                    ),
                    ui.icon_button(
                        id={"type": "tool-button-fork", "name": name},
                        icon=icon("duplicate", className="icon black"),
                        text="Duplicate",
                        tooltip="Copy this built-in tool into your workspace to edit all of it",
                        tooltip_options="bottom delay",
                        color="default",
                        width="auto",
                        bold=False,
                    ),
                ],
                style={
                    "marginTop": "14px",
                    "display": "flex",
                    "flexDirection": "row",
                    "width": "100%",
                    "alignItems": "center",
                    "justifyContent": "center",
                    "gap": "4px",
                },
            ),
        ],
        className="card",
        style={"padding": "18px 20px", "margin": "0", "width": "100%", "boxSizing": "border-box", "opacity": "0.85"},
        key=unique_key,
    )

def add_card(text: str):
    btn_id = {"type": "tool-button-add"}
    return html.Div(
        html.Div(
            html.Div(
                children=[
                    html.Div(text, style={"fontWeight": "bold", "fontSize": "1.05em", "color": "var(--add-card-text-color)"}),
                    html.Div("+", style={"fontSize": "2em", "lineHeight": "1", "marginTop": "8px"}),
                ],
                style={"textAlign": "center"},
            ),
            id=btn_id,
            n_clicks=0,
            style={"textDecoration": "none", "color": "var(--add-card-text-color)", "display": "flex", "flexDirection": "column", "alignItems": "center", "justifyContent": "center", "height": "100%"},
        ),
        className="card add hover",
        style={"padding": "18px 20px", "margin": "0", "width": "100%", "boxSizing": "border-box"},
    )


######################################
# Callbacks
######################################

@dash.callback(
    Output("tool-cards-matrix", "children"),
    Output("builtin-tool-cards-matrix", "children"),
    Input("tool-cards-matrix", "children"),
    State("odatix-settings", "data"),
)
def update_cards(_, odatix_settings):
    tools = get_workspace(odatix_settings).tools
    return build_tool_cards(tools), build_builtin_cards(tools)

@dash.callback(
    Output("tool-cards-matrix", "children", allow_duplicate=True),
    Output("builtin-tool-cards-matrix", "children", allow_duplicate=True),
    Input({"type": "tool-button-duplicate", "name": dash.ALL}, "n_clicks_timestamp"),
    State({"type": "tool-button-duplicate", "name": dash.ALL}, "id"),
    State("odatix-settings", "data"),
    prevent_initial_call=True,
)
def direct_duplicate(dupl_timestamps, btn_ids, odatix_settings):
    triggered = ctx.triggered_id
    if not triggered or not isinstance(triggered, dict):
        return dash.no_update, dash.no_update
    if not dupl_timestamps or not btn_ids:
        return dash.no_update, dash.no_update

    idx = max(range(len(dupl_timestamps)), key=lambda i: dupl_timestamps[i] or 0)
    btn_id = btn_ids[idx]
    if btn_id != triggered or not dupl_timestamps[idx]:
        return dash.no_update, dash.no_update

    tools = get_workspace(odatix_settings).tools
    name = btn_id["name"]

    base = name
    suffix = 1
    while True:
        new_name = f"{base}_copy{suffix}"
        if not tools.exists(new_name):
            break
        suffix += 1
        if suffix > 1000:
            return dash.no_update, dash.no_update

    try:
        tools.duplicate(name, new_name)
    except Exception:
        return dash.no_update, dash.no_update

    return build_tool_cards(tools), build_builtin_cards(tools)

@dash.callback(
    Output("tool-cards-matrix", "children", allow_duplicate=True),
    Output("builtin-tool-cards-matrix", "children", allow_duplicate=True),
    Input({"type": "tool-button-fork", "name": dash.ALL}, "n_clicks_timestamp"),
    State({"type": "tool-button-fork", "name": dash.ALL}, "id"),
    State("odatix-settings", "data"),
    prevent_initial_call=True,
)
def fork_builtin(fork_timestamps, btn_ids, odatix_settings):
    triggered = ctx.triggered_id
    if not triggered or not isinstance(triggered, dict):
        return dash.no_update, dash.no_update
    if not fork_timestamps or not btn_ids:
        return dash.no_update, dash.no_update

    idx = max(range(len(fork_timestamps)), key=lambda i: fork_timestamps[i] or 0)
    btn_id = btn_ids[idx]
    if btn_id != triggered or not fork_timestamps[idx]:
        return dash.no_update, dash.no_update

    tools = get_workspace(odatix_settings).tools
    name = btn_id["name"]

    suffix = 1
    while True:
        target_name = f"{name}_copy{suffix}"
        if not tools.exists(target_name):
            break
        suffix += 1
        if suffix > 1000:
            return dash.no_update, dash.no_update

    try:
        tools.import_builtin(name, target_name)
    except Exception:
        return dash.no_update, dash.no_update

    return build_tool_cards(tools), build_builtin_cards(tools)

@dash.callback(
    Output("tool-open-dummy", "data"),
    Input({"type": "tool-button-open", "name": dash.ALL}, "n_clicks_timestamp"),
    State({"type": "tool-button-open", "name": dash.ALL}, "id"),
    State("odatix-settings", "data"),
    prevent_initial_call=True,
)
def open_tool_directory(open_timestamps, btn_ids, odatix_settings):
    triggered = ctx.triggered_id
    if not triggered or not isinstance(triggered, dict):
        return dash.no_update
    if not open_timestamps or not btn_ids:
        return dash.no_update

    idx = max(range(len(open_timestamps)), key=lambda i: open_timestamps[i] or 0)
    btn_id = btn_ids[idx]
    if btn_id != triggered or not open_timestamps[idx]:
        return dash.no_update

    tool_dir = get_workspace(odatix_settings).tools.entry(btn_id["name"]).path
    if not os.path.isdir(tool_dir):
        return dash.no_update

    try:
        open_path_in_explorer(tool_dir)
    except Exception:
        return dash.no_update

    return dash.no_update

@dash.callback(
    Output("tool-delete-popup", "className"),
    Output("tool-delete-popup-message", "children"),
    Output("tool-delete-info", "data"),
    Input({"type": "tool-button-delete", "name": dash.ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def show_delete_popup(n_clicks):
    if not ctx.triggered_id or not isinstance(ctx.triggered_id, dict) or all(n == 0 for n in n_clicks):
        return dash.no_update, dash.no_update, dash.no_update
    name = ctx.triggered_id["name"]
    msg = f"Do you really want to delete tool '{name}'?"
    return "overlay-odatix visible", msg, {"name": name}

@dash.callback(
    Output("tool-delete-popup", "className", allow_duplicate=True),
    Input("tool-delete-cancel-btn", "n_clicks"),
    prevent_initial_call=True,
)
def close_delete_popup(_):
    return "overlay-odatix"

@dash.callback(
    Output("tool-delete-popup", "className", allow_duplicate=True),
    Output("tool-delete-error", "children"),
    Output("tool-cards-matrix", "children", allow_duplicate=True),
    Output("builtin-tool-cards-matrix", "children", allow_duplicate=True),
    Input("tool-delete-confirm-btn", "n_clicks"),
    State("tool-delete-info", "data"),
    State("odatix-settings", "data"),
    prevent_initial_call=True,
)
def do_delete(n_clicks, info, odatix_settings):
    if not n_clicks or not info:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update

    tools = get_workspace(odatix_settings).tools
    name = info["name"]
    if not tools.exists(name):
        return dash.no_update, "Tool not found.", dash.no_update, dash.no_update

    try:
        tools.delete(name)
    except Exception as e:
        return dash.no_update, f"Error: {e}", dash.no_update, dash.no_update

    return "overlay-odatix", "", build_tool_cards(tools), build_builtin_cards(tools)

@dash.callback(
    Output({"type": "update_url", "id": page_path}, "data"),
    Input({"type": "tool-button-add"}, "n_clicks_timestamp"),
    State("odatix-settings", "data"),
    prevent_initial_call=True,
)
def handle_add_card(n_click_timestamp, odatix_settings):
    if not n_click_timestamp:
        return dash.no_update

    tools = get_workspace(odatix_settings).tools
    base_name = "new_tool"

    for i in range(1, 1001):
        candidate = f"{base_name}{i}"
        if not tools.exists(candidate):
            return {"href": f"/tool_editor?tool={candidate}", "id": page_path}

    return {"href": "/tool_editor", "id": page_path}


######################################
# Layout
######################################

layout = html.Div(
    children=[
        dcc.Location(id="url", refresh="callback-nav"),
        html.Div(
            children=[
                ui.page_header("EDA Tools", "Add and configure the EDA tools of your workspace.", back_link="/"),
                html.Div(id="tool-cards-matrix", className="card-matrix configs", style={"gap": "var(--tile-gap)"}),
                html.Div(
                    [
                        html.H2(
                            [
                                html.Span("Built-in tools"),
                            ],
                            id="builtin-tools-title",
                        ),
                        ui.tooltip_icon("Tools shipped with Odatix. Their settings can be overridden in your workspace; "
                                    "duplicate one into it to edit all of it, flows included."),
                    ],
                    className="odx-section-head",
                    style={"justifyContent": "center", "marginTop": "32px", "gap": "0"},
                ),
                html.Div(id="builtin-tool-cards-matrix", className="card-matrix configs", style={"gap": "var(--tile-gap)"}),
            ],
            style={"display": "block", "width": "auto", "textAlign": "center", "marginBottom": "10px"},
        ),
        dcc.Store(id="tool-delete-info"),
        dcc.Store(id="tool-open-dummy"),
        html.Div(
            id="tool-delete-popup",
            className="overlay-odatix",
            children=[
                html.Div(
                    [
                        html.H2("Warning"),
                        html.Div(id="tool-delete-popup-message"),
                        html.Div("This action is irreversible.", style={"marginTop": "10px", "color": "#FA5252", "fontWeight": "bold"}),
                        html.Div(
                            [
                                ui.icon_button(
                                    icon=icon("delete", className="icon"),
                                    color="caution",
                                    text="Delete",
                                    width="90px",
                                    id="tool-delete-confirm-btn",
                                ),
                                html.Button("Cancel", id="tool-delete-cancel-btn", n_clicks=0, style={"marginLeft": "10px", "width": "90px"}),
                            ],
                            style={"marginTop": "18px", "display": "flex", "justifyContent": "center"},
                        ),
                        html.Div(id="tool-delete-error", style={"color": "red", "marginTop": "10px"}),
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
