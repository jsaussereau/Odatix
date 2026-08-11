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
The variables Odatix itself substitutes in the commands of an editor.

They are the counterpart of the variables the user declares: a command field
highlights both, in different colors, and each editor shows the list of the
built-in ones it accepts right next to the fields using them.

Each context lists what the runner replacing its commands defines:
  - "tool"       : odatix.lib.variables.replace_variables, plus the step tokens
                   resolved by odatix.components.synthesis_common
  - "simulation" : run_simulations.build_simulation_command_substitutions
  - "workflow"   : run_workflow._build_workflow_command_substitutions

Keep these lists in step with those functions: they are what the editor
promises the user.
"""

import json

from dash import html

import odatix.gui.ui_components as ui

# Descriptions are shown both in the list and in the hover tooltip of a token.
BUILTIN_VARIABLES = {
    "tool": [
        ("odatix_path", "Odatix installation directory."),
        ("eda_tools_path", "Directory holding the EDA tool definitions."),
        ("tool_path", "This tool's definition directory."),
        ("work_path", "The job's work directory."),
        ("tool_install_path", "Installation directory of the tool, from the target file."),
        ("script_path", "The job's script directory."),
        ("log_path", "The job's log directory."),
        ("rtl_path", "The job's RTL directory, holding the copied sources."),
        ("report_path", "The job's report directory."),
        ("result_path", "The job's result directory."),
        ("architecture", "Design being run, configuration included."),
        ("target", "Target this job runs on."),
        ("tool", "Name of this tool."),
        ("clock_signal", "Clock signal of the design being run."),
        ("top_level_module", "Top level module of the design being run."),
        ("lib_name", "Library name used by the flow."),
        ("source_work_path", "Place & route jobs only: work directory of the synthesis it starts from."),
        ("source_tool", "Place & route jobs only: tool the synthesis it starts from ran with."),
        ("first_step", "Steps only: the first step this process runs."),
        ("last_step", "Steps only: the last step this process runs."),
        ("steps", "Steps only: every step this process runs, joined with \"-\"."),
    ],
    "simulation": [
        ("simulation", "Name of this simulation."),
        ("architecture", "Design under test."),
        ("configuration", "Configuration under test."),
        ("arch_full", "Full name of the variant, parameter domains included."),
        ("top_level_module", "Top level module of the design under test."),
        ("clock_signal", "Its clock signal."),
        ("work_path", "The simulation's work directory."),
        ("rtl_path", "Directory holding the copied RTL."),
        ("log_path", "Directory logs are expected in."),
        ("script_path", "The simulation's script directory."),
        ("sim_path", "This simulation's definition directory."),
        ("design_path", "Source directory of the design under test."),
        ("odatix_path", "Odatix installation directory."),
    ],
    "workflow": [
        ("workflow", "Name of this workflow."),
        ("configuration", "Configuration being run."),
        ("workflow_full", "Full name of the variant, parameter domains included."),
        ("work_path", "The workflow's work directory."),
        ("log_path", "Directory logs are expected in."),
        ("workflow_path", "This workflow's definition directory."),
        ("source_path", "Directory the workflow's sources are copied from."),
        ("odatix_path", "Odatix installation directory."),
    ],
}

# Names that still work but are no longer offered: they were renamed to match
# the ones of the other contexts. The highlighter knows them so an existing
# command does not light up as an unknown variable, the lists do not show them
# so nothing new is written with them.
DEPRECATED_VARIABLES = {
    "simulation": [
        ("rtl_dir", "Deprecated: use ${rtl_path} instead."),
        ("log_dir", "Deprecated: use ${log_path} instead."),
        ("odatix_dir", "Deprecated: use ${odatix_path} instead."),
    ],
}

# What a command can reference besides the built-in names: names the user
# chose, so only their shape can be listed. Same colors as in the fields, hence
# the highlighter class of each one.
EXTRA_VARIABLES = {
    "simulation": [
        ("<param_domain>", "Configuration value of each parameter domain of the design under test.", "wf-hl-domain"),
    ],
    "workflow": [
        ("<variable>", "Value of each variable defined below, for this configuration.", "wf-hl-var"),
        ("<workflow>", "This workflow's own configuration value, under its name.", "wf-hl-domain"),
        ("<param_domain>", "Configuration value of each of its parameter domains.", "wf-hl-domain"),
    ],
}

# How a context writes its variables, used for the examples of the list.
_SYNTAX = {
    "tool": "$name",
    "simulation": "${name}",
    "workflow": "${name}",
}

_INTRO = {
    "tool": "Odatix replaces these tokens in every command of every task of this tool:",
    "simulation": "Odatix replaces these tokens in every command of every task of this simulation:",
    "workflow": "Odatix replaces these tokens in every command of every task of this workflow:"
}


def names(context):
    """The built-in variable names of a context, without their description."""
    return [name for name, _description in BUILTIN_VARIABLES.get(context, [])]


def descriptions(context):
    """
    {name: description} of the variables a command of this context accepts,
    deprecated ones included: it is what the highlighter recognizes, and a
    command written before a rename must still be read as valid.
    """
    variables = list(BUILTIN_VARIABLES.get(context, [])) + list(DEPRECATED_VARIABLES.get(context, []))
    return {name: description for name, description in variables}


def token(context, name):
    """How `name` is written in a command of this context."""
    return _SYNTAX.get(context, "${name}").replace("name", name)


def highlight_data(context, id="builtin-variables-data", declares_variables=False):
    """
    The built-in variables, handed to the command highlighter.

    Read straight from the DOM by assets/variable_highlight.js rather than
    pushed by a clientside callback: they are static per page, so the page
    declaring them is all the highlighter needs.

    `declares_variables` tells the highlighter this page pushes its own variable
    and parameter domain names (through a clientside callback, as the workflow
    and architecture editors do). A page that does not must say so: those names
    live in window globals, which would otherwise still hold what the editor
    visited before this one had put there.
    """
    attributes = {"data-odatix-hl-builtins": json.dumps(descriptions(context))}
    if not declares_variables:
        attributes["data-odatix-hl-no-globals"] = "1"
    return html.Div(id=id, style={"display": "none"}, **attributes)


def variable_list(context, id=None):
    """
    The list of the variables usable in the commands of this context, in the
    color the highlighter gives them, so what is read here is recognizable in
    the fields above.

    Folded away behind a discreet button of the section title, dropping down
    over the page when opened: it is a reminder one comes looking for, not
    something to scroll past on every visit. A <details> element rather than a
    callback, since nothing but the browser needs to know it is open.
    """
    # The user's own names first: they are what a command is usually written
    # around, and the built-in ones are the fallback one comes checking.
    items = [(name, description, css) for name, description, css in EXTRA_VARIABLES.get(context, [])]
    items += [(name, description, "wf-hl-builtin") for name, description in BUILTIN_VARIABLES.get(context, [])]

    heading = "Variables usable in commands"
    children = [html.P(_INTRO.get(context, ""), className="odx-varlist-intro")]

    if items:
        children.append(
            html.Div(
                children=[
                    html.Div(
                        children=[
                            html.Code(token(context, name), className="wf-hl-token " + css),
                            html.Span(description, className="odx-varlist-desc"),
                        ],
                        className="odx-varlist-item",
                    )
                    for name, description, css in items
                ],
                className="odx-varlist-items",
            )
        )

    kwargs = {"id": id} if id is not None else {}
    return html.Details(
        children=[
            # No `title`: the native tooltip would cover the very panel it opens.
            html.Summary(
                children=[
                    html.Span("$", className="odx-varlist-sigil"),
                    html.Span("Variables", className="odx-varlist-label"),
                    html.Span(className="odx-varlist-chevron"),
                ],
                className="odx-varlist-summary",
            ),
            html.Div(
                children=[
                    html.Div(html.H4(heading), className="odx-varlist-title")
                ] + children,
                className="odx-varlist",
            ),
        ],
        className="odx-varlist-panel",
        **kwargs,
    )
