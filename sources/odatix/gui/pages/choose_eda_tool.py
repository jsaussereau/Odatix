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
Tool, flow and step selection: everything that has to be decided before the job
settings page, in a single click.

A flow is a named way of running a job type with a given eda tool (a different
script, different options, sometimes a different binary); a flow can in turn be
split into ordered steps, and a run can stop at any of them and be resumed
later. Both are declared in the "flows" section of a tool.yml (see
odatix.lib.eda_tools).

Every choice a tool offers is laid out inside its own card, so the page shows
what is available at a glance and every card leads straight to the job
settings: a tool with a single one shot flow is one card-sized link, a tool with
several flows lists them as buttons, and a flow split into steps lists its steps
as "run up to here" buttons. There is nothing to confirm and no state to keep.
"""

import os
from urllib.parse import quote

import dash
from dash import dcc, html, Input, Output

import odatix.gui.ui_components as ui
import odatix.lib.eda_tools as eda_tools
import odatix.gui.navigation as navigation
import odatix.components.workspace as workspace
from odatix.gui.icons import icon
from odatix.lib.settings import OdatixSettings
from odatix.gui.utils import get_key_from_url

page_path = "/choose_eda_tool"

dash.register_page(
    __name__,
    path=page_path,
    title='Odatix - Choose EDA Tool',
    name='choose_eda_tool',
    order=9,
)

######################################
# UI Components
######################################

padding = 20

# Fallback icon used when a tool.yml does not define an "icon" key.
DEFAULT_TOOL_ICON = "assets/icons/workflow.png"


def is_builtin_tool(tool):
    """True if the tool is defined under the built-in EDA tools directory. A
    workspace tool.yml that only overrides or adds to a built-in tool does not
    make it a workspace tool: it stays built-in, with what the workspace adds."""
    builtin_root = os.path.realpath(OdatixSettings.odatix_eda_tools_path)
    return any(
        os.path.realpath(tool_dir).startswith(builtin_root + os.sep)
        for tool_dir in eda_tools.get_tool_dirs(tool)
    )


def run_link(job_type, tool, flow=None, until=None):
    """Link to the job settings page for a complete selection."""
    link = f"/run_jobs?type={quote(job_type)}&tool={quote(tool)}"
    if flow:
        link += f"&flow={quote(flow)}"
    if until:
        link += f"&until={quote(until)}"
    return link


def tool_head(tool, meta):
    """Logo, name and description, the part every tool card starts with."""
    icon_path = meta.get("icon") if isinstance(meta.get("icon"), str) else None
    description = meta.get("description", "") if isinstance(meta.get("description"), str) else ""

    children = [
        html.Img(src=icon_path or DEFAULT_TOOL_ICON, className="odx-tool-img"),
        html.Div(eda_tools.get_tool_label(tool), className="odx-tool-name"),
    ]
    if description:
        children.append(html.Div(description, className="odx-tool-desc"))
    return html.Div(children, className="odx-tool-head")


def step_overlay(job_type, tool, flow, steps, default_step=None):
    """
    Steps of a flow, as an ordered chain of "run up to here" buttons.

    Stopping early is not throwing work away: the steps a job has done are
    tracked, so a later run picks up at the first one left to do. This is how a
    bitstream ends up generated only for the implementations worth it.

    Where a run stops is a refinement of running the flow, not a question the
    page has to ask upfront: the buttons stay out of the card and appear beside
    it on hover. The step a flow stops at when nothing is asked for is marked,
    since that is what the flow button itself does.
    """
    return html.Div(
        html.Div(
            [html.Div("Run up to", className="odx-steps-title")]
            + [
                dcc.Link(
                    children=[
                        html.Span(str(index + 1), className="odx-step-index"),
                        html.Span(step, className="odx-step-name"),
                        html.Span("(default)", className="odx-step-default") if step == default_step else None,
                    ],
                    # Every button says where it stops, the last one included: not
                    # saying it would mean "wherever the flow stops by default".
                    href=run_link(job_type, tool, flow, step),
                    className="odx-step" + (" default" if step == default_step else ""),
                )
                for index, step in enumerate(steps)
            ],
            className="odx-steps",
        ),
        # Wrapper rather than the panel itself: its padding is the gap the
        # pointer crosses to reach the panel without leaving the hover.
        className="odx-steps-pop",
    )


def custom_flow_names(job_type, tool):
    """
    Flows of a built-in tool the workspace added on top of the ones Odatix
    ships. Empty for a workspace tool: nothing there was "added", the whole tool
    is the workspace's, so nothing needs telling apart.
    """
    if not is_builtin_tool(tool):
        return frozenset()
    builtin = eda_tools.list_flows(tool, job_type=job_type, settings=workspace.load_builtin_tool_settings(tool))
    return frozenset(
        name for name in eda_tools.list_flows(tool, job_type=job_type) if name not in builtin
    )


def flow_entry(job_type, tool, flow, single_flow=False, custom=False):
    """
    One flow of a tool: a button running it, plus, when it is split into steps,
    an overlay of stopping points shown on hover.

    "custom" marks a flow the workspace added to a built-in tool: it runs like
    any other, but where it comes from is worth seeing next to the flows Odatix
    ships.
    """
    steps = eda_tools.get_flow_step_names(tool, flow=flow["name"], job_type=job_type)
    default_step = eda_tools.get_default_step(tool, flow=flow["name"], job_type=job_type)
    label = "Run" if single_flow else flow["label"]

    button = dcc.Link(
        children=[
            html.Span(label, className="odx-flow-name"),
            ui.badge("custom", className="odx-flow-custom-badge") if custom else None,
            html.Span("→", className="odx-flow-go"),
        ],
        # Running the flow means running it up to where it stops by default.
        href=run_link(job_type, tool, flow["name"], default_step),
        className="odx-flow",
        # What a flow does is a sentence, not a chip: keep it out of the
        # card and one hover away.
        title=flow["description"] or None,
    )

    if not steps:
        return button

    button.className = "odx-flow has-steps"
    return html.Div(
        children=[button, step_overlay(job_type, tool, flow["name"], steps, default_step=default_step)],
        className="odx-flow-block",
    )


def tool_settings_button(tool):
    """
    Way out of the page for the tool itself: its commands, and the flows it
    offers here. A sibling of the card rather than a child, because a card with
    a single flow is one big link and a link cannot hold another one.
    """
    return dcc.Link(
        children=icon("gear", className="icon", width="17px", height="17px"),
        href=f"/tool_editor?tool={quote(tool)}",
        className="odx-tool-gear",
        title=f"Edit {tool}",
    )


# Rows of buttons a card shows before it is widened rather than lengthened, and
# the most columns it may take (past three, cards stop fitting side by side).
MAX_FLOW_ROWS = 10
MAX_FLOW_COLUMNS = 3


def flow_columns(flows):
    """
    How many columns of flows a card gets, and so how wide it is.

    Every flow is one button, steps or not: the steps live in an overlay and
    cost the card no height. Once the buttons exceed what reads comfortably
    stacked, they spread sideways instead of the card running off the page.
    """
    return min(MAX_FLOW_COLUMNS, max(1, -(-len(flows) // MAX_FLOW_ROWS)))


def tool_card(job_type, tool):
    """
    Card of a single tool: its identity, then whatever it leaves to choose.

    A tool with a single one shot flow has nothing to choose, so the whole card
    is the link to the job settings rather than a card holding a lone button.
    """
    meta = eda_tools.load_tool_settings(tool)
    flows = eda_tools.list_flows(tool, job_type=job_type)

    custom_flows = custom_flow_names(job_type, tool)

    only_flow = next(iter(flows.values()), None) if len(flows) == 1 else None
    if only_flow and not eda_tools.get_flow_step_names(tool, flow=only_flow["name"], job_type=job_type):
        card = dcc.Link(
            children=tool_head(tool, meta),
            href=run_link(job_type, tool, only_flow["name"]),
            className="odx-tool-card single",
        )
    else:
        card = html.Div(
            children=[
                tool_head(tool, meta),
                html.Div(
                    [
                        flow_entry(
                            job_type,
                            tool,
                            flow,
                            single_flow=len(flows) == 1,
                            custom=flow["name"] in custom_flows,
                        )
                        for flow in flows.values()
                    ],
                    className="odx-tool-flows",
                ),
            ],
            className="odx-tool-card",
        )

    return html.Div(
        [card, tool_settings_button(tool)],
        className="odx-tool-card-wrap",
        # The card width and its flow layout both follow from this: the css
        # turns a column count into a width.
        style={"--odx-tool-cols": str(flow_columns(flows))},
    )


def get_tool_cards(job_type):
    """
    One card per discovered eda tool that supports the requested job type, split
    into workspace tools and built-in tools (mirroring the /tools page). Card
    label / description / icon come from the optional "label", "description" and
    "icon" keys of the tool's tool.yml.
    """
    workspace_cards = []
    builtin_cards = []
    for tool in eda_tools.tools_supporting(job_type):
        card = tool_card(job_type, tool)
        (builtin_cards if is_builtin_tool(tool) else workspace_cards).append(card)
    return workspace_cards, builtin_cards


def get_layout(job_type):
    if not job_type:
        return [ui.page_header("Select an EDA Tool", "No job type selected.", back_link="/choose_job_type")]

    workspace_cards, builtin_cards = get_tool_cards(job_type)

    if not workspace_cards and not builtin_cards:
        content = [ui.empty_state("No eda tool can run this job type.")]
    else:
        content = []
        if workspace_cards:
            content.append(html.Div(workspace_cards, className="odx-tool-grid"))
        if builtin_cards:
            if workspace_cards:
                content.append(
                    html.Div(
                        html.H2("Built-in tools", id="choose-eda-tool-builtin-title"),
                        className="odx-section-head odx-choose-subhead",
                    )
                )
            content.append(html.Div(builtin_cards, className="odx-tool-grid"))

    return [
        ui.page_header(
            "Select an EDA Tool",
            "Choose the tool to run this job with, and how it should run.",
            back_link="/choose_job_type",
        ),
        html.Div(
            content,
            id=f"{__name__}-content",
            style={
                "display": "flex",
                "flexDirection": "column",
                "paddingBottom": f"{padding}px",
            },
        ),
    ]


######################################
# Callbacks
######################################

@dash.callback(
    Output("run_jobs_tool-page-content", "children"),
    Input("url", "search"),
    prevent_initial_call=False,
)
def update_layout(search):
    return get_layout(get_key_from_url(search, "type"))


######################################
# Layout
######################################

layout = html.Div(
    children=[
        dcc.Location(id="url", refresh=False),
        html.Div(
            id="run_jobs_tool-page-content"
        ),
    ],
    id="run_jobs_tool-page",
    className="page-content",
    style={
        "width": "100%",
        "minHeight": f"calc(100vh - {navigation.top_bar_height})",
        "display": "flex",
        "flexDirection": "column",
        "justifyContent": "flex-start",
        "alignItems": "stretch",
    }
)
