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

from typing import Optional, Union
from dash_svg import Svg
from dash import html, dcc
from dash.development.base_component import Component

from odatix.gui.icons import icon, pictogram

def icon_button(icon, color, text="", id=None, link=None, multiline=False, width="115px", style={}, tooltip:str="", tooltip_options:str="bottom"):  
    """
    Create a button with an icon and optional text.
    Args:
        icon (str or Svg): The icon to display (filename in assets/icons or Svg component).
        color (str): The color of the button (e.g., "red", "blue", "green").
        text (str, optional): The text to display next to the icon. Defaults to "" (just the icon).
        id (str, optional): The id of the button. Defaults to None.
        link (str | dict, optional): If provided, the button will be a link to this URL. Defaults to None.
        multiline (bool, optional): If True, adjust vertical alignment for multiline text. Defaults to False.
    """ 
    if text:
        style = {**style, "min-width": width}
    inner_children = [
        icon if isinstance(icon, Svg) else html.Img(
            src=f"/assets/icons/{icon}",
            alt=text if text else icon.capitalize(),
            style={"width": "22px", "height": "22px"},
        ),
    ]
    if text:
        inner_children.append(
            html.Span(text, style={"fontWeight": "600", "fontSize": "1em", "marginLeft": "6px", "lineHeight": "1.15", "whiteSpace": "nowrap"})
        )
    content = html.Button(
        html.Div(
            children=inner_children,
            style={
                "display": "flex",
                "alignItems": "center",
                "justifyContent": "flex-start" if text else "center",
                "width": "100%",
                "gap": "0px",
            },
        ),
        id=id if id else "",
        n_clicks=0,
        className=f"color-button {color} icon-button{'' if text else ' icon-only'}{f' tooltip {tooltip_options}' if tooltip else ''}",
        style=style,
        **{'data-tooltip': tooltip},
    )
    if link is None:
        return content
    else:
        link_kwargs = {
            "children": content,
            "href": link,
            "style": {"textDecoration": "none"}
        }
        if isinstance(id, dict):
            link_id = id.copy()
            link_id.update({"is_link": True})
        elif isinstance(id, str):
            link_id = id + "-link"
        else:   
            link_id = None
        if link_id is not None:
            link_kwargs["id"] = link_id
        return dcc.Link(**link_kwargs)

def delete_button(id, large=False, tooltip:str="Delete"):
    return icon_button(
        icon=icon("delete", width="25px", height="25px", className="icon red"),
        color="caution", 
        text="Delete" if large else "", 
        tooltip=tooltip,
        tooltip_options="bottom auto",
        id=id,
    )

def duplicate_button(id, large=False, tooltip:str="Duplicate"):
    return icon_button(
        icon=icon("duplicate", className="icon blue"),
        color="secondary",
        text="Duplicate" if large else "", 
        tooltip=tooltip,
        tooltip_options="bottom auto",
        id=id,
    )

def save_button(id, text="Save All", disabled=False, tooltip:str="Save all changes"):
    if isinstance(id, dict):
        icon_id = id.copy()
        icon_id.update({"is_icon": True})
    else:
        icon_id = id + "-icon"

    return icon_button(
        icon=icon("save", className="icon", id=icon_id),
        color="disabled" if disabled else "warning",
        text=text, 
        tooltip=tooltip,
        tooltip_options="bottom auto caution",
        id=id,
    )


def title_tile(text:str="", id:Union[str, dict]="main-title", buttons:html.Div=html.Div(), back_button_link:Optional[str]=None, back_button_id:Optional[str]=None, tooltip:str="", switch:Optional[bool]=None, style={}):
    if isinstance(id, dict):
        checklist_id = id.copy()
        checklist_id.update({"is_switch": True})
    else:
        checklist_id = id + "-switch"
    title_content = html.Div(
        children=[
            html.Div(
                children=[
                    dcc.Checklist(
                        options=[{"label": "", "value": True}],
                        value=[True] if switch else [],
                        id=checklist_id,
                        className="checklist-switch",
                        style={"display": "inline-block", "transform": "translate(-7px, -17px)"},
                    ) if switch is not None else html.Div(),
                    html.H3(text, id=id, style={"marginBottom": "0px", "display": "inline-block"}),
                    tooltip_icon(tooltip) if tooltip else html.Div(style={"display": "none"}),
                ],
            ),
            html.Div(
                [buttons],
            ),
        ],
        className="title-tile-flex",
        style={
            "display": "flex",
            "alignItems": "center",
            "padding": "0px",
            "justifyContent": "space-between",
        }
    )
    style = {**style, "position": "relative"}
    return html.Div(
        html.Div(
            children=[
                back_button(link=back_button_link, id=back_button_id),
                title_content
            ],
            className="tile title",
            style=style,
        ),
        className="card-matrix config",
        style={"marginTop": "10px", "marginBottom": "0px"},
    )

