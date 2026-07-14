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
from dash import html, dcc, Input, Output, State, ctx
from typing import Optional, Sequence#, Literal

import odatix.components.workspace as workspace
from odatix.gui.icons import icon
from odatix.gui.utils import get_key_from_url
import odatix.gui.ui_components as ui
from odatix.gui.css_helper import Style
import odatix.gui.navigation as navigation
import odatix.lib.hard_settings as hard_settings
from odatix.lib.settings import OdatixSettings

page_path = "/select_targets"

dash.register_page(
    __name__,
    path=page_path,
    title='Odatix - Target Selection',
    name='Select Targets',
    order=3,
)

MAX_PREVIEW_COMBINATIONS = 10000

######################################
# UI Components
######################################


def target_card(tool_uuid, target_name, target_layout="normal"):
    display_name = target_name[:-4] if target_name.endswith(".txt") else target_name

    return html.Div([
        html.Div([
            dcc.Input(
                value=f"{display_name}",
                type="text",
                id={"type": "config-title", "tool_uuid": tool_uuid, "target_name": target_name},
                className="title-input",
                style={
                    "width": "calc(100% - 20px)",
                    "marginLeft": "5px",
                    "marginRight": "5px",
                    "fontWeight": "bold",
                    "fontSize": "1.1em",
                    "height": "10px",
                    "marginTop": "-5px",
                    "marginBottom": "2px",
                    "textAlign": "center",
                },
            )
        ]),
        dcc.Store(id={"type": "config-metadata", "tool_uuid": tool_uuid, "target_name": target_name}, data={"tool_uuid": tool_uuid, "target_name": target_name}),
        html.Div([
            html.Div([
                dcc.Checklist(
                    options=[{"label": "Enable", "value": True}],
                    value=[True] if True else [],
                    id="overwrite",
                    className="checklist-switch",
                    style={"marginBottom": "12px", "marginTop": "10px", "marginLeft": "5px", "display": "inline-block"},
                ),
            ]),
            html.Div([
                html.Div([
                    ui.icon_button(
                        icon=icon("more", className="icon normal rotate", id={"type": "more-fields-icon", "target_name": target_name}),
                        color="default",
                        id={"type": "more-fields", "target_name": target_name},
                        tooltip="Show/Hide extra fields",
                        tooltip_options="bottom small",
                    )
                ], id={"type": "more-fields-div", "target_name": target_name}, style={"display": "flex", "alignItems": "center"}),
                ui.duplicate_button(id={"type": "duplicate-config", "tool_uuid": tool_uuid, "target_name": target_name}),
                ui.delete_button(id={"type": "delete-config", "tool_uuid": tool_uuid, "target_name": target_name}),
            ], style={"display": "flex", "alignItems": "center", "marginLeft": "0px"}, className="inline-flex-buttons"),
        ], style={
            "marginTop": "8px",
            "display": "flex",
            "flexDirection": "row",
            "width": "100%",
            "justifyContent": "space-between",
        }),
        dcc.Store(id={"type": "initial-title", "tool_uuid": tool_uuid, "target_name": target_name}, data=display_name),
    ], 
    className="card configs", 
    id={"type": "config-card", "tool_uuid": tool_uuid, "target_name": target_name},
    style={
        "padding": "10px", 
        "margin": "5px", 
        "display": "inline-block", 
        "verticalAlign": "top"
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
            id="new-variable",
            n_clicks=0,
            style={"textDecoration": "none", "height": "100%"},
        ),
        className=f"card configs add hover",
        id="add-config-card",
        style={
            "padding": "10px",
            "margin": "5px",
            "display": "inline-block",
            "verticalAlign": "top",
            "boxSizing": "border-box"
        },
    )


def target_field(
    var: str,
    # type: Literal['text', 'number', 'password', 'email', 'range', 'search', 'tel', 'url', 'hidden'] = "text",
    type = "text",
    name: str = "",
    label: Optional[str] = None,
    options: Optional[list] = None,
    value: str = "",
    placeholder: str = "",
    default_style: dict = Style.hidden
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
                        id={"type": f"variable-field-{name}", "name": var},
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
                        id={"type": f"variable-field-{name}", "name": var},
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
        id={"type": f"variable-field-{name}-div", "name": var},
        style=default_style
    )

######################################
# Callbacks
######################################

@dash.callback(
    Output({"type": "target-cards-row", "tool_uuid": "Vivado"}, "children"),
    Input(f"url_{page_path}", "search"),
    prevent_initial_call=True
)
def update_target_cards(
    search,
):
    return [
        target_card(
            tool_uuid="Vivado",
            target_name="xc7a35tcsg324-1",
            target_layout="wide",
        ),
        target_card(
            tool_uuid="Vivado",
            target_name="xc7a100tcsg324-1",
            target_layout="wide",
        ),
        add_card(),
    ]

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
        html.Div(id={"page": page_path, "type": "title-div"}, style={"marginTop": "20px"}),
        ui.title_tile("Vivado targets", buttons=title_buttons, style={"marginTop": "10px", "marginBottom": "20px"}),
        # html.H2("Vivado Targets", style={"textAlign": "center"}),
        html.Div(id="target-section", style={"marginBottom": "10px"}, children=[
            html.Div(
                id={"type": "target-cards-row", "tool_uuid": "Vivado"},
                style={
                    "display": "flex",
                    "flexWrap": "wrap",
                    "justifyContent": "center",
                },
            ),
        ]),
    ],
    className="page-content",
    style={
        "display": "flex",  
        "flexDirection": "column",
        "min-height": f"calc(100vh - {navigation.top_bar_height})",
    },
)
