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
Shared task editor, used by the Workflow Editor and the Simulation Editor.

A workflow and a simulation describe what they run the same way: a list of
tasks, each with a name, commands, a fallback, dependencies, a working path and
the platforms it applies to (see odatix.components.task_common). Both pages
render the same task cards and read them back into the same list; only the id
namespace differs ("wf" or "sim"), so every component id is built from a
``prefix``. A key added to a task is added here, once, for both pages.
"""

import dash
from dash import html, dcc

import odatix.gui.ui_components as ui
from odatix.gui.css_helper import Style
from odatix.gui.icons import icon

#: The fields of a task card, in the order the pages receive their values.
TASK_FIELDS = ("name", "dependencies", "commands", "on_failure_commands", "path", "platforms")

#: Fields holding one command per line.
_COMMAND_FIELDS = ("commands", "on_failure_commands")
#: Fields holding a comma separated list.
_LIST_FIELDS = ("dependencies", "platforms")


def field_id(prefix, field, name):
    return {"type": f"{prefix}-task-field-{field}", "name": name}


def task_field_dependencies(prefix, dependency):
    """
    The callback dependencies (``Input`` or ``State``) reading every task field,
    in :data:`TASK_FIELDS` order.
    """
    return [dependency({"type": f"{prefix}-task-field-{field}", "name": dash.ALL}, "value") for field in TASK_FIELDS]


######################################
# Between a task and its card
######################################

def _join_list(value, separator):
    if isinstance(value, list):
        return separator.join(str(item) for item in value if str(item).strip())
    if isinstance(value, str):
        return value
    return ""


def task_values(task):
    """What the fields of the card of one task show, as text."""
    task = task if isinstance(task, dict) else {}
    values = {
        "dependencies": _join_list(task.get("dependencies", []), ", "),
        "platforms": _join_list(task.get("platforms", ""), ", "),
        "path": str(task.get("path", "")) if task.get("path") is not None else "",
    }
    for field in _COMMAND_FIELDS:
        values[field] = _join_list(task.get(field, []), "\n")
    return values


def _split(text, separator=None):
    text = "" if text is None else str(text)
    parts = text.splitlines() if separator is None else text.split(separator)
    return [part.strip() for part in parts if part.strip() != ""]


def build_tasks_list(*field_values):
    """
    The task list the cards describe.

    Args:
        *field_values: one list of values per field of :data:`TASK_FIELDS`, in
            that order, as the pattern matching callback dependencies give them.
    """
    columns = dict(zip(TASK_FIELDS, field_values))
    names = columns.get("name") or []

    def value(field, idx):
        values = columns.get(field) or []
        return values[idx] if idx < len(values) else ""

    tasks = []
    for idx in range(len(names)):
        name = str(names[idx]).strip() if names[idx] is not None else ""
        if name == "":
            continue

        task = {"name": name, "commands": _split(value("commands", idx))}
        dependencies = _split(value("dependencies", idx), ",")
        if dependencies:
            task["dependencies"] = dependencies
        on_failure = _split(value("on_failure_commands", idx))
        if on_failure:
            task["on_failure_commands"] = on_failure
        path = str(value("path", idx) or "").strip()
        if path:
            task["path"] = path
        platforms = _split(value("platforms", idx), ",")
        if len(platforms) == 1:
            task["platforms"] = platforms[0]
        elif len(platforms) > 1:
            task["platforms"] = platforms
        tasks.append(task)
    return tasks


def card_values(field_values, idx):
    """The values of the card at ``idx``, to duplicate it."""
    values = {}
    for field, column in zip(TASK_FIELDS, field_values):
        if field != "name":
            column = column or []
            values[field] = column[idx] if idx < len(column) else ""
    return values


######################################
# Components
######################################

_LABEL_STYLE = {"fontWeight": "bold", "fontSize": "1em"}
_INPUT_STYLE = {"width": "100%", "marginBottom": "8px"}
_COMMANDS_STYLE = {
    "width": "100%",
    "minHeight": "110px",
    "resize": "vertical",
    "fontFamily": "monospace",
    "fontWeight": "500",
    "marginBottom": "8px",
    "boxSizing": "border-box",
}


def _commands_field(prefix, field, name, value, min_height=None):
    style = dict(_COMMANDS_STYLE)
    if min_height:
        style["minHeight"] = min_height
    return dcc.Textarea(
        value=value,
        id=field_id(prefix, field, name),
        className="auto-resize-textarea odatix-command-field",
        style=style,
    )


def task_card(prefix, name="main", values=None, main_is_deletable=False):
    """
    The card of one task.

    Args:
        prefix (str): the id namespace of the page ("wf", "sim").
        values (dict): what its fields show, by field (see :func:`task_values`).
        main_is_deletable (bool): whether the "main" task can be deleted. A
            workflow always has one; a simulation may have no task at all.
    """
    values = values or {}
    is_main = str(name).strip() == "main"
    # A fallback is worth seeing without having to look for it.
    extra_open = bool(str(values.get("on_failure_commands", "") or "").strip())
    return html.Div([
        html.Div(
            children=[
                dcc.Input(
                    value=name,
                    type="text",
                    id=field_id(prefix, "name", name),
                    className="title-input",
                    disabled=is_main,
                    style={
                        "width": "100%",
                        "marginLeft": "5px",
                        "marginRight": "5px",
                        "marginTop": "-5px",
                        "marginBottom": "2px",
                        "fontWeight": "bold",
                        "fontSize": "1.1em",
                        "height": "10px",
                        "textAlign": "center",
                    },
                ),
                html.Label("Dependencies", style=_LABEL_STYLE),
                dcc.Input(
                    value=values.get("dependencies", ""),
                    type="text",
                    placeholder="task_a, task_b",
                    id=field_id(prefix, "dependencies", name),
                    className="value-input",
                    style=_INPUT_STYLE,
                ),
                html.Label("Commands (one per line)", style=_LABEL_STYLE),
                _commands_field(prefix, "commands", name, values.get("commands", "")),
                html.Div(
                    children=[
                        html.Div([
                            html.Label("On failure (optional)", style=_LABEL_STYLE),
                            ui.tooltip_icon(
                                "Commands run, one per line, when one of the commands above fails. "
                                "The task then succeeds if they do."
                            ),
                        ], style={"display": "flex", "alignItems": "center", "gap": "4px"}),
                        _commands_field(prefix, "on_failure_commands", name, values.get("on_failure_commands", ""), min_height="60px"),
                        html.Label("Path (optional)", style=_LABEL_STYLE),
                        dcc.Input(
                            value=values.get("path", ""),
                            type="text",
                            id=field_id(prefix, "path", name),
                            className="value-input",
                            style=_INPUT_STYLE,
                        ),
                        html.Label("Platforms (optional)", style=_LABEL_STYLE),
                        dcc.Input(
                            value=values.get("platforms", ""),
                            type="text",
                            placeholder="linux, win32",
                            id=field_id(prefix, "platforms", name),
                            className="value-input",
                            style=_INPUT_STYLE,
                        ),
                    ],
                    id={"type": f"{prefix}-more-task-field-div", "name": name},
                    className="expandable-area",
                    style=Style.visible if extra_open else Style.hidden,
                ),
            ],
            style={"width": "100%"}
        ),
        html.Div([
            html.Div([
                ui.icon_button(
                    icon=icon(
                        "more",
                        className="icon normal rotate" + (" rotated" if extra_open else ""),
                        id={"type": f"{prefix}-more-task-fields-icon", "name": name},
                    ),
                    color="default",
                    id={"type": f"{prefix}-more-fields-task", "name": name},
                    tooltip="Show/hide extra fields",
                    tooltip_options="bottom small",
                )
            ], id={"type": f"{prefix}-more-fields-task-div", "name": name}, style={"display": "flex", "alignItems": "center"}),
            html.Div([
                ui.duplicate_button(id={"type": f"{prefix}-duplicate-task", "name": name}),
                ui.delete_button(id={"type": f"{prefix}-delete-task", "name": name})
                if main_is_deletable or not is_main else html.Div(),
            ], style={"display": "flex", "flexDirection": "horizontal", "alignItems": "center", "gap": "5px"}),
        ], style={
            "marginTop": "8px",
            "display": "flex",
            "flexDirection": "row",
            "width": "100%",
            "justifyContent": "space-between",
        }),
    ],
    className="tile config",
    id={"type": f"{prefix}-task-card", "name": name},
)


def cards_from_tasks(prefix, tasks, main_is_deletable=False):
    """The cards of a task list, without the page's own "add" card."""
    cards = []
    for idx, task in enumerate(tasks if isinstance(tasks, list) else []):
        if not isinstance(task, dict):
            continue
        name = str(task.get("name", "")).strip() or f"task{idx + 1}"
        cards.append(task_card(prefix, name=name, values=task_values(task), main_is_deletable=main_is_deletable))
    return cards