def subtitle_div(text:str="", id:str="main-title", buttons:html.Div=html.Div()):
    title_content = html.Div([
        html.H3(text, id=id, style={"marginBottom": "0px"}),
        html.Div(
            [buttons],
        ),
    ],
    className="title-tile-flex",
    style={
        "display": "flex",
        "alignItems": "center",
        "padding": "0px",
        "margin-right": "-15px",
        "margin-top": "0px",
        "justifyContent": "space-between",
    })
    return title_content

def back_button(link: Optional[str]="/", id: Optional[str]="back-button"):
    if link is None and id is None:
        return html.Div()
    id_kwargs = {"id": id} if id is not None else {}
    if link:
        button = dcc.Link(
            icon("back", className="icon back-button", width="30px", height="30px"),
            href=link,
            style={"textDecoration": "none"},
            **id_kwargs,
        )
    else:
        button = html.Button(
            icon("back", className="icon back-button", width="30px", height="30px"),
            n_clicks=0,
            style={"background": "none", "border": "none", "padding": "0px", "margin": "0px"},
            **id_kwargs,
        )
    return html.Div(
        button,
        style={
            "position": "absolute",
            "display": "flex",
            "alignItems": "center",
            "left": "0",
            "top": "0",
            "height": "100%",
            "width": "45px",
            "transform": "translate(-45px)",
        },
    )

def tooltip_icon(tooltip: str="", tooltip_options: str="secondary") -> Component:
    return html.Div(
        children=[
            icon(
                "tooltip",
                className="icon",
                color="default",
                width="20px",
                height="20px",
            ),
        ],
        className="tooltip " + tooltip_options,
        style={"display": "inline-block", "transform": "translate(5px, 1px)", "verticalAlign": "middle"},
        **{"data-tooltip": tooltip},
    )

######################################
# Design system (odx-*)
#
# Shared page furniture in the style of the monitor dashboard, Odatix Explorer
# and the /run_jobs page. The matching css lives in assets/odatix-ui.css.
######################################

def page_bar(
    title,
    actions=None,
    extra=None,
    back_link: Optional[str]=None,
    back_id: Optional[Union[str, dict]]=None,
    title_id: Optional[Union[str, dict]]=None,
    id: Optional[Union[str, dict]]=None,
) -> Component:
    """
    Sticky page bar: back arrow, title (plain text or any component, e.g. an
    editable name input), action buttons on the right and an optional second
    row (stat strip, toolbar).
    """
    left = []
    if back_link is not None or back_id is not None:
        link_kwargs = {"id": back_id} if back_id is not None else {}
        left.append(
            dcc.Link(
                icon("back", className="icon back-button", width="28px", height="28px"),
                href=back_link if back_link is not None else "/",
                className="odx-back",
                **link_kwargs,
            )
        )
    if isinstance(title, str):
        title_kwargs = {"id": title_id} if title_id is not None else {}
        left.append(html.H1(title, className="odx-title", **title_kwargs))
    else:
        left.append(title)

    children = [
        html.Div(
            children=[
                html.Div(left, className="odx-header-titles"),
                html.Div(actions if actions is not None else [], className="odx-header-actions"),
            ],
            className="odx-header-row",
        )
    ]
    if extra is not None:
        children.append(extra)

    kwargs = {"id": id} if id is not None else {}
    return html.Div(children, className="odx-header", **kwargs)


def title_input(value: str="", id: Union[str, dict]="page-title", placeholder: str="") -> Component:
    """Editable page title, used as the `title` of page_bar()."""
    return dcc.Input(
        value=value,
        id=id,
        type="text",
        placeholder=placeholder,
        className="odx-title-input",
    )


def stat(value, label: str, className: str="") -> Component:
    """Pill of the stat strip: a big value and its label."""
    return html.Div(
        children=[
            html.Span(str(value), className="odx-stat-value"),
            html.Span(label, className="odx-stat-label"),
        ],
        className=f"odx-stat {className}".strip(),
    )


