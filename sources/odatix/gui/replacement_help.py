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
What parameter replacement is, said once, in the page where it is set up.

The configuration editor asks for a target file and two delimiters before it
says what they are for. This module is the answer: a line folded away at the top
of the page that, once opened, draws what a configuration does to the target
file, and says what the three ways of describing configurations are, and what
several parameter domains buy.

It takes the settings of a domain when it has them, so the drawing can name that
domain's own file and delimiters; the page-wide fold has none and draws the
mechanism with placeholders instead.

Purely presentational: no state, one toggle callback, nothing written anywhere.
"""

import dash
from dash import html, Input, Output

from odatix.gui.icons import icon
import odatix.lib.hard_settings as hard_settings

#: What the diagram shows when the domain has not been set up yet. Not defaults
#: Odatix would use -- just something readable to point at.
PLACEHOLDER_TARGET_FILE = "<target file>"
PLACEHOLDER_START = "// ODATIX_PARAMS_BEGIN"
PLACEHOLDER_STOP = "// ODATIX_PARAMS_END"


def _text(value, placeholder):
    value = "" if value is None else str(value)
    return value if value.strip() else placeholder


def replacement_diagram(settings, domain_name=None):
    """
    The one picture of the mechanism: a configuration on the left, the target
    file on the right, and what the configuration replaces in it.
    """
    target_file = _text(settings.get("param_target_file"), PLACEHOLDER_TARGET_FILE)
    start_delimiter = _text(settings.get("start_delimiter"), PLACEHOLDER_START)
    stop_delimiter = _text(settings.get("stop_delimiter"), PLACEHOLDER_STOP)
    example = "16bit" if not domain_name or domain_name == hard_settings.main_parameter_domain else "16"

    configuration = html.Div(
        children=[
            html.Div(
                children=[
                    html.Span("configuration", className="odx-diagram-kind"),
                    html.Span("{0}.txt".format(example), className="odx-diagram-name"),
                ],
                className="odx-diagram-head",
            ),
            html.Pre("parameter WIDTH = 16;", className="odx-diagram-code content"),
        ],
        className="odx-diagram-box",
    )

    target = html.Div(
        children=[
            html.Div(
                children=[
                    html.Span("target file", className="odx-diagram-kind"),
                    html.Span(target_file, className="odx-diagram-name"),
                ],
                className="odx-diagram-head",
            ),
            html.Pre(
                children=[
                    html.Span("module alu #(\n", className="odx-diagram-dim"),
                    html.Span(start_delimiter + "\n", className="odx-diagram-delimiter"),
                    html.Span("parameter WIDTH = 16;\n", className="odx-diagram-replaced"),
                    html.Span(stop_delimiter + "\n", className="odx-diagram-delimiter"),
                    html.Span(") ( ... );", className="odx-diagram-dim"),
                ],
                className="odx-diagram-code",
            ),
        ],
        className="odx-diagram-box grow",
    )

    return html.Div(
        children=[
            configuration,
            html.Div(
                children=[
                    html.Span("replaces", className="odx-diagram-arrow-label"),
                    html.Span("→", className="odx-diagram-arrow-glyph"),
                ],
                className="odx-diagram-arrow",
            ),
            target,
        ],
        className="odx-diagram",
    )


def _paragraph(title, children):
    return html.Div(
        children=[html.Div(title, className="odx-help-title"), html.P(children, className="odx-help-text")],
        className="odx-help-block",
    )


def help_body(settings, domain_name=None):
    """The diagram and what goes with it."""
    return html.Div(
        children=[
            replacement_diagram(settings, domain_name),
            html.Div(
                children=[
                    _paragraph("What a configuration is", [
                        "A configuration is a piece of text. Before a run, Odatix copies the design and writes that "
                        "text into the target file, in place of everything between the start and the stop delimiter. "
                        "The rest of the file is left untouched, so the delimiters mark the one part of the design "
                        "this domain is allowed to change.",
                    ]),
                    _paragraph("Three ways to describe them", [
                        "Write them by hand, one card each — always possible, whatever else this domain does. ",
                        "Or declare a single variable and let its values name and write the configurations for you. ",
                        "Or, under ", html.B("Advanced"), ", spell out how a configuration is named and what it "
                        "contains, with as many variables as needed. A configuration written by hand always wins "
                        "over the one a rule would produce under the same name.",
                    ]),
                    _paragraph("Why several parameter domains", [
                        "One domain varies one thing, in one place of the design. A second domain replaces its own "
                        "section — another file, or another pair of delimiters in the same file — and Odatix runs "
                        "every combination of the two. Four data widths and three architectures are seven "
                        "configurations to describe, not twelve to write, and each domain stays its own column in "
                        "the results, which is what makes the two effects readable apart.",
                    ]),
                ],
                className="odx-help-blocks",
            ),
        ],
        className="odx-help-body",
    )


def help_section(domain_uuid="page", settings=None, domain_name=None, open=False):
    """
    The folded explanation, as one line above the domains it explains.

    One per page rather than one per domain: it says what the page is, and a
    page saying that once is a page that says it where it is looked for.
    """
    settings = settings or {}
    return html.Div(
        children=[
            html.Div(
                children=[
                    icon("more", className="icon normal rotate rotated" if open else "icon normal rotate",
                         id={"type": "cfg-help-icon", "domain_uuid": domain_uuid}),
                    html.Span("How does parameter replacement work?", className="odx-help-question"),
                ],
                id={"type": "cfg-help-toggle", "domain_uuid": domain_uuid},
                n_clicks=1 if open else 0,
                className="odx-help-header",
            ),
            html.Div(
                help_body(settings, domain_name),
                id={"type": "cfg-help-panel", "domain_uuid": domain_uuid},
                style={} if open else {"display": "none"},
            ),
        ],
        className="odx-help",
    )


@dash.callback(
    Output({"type": "cfg-help-panel", "domain_uuid": dash.ALL}, "style"),
    Output({"type": "cfg-help-icon", "domain_uuid": dash.ALL}, "className"),
    Input({"type": "cfg-help-toggle", "domain_uuid": dash.ALL}, "n_clicks"),
)
def toggle_help(n_clicks):
    """Open the explanation of one domain, leaving the others as they are."""
    styles = []
    classes = []
    for clicks in n_clicks:
        shown = bool(clicks) and clicks % 2 == 1
        styles.append({} if shown else {"display": "none"})
        classes.append("icon normal rotate rotated" if shown else "icon normal rotate")
    return styles, classes
