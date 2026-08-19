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
Clean page (/clean).

Edits the workspace "clean.yml" (see odatix.workspace.clean) and runs the clean
it describes -- the same list, and the same removal, as "odatix clean".

The file holds one thing: the paths and glob patterns to remove, resolved
against the workspace directory. Each tool Odatix runs leaves its own litter
behind, so the list is what says which of it is safe to throw away. It is edited
here as one pattern per line, which is how it reads in the file.

Removing files cannot be undone, so the run is deliberately not a single click:
it asks for a confirmation, it runs on the patterns currently shown (what you
see is what gets removed, saved or not), and it reports every path it removed,
refused or failed to remove.
"""

import os

import dash
from dash import html, dcc, Input, Output, State, ctx

from odatix.gui.icons import icon
from odatix.gui.utils import get_workspace
import odatix.gui.ui_components as ui
import odatix.gui.navigation as navigation
from odatix.gui.page_scope import page_callback, scoped

# Scope anchoring the callbacks below: they are dispatched only on the pages
# embedding the matching anchor store (see odatix.gui.page_scope).
PAGE_SCOPE = "clean"

page_path = "/clean"

dash.register_page(
    __name__,
    path=page_path,
    title="Odatix - Clean",
    name="Clean",
    order=11,
)

PAGE_TOOLTIP = (
    "The paths removed by a clean, one per line. Glob patterns are accepted, and every path is "
    "resolved against the workspace directory."
)

FORCE_TOOLTIP = (
    'Remove even the patterns that would take the whole workspace with them ("*", ".", "/", ...). '
    "Without it, a clean refuses them and says so. Use at your own risks."
)

PATTERNS_TOOLTIP = (
    'One path or glob pattern per line, e.g. "vivado*.log" or ".Xil". Lines are kept in this order '
    "in the file, and blank lines are dropped."
)


######################################
# Value <-> text conversions
######################################

def join_patterns(patterns):
    """The pattern list as the textarea holds it: one per line."""
    return "\n".join(str(pattern) for pattern in (patterns or []))


def split_patterns(text):
    """The textarea content back into a pattern list, blank lines dropped."""
    return [line.strip() for line in str(text or "").splitlines() if line.strip() != ""]


def display_path(path, root):
    """
    A removed path as the page shows it: relative to the workspace when it lies
    inside it, absolute otherwise. What a clean touched outside the workspace is
    exactly what a user needs to see in full.
    """
    try:
        relative = os.path.relpath(path, os.path.realpath(root or "."))
    except ValueError:
        return path
    if relative.startswith(os.pardir):
        return path
    return relative


######################################
# UI Components
######################################

def clean_form(patterns_text, force=False):
    return ui.grid(
        children=[
            ui.panel(body=[
                ui.caption("Paths to remove"),
                ui.form_area(
                    label="Patterns",
                    id="clean-remove-list",
                    value=patterns_text,
                    placeholder="vivado*.log\n.Xil\n*.jou",
                    tooltip=PATTERNS_TOOLTIP,
                ),
            ]),
            ui.panel(body=[
                ui.caption("Run"),
                ui.switch_row(
                    label="Force dangerous patterns",
                    id="clean-force",
                    checked=force,
                    tooltip=FORCE_TOOLTIP,
                ),
                html.Div(
                    "A clean runs on the patterns shown here, saved or not.",
                    className="odx-status",
                    style={"marginTop": "8px"},
                ),
            ]),
        ],
    )


def path_list(title, paths, color, root, details=None):
    """One group of the run report: a badge saying how many, then the paths."""
    if not paths:
        return None
    lines = []
    for index, path in enumerate(paths):
        line = [html.Span(display_path(path, root), className="odx-code")]
        if details is not None and details[index]:
            line.append(html.Div(details[index], className="odx-status error"))
        lines.append(html.Div(line, className="odx-preview-item"))
    return ui.panel(
        title=html.Div([html.Span(title), ui.badge(str(len(paths)), color=color)],
                       style={"display": "flex", "alignItems": "center", "gap": "8px"}),
        body=lines,
        body_className="scroll tall",
    )


def result_view(result, root):
    """The report of one clean run."""
    if result is None:
        return ui.empty_state("Nothing cleaned yet.")

    nothing_happened = not (result.removed or result.skipped or result.errors)

    stats = html.Div(
        children=[
            ui.stat(len(result.removed), "removed", className="accent"),
            ui.stat(len(result.skipped), "refused", className="muted" if not result.skipped else ""),
            ui.stat(len(result.errors), "failed", className="muted" if not result.errors else ""),
            ui.stat(len(result.unmatched), "matched nothing", className="muted"),
        ],
        style={"display": "flex", "flexWrap": "wrap", "gap": "12px", "marginBottom": "12px"},
    )

    panels = [
        path_list(
            "Removed", [removal.path for removal in result.removed], "success", root,
        ),
        path_list(
            "Refused", [removal.path for removal in result.skipped], "warning", root,
            details=[removal.message for removal in result.skipped],
        ),
        path_list(
            "Failed", [removal.path for removal in result.errors], "caution", root,
            details=[removal.message for removal in result.errors],
        ),
    ]
    panels = [panel for panel in panels if panel is not None]

    if nothing_happened:
        panels.append(ui.empty_state("Nothing to remove: the workspace is already clean."))

    return html.Div([stats, ui.grid(panels)] if panels else [stats])


######################################
# Callbacks
######################################

@dash.callback(
    Output("clean-form-container", "children"),
    Output("clean-initial", "data"),
    Output("clean-file-path", "children"),
    Input(f"url_{page_path}", "pathname"),
    State("odatix-settings", "data"),
)
def init_page(page, odatix_settings):
    if page != page_path:
        return dash.no_update, dash.no_update, dash.no_update

    settings = get_workspace(odatix_settings).clean_settings
    patterns = list(settings.remove_list)
    note = 'Removed paths are read from "{0}"{1}.'.format(
        settings.path, "" if settings.exists else " (which does not exist yet)"
    )
    return clean_form(join_patterns(patterns)), patterns, note


@dash.callback(
    Output({"page": page_path, "action": "save-all"}, "className"),
    Output({"page": page_path, "action": "save-all"}, "data-tooltip"),
    Output("clean-saved", "data"),
    Input({"page": page_path, "action": "save-all"}, "n_clicks"),
    Input("clean-remove-list", "value"),
    State(f"url_{page_path}", "pathname"),
    State("clean-initial", "data"),
    State("clean-saved", "data"),
    State("odatix-settings", "data"),
    prevent_initial_call=True,
)
def save_and_status(n_clicks, patterns_text, page, initial, saved, odatix_settings):
    if page != page_path:
        return dash.no_update, dash.no_update, dash.no_update

    disabled = ("color-button disabled icon-button tooltip delay bottom small", "Nothing to save")
    warning = ("color-button warning icon-button tooltip bottom small", "Unsaved changes!")
    error = "color-button error-status icon-button tooltip bottom small"

    current = split_patterns(patterns_text)
    reference = saved if isinstance(saved, list) else initial

    if ctx.triggered_id == {"page": page_path, "action": "save-all"}:
        try:
            settings = get_workspace(odatix_settings).clean_settings
            settings.remove_list = current
            settings.save()
            return disabled[0], disabled[1], current
        except Exception:
            return error, "Failed to save...", dash.no_update

    if not isinstance(reference, list) or current != reference:
        return warning[0], warning[1], dash.no_update

    return disabled[0], disabled[1], dash.no_update


@page_callback(PAGE_SCOPE,
    Output("clean-confirm", "displayed"),
    Output("clean-confirm", "message"),
    Input({"page": page_path, "action": "run"}, "n_clicks"),
    State("clean-remove-list", "value"),
    State("clean-force", "value"),
    prevent_initial_call=True,
)
def ask_confirmation(n_clicks, patterns_text, force):
    """Removing files cannot be undone: say what is about to happen first."""
    if not n_clicks:
        return dash.no_update, dash.no_update

    patterns = split_patterns(patterns_text)
    if not patterns:
        return False, ""

    message = "Remove everything matched by these {0} pattern(s)?\n\n{1}".format(
        len(patterns), "\n".join(patterns)
    )
    if force:
        message += "\n\nDangerous patterns will NOT be refused: force is on."
    return True, message


@dash.callback(
    Output("clean-results", "children"),
    Output("clean-run-status", "children"),
    Output("clean-run-status", "className"),
    Input("clean-confirm", "submit_n_clicks"),
    State("clean-remove-list", "value"),
    State("clean-force", "value"),
    State("odatix-settings", "data"),
    prevent_initial_call=True,
)
def run_clean(submit_n_clicks, patterns_text, force, odatix_settings):
    if not submit_n_clicks:
        return dash.no_update, dash.no_update, dash.no_update

    workspace = get_workspace(odatix_settings)
    settings = workspace.clean_settings
    # Run on what the page shows, not on what the file holds: the patterns the
    # confirmation listed are the ones that must be removed, saved or not.
    settings.remove_list = split_patterns(patterns_text)

    try:
        result = settings.run(force=bool(force))
    except Exception as error:
        return dash.no_update, "Clean failed: " + str(error), "odx-status error"

    return (
        result_view(result, workspace.root),
        result.summary(),
        "odx-status" if result.ok else "odx-status error",
    )


######################################
# Layout
######################################

title_buttons = html.Div(
    children=[
        ui.icon_button(
            id={"page": page_path, "action": "run"},
            icon=icon("clean", className="icon"),
            text="Clean",
            tooltip="Remove everything the patterns match",
            tooltip_options="bottom auto",
            color="caution",
        ),
        ui.save_button(
            id={"page": page_path, "action": "save-all"},
            tooltip="Save all changes",
            disabled=True,
        ),
    ],
    className="odx-header-actions",
)

layout = html.Div(
    children=[
        dcc.Location(id=f"url_{page_path}"),
        ui.page_bar(
            "Clean",
            actions=title_buttons,
            back_link="/workspace",
            extra=html.Div(
                children=[
                    html.Div(id="clean-file-path"),
                    html.Div(id="clean-run-status", className="odx-status"),
                ],
                className="odx-summary",
            ),
        ),
        html.Div(id="clean-form-container"),
        ui.section("Last clean", html.Div(id="clean-results", children=ui.empty_state("Nothing cleaned yet."))),
        dcc.ConfirmDialog(id="clean-confirm", message=""),
        dcc.Store(id="clean-initial", data=None),
        dcc.Store(id="clean-saved", data=None),
    ],
    className="page-content odx-page",
    style={
        "display": "flex",
        "flexDirection": "column",
        "min-height": f"calc(100vh - {navigation.top_bar_height})",
    },
)

# Anchor of PAGE_SCOPE: makes this page the only one dispatching its callbacks.
layout = scoped(PAGE_SCOPE, layout)