def tag(text: str, className: str="") -> Component:
    return html.Span(text, className=f"odx-tag {className}".strip())


def badge(text, className: str="", id: Optional[Union[str, dict]]=None) -> Component:
    kwargs = {"id": id} if id is not None else {}
    return html.Span(text, className=f"odx-badge {className}".strip(), **kwargs)


def section(title: str, children, id: Optional[Union[str, dict]]=None, heading_id: Optional[Union[str, dict]]=None, tools=None, tooltip: str="") -> Component:
    """Page section: an uppercase heading with optional tools, then its content."""
    heading_kwargs = {"id": heading_id} if heading_id is not None else {}
    section_kwargs = {"id": id} if id is not None else {}
    heading = [html.Span(title)]
    if tooltip:
        heading.append(tooltip_icon(tooltip))
    return html.Div(
        children=[
            html.Div(
                children=[
                    html.H2(heading, **heading_kwargs),
                    html.Div(tools if tools is not None else [], className="odx-section-tools"),
                ],
                className="odx-section-head",
            ),
            children,
        ],
        className="odx-section",
        **section_kwargs,
    )


def panel(title=None, tools=None, body=None, className: str="", title_id: Optional[Union[str, dict]]=None, body_className: str="", id: Optional[Union[str, dict]]=None) -> Component:
    """
    Flat panel with an optional hairline header, the surface used all over the
    app. Without a title the body is padded by the panel itself.
    """
    kwargs = {"id": id} if id is not None else {}
    if title is None:
        return html.Div(body, className=f"odx-panel padded {className}".strip(), **kwargs)

    title_kwargs = {"id": title_id} if title_id is not None else {}
    return html.Div(
        children=[
            html.Div(
                children=[
                    html.Div(title, className="odx-panel-title", **title_kwargs),
                    html.Div(tools if tools is not None else [], className="odx-panel-tools"),
                ],
                className="odx-panel-header",
            ),
            html.Div(body, className=f"odx-panel-body {body_className}".strip()),
        ],
        className=f"odx-panel {className}".strip(),
        **kwargs,
    )


def caption(text, tooltip: str="") -> Component:
    """Small uppercase caption introducing a group of fields inside a panel."""
    children = [html.Span(text)]
    if tooltip:
        children.append(tooltip_icon(tooltip))
    return html.Div(children, className="odx-panel-caption")


def grid(children, className: str="", id: Optional[Union[str, dict]]=None) -> Component:
    """Responsive auto-fit grid of panels."""
    kwargs = {"id": id} if id is not None else {}
    return html.Div(children, className=f"odx-grid {className}".strip(), **kwargs)


def form_field(
    label: str,
    id: Union[str, dict],
    value: str="",
    tooltip: str="",
    placeholder: str="",
    tooltip_options: str="secondary",
    style: Optional[dict]=None,
    disabled: bool=False,
    className: str="",
    type=None,
) -> Component:
    """Labelled text/number input."""
    return html.Div(
        children=[
            html.Div(
                children=[
                    html.Label(label),
                    tooltip_icon(tooltip, tooltip_options) if tooltip else html.Div(style={"display": "none"}),
                ],
                className="odx-field-label",
            ),
            dcc.Input(id=id, value=value, type=type, placeholder=placeholder, disabled=disabled),
        ],
        className=f"odx-field {className}".strip(),
        style=style or {},
    )


def form_area(
    label: str,
    id: Union[str, dict],
    value: str="",
    tooltip: str="",
    placeholder: str="",
    tooltip_options: str="secondary",
    style: Optional[dict]=None,
    className: str="",
    textarea_className: str="auto-resize-textarea",
) -> Component:
    """Labelled multi-line (monospace) input."""
    return html.Div(
        children=[
            html.Div(
                children=[
                    html.Label(label),
                    tooltip_icon(tooltip, tooltip_options) if tooltip else html.Div(style={"display": "none"}),
                ],
                className="odx-field-label",
            ),
            dcc.Textarea(id=id, value=value, placeholder=placeholder, className=textarea_className),
        ],
        className=f"odx-field {className}".strip(),
        style=style or {},
    )


def form_dropdown(label: str, id: Union[str, dict], options, value=None, tooltip: str="", placeholder: str="", clearable: bool=True, className: str="") -> Component:
    """Labelled dropdown."""
    return html.Div(
        children=[
            html.Div(
                children=[
                    html.Label(label),
                    tooltip_icon(tooltip) if tooltip else html.Div(style={"display": "none"}),
                ],
                className="odx-field-label",
            ),
            dcc.Dropdown(id=id, options=options, value=value, placeholder=placeholder, clearable=clearable),
        ],
        className=f"odx-field {className}".strip(),
    )


def switch_row(label: str, id: Union[str, dict], checked: bool=False, tooltip: str="") -> Component:
    """A labelled toggle switch, the standard way to flip a boolean setting."""
    return html.Div(
        children=[
            dcc.Checklist(
                options=[{"label": label, "value": True}],
                value=[True] if checked else [],
                id=id,
                className="checklist-switch",
            ),
            tooltip_icon(tooltip) if tooltip else html.Div(style={"display": "none"}),
        ],
        className="odx-switch-row",
    )


def inline_switch(label: str, id: Union[str, dict], checked: bool=False, tooltip: str="") -> Component:
    """Compact switch stacked under its own label, used next to an input."""
    return html.Div(
        children=[
            html.Div(
                children=[html.Span(label), tooltip_icon(tooltip) if tooltip else html.Div(style={"display": "none"})],
                className="odx-field-label",
            ),
            dcc.Checklist(
                options=[{"label": "", "value": True}],
                value=[True] if checked else [],
                id=id,
                className="checklist-switch",
            ),
        ],
        className="odx-inline-switch",
    )


def add_card(id: Union[str, dict], text: str="Add", className: str="") -> Component:
    """Dashed "add an item" placeholder, sized like the cards it sits next to."""
    return html.Div(
        children=[
            html.Div("+", className="odx-add-card-plus"),
            html.Div(text, className="odx-add-card-text"),
        ],
        id=id,
        n_clicks=0,
        className=f"odx-add-card {className}".strip(),
    )


def empty_state(text: str, className: str="") -> Component:
    return html.Div(text, className=f"odx-panel odx-empty {className}".strip())


def card_pictogram(name: str, size: str = "52px") -> Component:
    """Card visual: a clean line-art pictogram (preferred) rendered from the icon set."""
    return html.Div(pictogram(name, size=size), className="card-pictogram-wrap")


def page_header(title: str, subtitle: str = "", back_link: Optional[str] = None) -> Component:
    """Centered page header (title + optional subtitle) in the modern Odatix style."""
    children = []
    if back_link:
        children.append(
            dcc.Link(
                icon("back", className="icon back-button", width="30px", height="30px"),
                href=back_link,
                className="page-header-back",
                style={
                    "position": "absolute",
                    "left": "0",
                    "top": "0",
                    "display": "flex",
                    "alignItems": "center",
                    "height": "100%",
                    "textDecoration": "none",
                },
            )
        )
    children.append(html.H1(title, className="page-header-title"))
    if subtitle:
        children.append(html.P(subtitle, className="page-header-subtitle"))
    style = {"position": "relative"} if back_link else None
    return html.Div(children, className="page-header", style=style)


def card_grid(children, id: Optional[Union[str, dict]] = None) -> Component:
    """Responsive auto-fit grid of cards."""
    kwargs = {"className": "card-grid"}
    if id is not None:
        kwargs["id"] = id
    return html.Div(children, **kwargs)


def create_card_button(page: dict) -> Component:
    """
    Build a menu card. Prefer an inline line-art pictogram (page["icon"]);
    fall back to a PNG/SVG image (page["image"]) for backward compatibility.
    """
    if page.get("icon"):
        visual = card_pictogram(page["icon"])
    else:
        visual = html.Img(
            src=page["image"],
            className="card-img",
            style={"maxHeight": "72px", "maxWidth": "60%"},
        )
    options = {
        "className": "card home hover",
        "style": {"textDecoration": "none"},
        "children": [
            visual,
            html.Div(
                page["name"],
                className="card-title",
            ),
            html.Div(
                page["description"],
                className="card-description",
            ),
        ],
    }
    if "id" in page:
        options["id"] = page["id"]
    if "link" in page:
        options["href"] = page["link"]
        if page["link"].startswith("/"):
            return dcc.Link(
                **options
            )
        else:
            options["target"] = "_blank"
            return html.A(
                **options
            )
    else:
        return html.Div(
            **options
        )
