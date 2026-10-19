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

import yaml
import dash
from dash import html, dcc, Input, Output, State, ctx
from dash.exceptions import PreventUpdate
from typing import Optional

from odatix.gui.icons import icon
from odatix.gui.utils import get_key_from_url, get_workspace
from odatix.gui.css_helper import Style
import odatix.gui.ui_components as ui
import odatix.gui.navigation as navigation
import odatix.gui.builtin_variables as builtin_variables
import odatix.lib.hard_settings as hard_settings
import odatix.gui.variable_editor as ve
import odatix.gui.task_editor as te
from odatix.lib.config_generator import get_variables
from odatix.gui.page_scope import page_callback, page_clientside_callback, scoped
from odatix.workspace.settings import Settings

# Scope anchoring the callbacks below: they are dispatched only on the pages
# embedding the matching anchor store (see odatix.gui.page_scope).
PAGE_SCOPE = "workflow_editor"

# Variable-editor id namespace for this page.
VE_PREFIX = "wf-"
#: Merged into the id of every component of a variable card. The ids of the
#: variable cards and those of the task cards would otherwise have the same
#: keys, and Dash compares every id of an updated part of the page with every
#: other id of the same keys (computePaths): filling the form of a big workflow
#: compared its hundreds of task ids with its thousand variable ids, seconds of
#: work before the page showed anything.
VE_SCOPE = {"row": "variable"}

page_path = "/workflow_editor"

dash.register_page(
    __name__,
    path=page_path,
    title="Odatix - Workflow editor",
    name="Workflow editor",
    order=5,
)


######################################
# Helpers
######################################

def _parse_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        val = value.strip().lower()
        if val in ["yes", "true", "1"]:
            return True
        if val in ["no", "false", "0"]:
            return False
    return default

def _normalize_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [str(v).strip() for v in str(value).split(",") if str(v).strip()]

def normalize_workflow_settings(settings):
    if not isinstance(settings, dict):
        settings = {}

    sources = settings.get("sources", {})
    if not isinstance(sources, dict):
        sources = {}

    progress = settings.get("progress", {})
    if not isinstance(progress, dict):
        progress = {}

    tasks = settings.get("tasks", [])
    if not isinstance(tasks, list):
        tasks = []

    # Variables are declared at the root of the settings file, but are still
    # read from where they used to be declared.
    variables, _legacy = get_variables(settings)

    try:
        vars_copy = {}
        for vname, vcfg in variables.items():
            if not isinstance(vcfg, dict):
                vars_copy[vname] = vcfg
                continue

            # Only keep canonical keys
            v_type = vcfg.get("type")
            v_format = vcfg.get("format") if "format" in vcfg else None
            v_group = vcfg.get("group") if "group" in vcfg else None
            v_unit = vcfg.get("unit") if "unit" in vcfg else None
            vsettings = vcfg.get("settings", {}) if isinstance(vcfg.get("settings", {}), dict) else {}

            # Normalize list elements to strings when present
            if "list" in vsettings and isinstance(vsettings["list"], (list, tuple)):
                vsettings = dict(vsettings)
                vsettings["list"] = [str(x) for x in vsettings["list"]]

            new_vcfg = {"type": v_type, "settings": vsettings}
            if v_format:
                new_vcfg["format"] = v_format
            if v_group:
                new_vcfg["group"] = v_group
            if v_unit is not None and str(v_unit).strip():
                new_vcfg["unit"] = str(v_unit).strip()

            vars_copy[vname] = new_vcfg

        variables = vars_copy
    except Exception:
        pass

    return {
        "sources": {
            "path": sources.get("path", ""),
            "whitelist": _normalize_list(sources.get("whitelist", [])),
            "blacklist": _normalize_list(sources.get("blacklist", [])),
        },
        "use_parameters": _parse_bool(settings.get("use_parameters", True), True),
        "param_target_file": settings.get("param_target_file", ""),
        "start_delimiter": settings.get("start_delimiter", ""),
        "stop_delimiter": settings.get("stop_delimiter", ""),
        "progress": {
            "file": progress.get("file", ""),
            "regex": progress.get("regex", ""),
        },
        # Only what the cards edit: a key they do not show ("phony" before
        # the switch, or any other) must not make the form look edited.
        "tasks": [
            {k: v for k, v in task.items() if k in te.TASK_FIELDS + ("phony",)} if isinstance(task, dict) else task
            for task in tasks
        ],
        "variables": variables,
    }

def format_tasks(tasks):
    if not isinstance(tasks, list) or len(tasks) == 0:
        return ""
    return yaml.safe_dump(tasks, sort_keys=False, default_flow_style=False).strip()

#: The keys of a task the cards of this page edit (the shared fields, and
#: the "Always run" switch).
TASK_MANAGED_KEYS = te.TASK_FIELDS + ("phony",)

def keep_unmanaged_task_keys(tasks, stored_tasks, managed=te.TASK_FIELDS):
    """
    The tasks the cards describe, with what the cards do not edit (not in
    ``managed``) kept as the file has it, each key where the file had it. A
    task is matched to the stored one of the same name, implementations
    sharing a name being matched in order.
    """
    stored_by_name = {}
    for task in stored_tasks if isinstance(stored_tasks, list) else []:
        if isinstance(task, dict):
            stored_by_name.setdefault(str(task.get("name")), []).append(task)
    kept = []
    for task in tasks:
        candidates = stored_by_name.get(str(task.get("name")), [])
        if candidates and isinstance(task, dict):
            task = ve.merge_in_file_order(task, candidates.pop(0), managed)
        kept.append(task)
    return kept

def _plain(value):
    """A settings value with its scalars as text, to compare a file and a form."""
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, bool) or value is None:
        return value
    return str(value)

def same_tasks(tasks, stored_tasks):
    """Whether saving these tasks would write what the file already says."""
    def one(task):
        task = dict(task) if isinstance(task, dict) else {}
        if not isinstance(task.get("platforms", []), list):
            task["platforms"] = [task["platforms"]]
        if task.get("phony", True) is True:
            task.pop("phony", None)
        return _plain(task)
    stored_tasks = stored_tasks if isinstance(stored_tasks, list) else []
    return [one(task) for task in tasks] == [one(task) for task in stored_tasks]

def same_variables(variables, stored_variables):
    """
    Whether saving these variables (as the cards build them) would write what
    the file already says: the file goes through the cards first, a file and
    a form not spelling the same thing identically (see
    variable_editor.normalized_variables).
    """
    stored_variables = stored_variables if isinstance(stored_variables, dict) else {}
    reference = ve.normalized_variables(stored_variables)
    for name, definition in stored_variables.items():
        unit = definition.get("unit") if isinstance(definition, dict) else None
        if name in reference and unit is not None and str(unit).strip():
            reference[name]["unit"] = str(unit).strip()
    return list(_plain(reference).items()) == list(_plain(variables or {}).items())

def wf_build_tasks_list(*field_values, phony=None):
    """
    Build the workflow tasks list from the task card field values (one list per
    field of task_editor.TASK_FIELDS), and the "Always run" switches by task
    name (see task_editor.phony_by_name). A workflow always has its "main" task.
    """
    tasks = te.apply_phony(te.build_tasks_list(*field_values), phony or {})
    if not any(task["name"] == "main" for task in tasks):
        tasks.insert(0, {"name": "main", "commands": []})
    return tasks

def wf_build_variables_dict(
    titles, types, base_vals, from_vals, to_vals, from_2_pow_vals, to_2_pow_vals, from_type_vals, to_type_vals, step_vals, op_vals, list_vals, source_vals, sources_vals, format_vals, group_vals, unit_vals=None
):
    """
    Build a "variables" dict from the variable card field values.
    """
    return ve.build_variables_dict(
        titles, types, base_vals, from_vals, to_vals, from_2_pow_vals, to_2_pow_vals,
        from_type_vals, to_type_vals, step_vals, op_vals, list_vals, source_vals, sources_vals,
        format_vals, group_vals, unit_vals=unit_vals,
    )


######################################
# UI Components
######################################

def workflow_title(workflow_name):
    title_buttons = html.Div(
        children=[
            ui.icon_button(
                id=f"button-open-metric-editor",
                icon=icon("metrics", className="icon blue"),
                text="Edit metrics",
                tooltip="Open the exported metrics editor for this workflow",
                tooltip_options="bottom delay",
                color="default",
                link=f"/metric_editor?workflow={workflow_name}",
                multiline=False,
                width="135px",
            ),
            ui.icon_button(
                id=f"button-open-config-editor",
                icon=icon("edit", className="icon blue"),
                text="Edit configurations",
                tooltip="Open the configuration editor for this workflow",
                tooltip_options="bottom delay",
                color="default",
                link=f"/config_editor?workflow={workflow_name}",
                multiline=False,
                width="175px",
            ),
            ui.save_button(
                id={"page": page_path, "action": "save-all"},
                tooltip="Save all changes",
                disabled=True,
            ),
        ],
        className="inline-flex-buttons",
    )

    return html.Div(
        html.Div(
            children=[
                html.Div(
                    children=[
                        html.Div(
                            children=[
                                dcc.Input(
                                    value=f"{workflow_name}",
                                    type="text",
                                    id="workflow-title",
                                    placeholder="Workflow name...",
                                    className="title-input",
                                    style={"width": "100%", "transform": "translate(-5px, 5px)"},
                                )
                            ],
                            id="workflow-title-container",
                            # The name takes all the room the buttons leave.
                            style={"flex": "1 1 auto", "minWidth": "0"},
                        ),
                        html.Div([title_buttons]),
                    ],
                    className="title-tile-flex",
                    style={
                        "display": "flex",
                        "alignItems": "center",
                        "padding": "0px",
                        "justifyContent": "space-between",
                    },
                ),
                ui.back_button(link="/workflows"),
            ],
            className="tile title",
            style={"position": "relative"},
        ),
        className="card-matrix config",
        style={"marginTop": "0px", "marginBottom": "10px"},
    )

def workflow_form_field(
    label,
    id,
    value="",
    tooltip="",
    placeholder="",
    tooltip_options="secondary",
):
    return html.Div(
        children=[
            html.Label(label),
            ui.tooltip_icon(tooltip, tooltip_options),
            dcc.Input(id=id, value=value, type="text", placeholder=placeholder, style={"width": "100%"}),
        ],
        style={"marginBottom": "12px"},
    )

def workflow_form(settings):
    defval = lambda k, v=None: settings.get(k, v)

    sources = defval("sources", {})
    progress = defval("progress", {})
    use_parameters = True if defval("use_parameters", True) else False

    tiles = [
            html.Div(
                [
                    html.H3("Workflow sources"),
                    workflow_form_field(
                        label="Source path",
                        id="wf-source-path",
                        value=sources.get("path", ""),
                        tooltip="Directory copied in each workflow work directory before running tasks.",
                    ),
                    workflow_form_field(
                        label="Source whitelist",
                        id="wf-source-whitelist",
                        value=", ".join(sources.get("whitelist", [])),
                        placeholder="src/**, scripts/**",
                        tooltip="Optional comma-separated inclusion patterns.",
                    ),
                    workflow_form_field(
                        label="Source blacklist",
                        id="wf-source-blacklist",
                        value=", ".join(sources.get("blacklist", [])),
                        placeholder="*.log, tmp/**",
                        tooltip="Optional comma-separated exclusion patterns.",
                    ),
                ],
                className="tile config",
            ),
            html.Div(
                [
                    html.H3("Parameters replacement"),
                    html.Div(
                        children=[
                            dcc.Checklist(
                                options=[{"label": "Enable parameter replacement", "value": True}],
                                value=[True] if use_parameters else [],
                                id="wf-use-parameters",
                                className="checklist-switch",
                                style={"marginBottom": "12px", "marginTop": "5px", "display": "inline-block"},
                            ),
                            ui.tooltip_icon("Replace values in a target file using selected workflow configuration files."),
                        ],
                        style={"marginBottom": "12px"},
                    ),
                    html.Div(
                        children=[
                            workflow_form_field(
                                label="Parameter target file",
                                id="wf-param-target-file",
                                value=defval("param_target_file", ""),
                                tooltip="File in the copied sources where replacements are applied.",
                            ),
                            workflow_form_field(
                                label="Start delimiter",
                                id="wf-start-delimiter",
                                value=defval("start_delimiter", ""),
                                tooltip="Start marker for replacement. Escape sequences such as \\n are supported.",
                            ),
                            workflow_form_field(
                                label="Stop delimiter",
                                id="wf-stop-delimiter",
                                value=defval("stop_delimiter", ""),
                                tooltip="Stop marker for replacement. Escape sequences such as \\n are supported.",
                            ),
                        ],
                        id="wf-params-config-fields",
                        className="animated-section" if use_parameters else "animated-section hide",
                        style={"overflow": "visible"},
                    ),
                ],
                className="tile config",
            ),
            html.Div(
                [
                    html.H3("Progress tracking"),
                    workflow_form_field(
                        label="Progress file",
                        id="wf-progress-file",
                        value=progress.get("file", ""),
                        tooltip="Path of the progress file generated by tasks.",
                    ),
                    workflow_form_field(
                        label="Progress regex",
                        id="wf-progress-regex",
                        value=progress.get("regex", ""),
                        tooltip="Regex containing one capture group for completion percentage.",
                    ),
                ],
                className="tile config",
            ),
    ]
    # Two flex columns, not CSS columns: a multicol container is laid out
    # again as a whole at every change, and fragments the dropdown menus.
    return html.Div(
        children=[
            html.Div([tiles[0], tiles[2]], className="flex-form-column"),
            html.Div([tiles[1]], className="flex-form-column"),
        ],
        className="tiles-container config flex-form",
        style={"marginTop": "-10px", "marginBottom": "20px"},
    )

def wf_task_card(name="main", **values):
    return te.task_card("wf", name=name, values=values, with_phony=True)

def wf_add_card(prefix: str = "wf-variable", text: str = "Add new variable", mode="variable"):
    return html.Div(
        html.Div(
            html.Div(
                children=[
                    html.Div("+", style={"fontSize": "2.5em", "lineHeight": "80px", "height": "80px", "marginTop": "-2px", "marginBottom": "-16px"}),
                    html.Div(text, style={"fontWeight": "bold", "fontSize": "1.2em", "paddingBottom": "20px"}),
                ],
                style={"display": "flex", "flexDirection": "column", "alignItems": "center", "justifyContent": "center", "height": "100%"}
            ),
            id=f"{prefix}-new",
            n_clicks=0,
            style={"textDecoration": "none", "height": "100%"},
        ),
        className="tile config add hover" if mode == "task" else "card configs add hover",
        id=f"{prefix}-add-card",
        style= {
        } if mode == "task" else {
            "padding": "10px",
            "margin": "5px",
            "display": "inline-block",
            "verticalAlign": "top",
            "boxSizing": "border-box"
        },
    )

def wf_cards_from_tasks(tasks):
    cards = te.cards_from_tasks("wf", tasks, with_phony=True)
    if not any(card.id.get("name") == "main" for card in cards):
        cards.insert(0, wf_task_card(name="main"))
    cards.append(wf_add_card(prefix="wf-task", text="Add new task", mode="task"))
    return cards

def wf_variable_card(name, **values):
    """A variable card of this page: with the "Unit" field."""
    values.setdefault("unit_value", "")
    return ve.variable_card(VE_PREFIX, name, scope=VE_SCOPE, **values)

def wf_cards_from_variables(variables):
    cards = ve.variable_cards_from_dict(VE_PREFIX, variables, scope=VE_SCOPE, with_unit=True)
    cards.append(wf_add_card(prefix="wf-variable", text="Add new variable"))
    return cards

def _free_name(base, existing):
    """`base`1, `base`2... the first one no card holds yet."""
    idx = 1
    while f"{base}{idx}" in existing:
        idx += 1
    return f"{base}{idx}"

######################################
# Card slots
######################################
# Every card lives in a "slot" of its own (a <div> with display: contents, so
# the row lays the cards out as if it were not there), and the add card in the
# last one. Adding a card fills that last slot with the new card and a new last
# slot; deleting one empties its slot. The row itself is never sent back: Dash
# works out where every id of an updated subtree sits by comparing it with every
# id of the page that has the same keys (computePaths), and the row of a big
# workflow holds hundreds of them -- adding a card to it took 4 to 11 seconds.

def _slot(kind, serial, children):
    return html.Div(children, id={"type": f"wf-{kind}-slot", "slot": serial}, style={"display": "contents"})

def _slotted(kind, cards):
    """
    The children of a row, from its cards (the add card last), and where each
    card is: what the add, duplicate and delete callbacks need to find it again.
    """
    cards = list(cards)
    add_card = cards.pop()
    children = []
    serials = {}
    for serial, card in enumerate(cards):
        serials[card.id.get("name")] = serial
        children.append(_slot(kind, serial, [card]))
    children.append(_slot(kind, len(cards), [add_card]))
    return children, {"cards": serials, "add": len(cards), "next": len(cards) + 1}

def _slot_update(kind, slot_ids, slots, add_card, new_card=None, new_name=None, deleted=None):
    """
    What the slots of a row become: the new card added before the add card,
    or the card `deleted` taken out. Every other slot is left as it is.
    """
    slots = {
        "cards": dict((slots or {}).get("cards") or {}),
        "add": (slots or {}).get("add", 0),
        "next": (slots or {}).get("next", 1),
    }
    serials = [slot_id.get("slot") for slot_id in slot_ids or [] if isinstance(slot_id, dict)]
    children = [dash.no_update for _ in serials]
    if new_card is not None:
        if slots["add"] not in serials:
            raise PreventUpdate
        serial = slots["next"]
        children[serials.index(slots["add"])] = [_slot(kind, serial, [new_card]), _slot(kind, serial + 1, [add_card])]
        slots["cards"][new_name] = serial
        slots["add"] = serial + 1
        slots["next"] = serial + 2
    elif deleted is not None:
        serial = slots["cards"].pop(deleted, None)
        if serial not in serials:
            raise PreventUpdate
        children[serials.index(serial)] = []
    return children, slots

def _taken_names(names, slots):
    """
    The names a new card cannot take: those of the cards, and those of the
    slots, which keep the ids of their cards (a name taken again would give two
    components the same id).
    """
    return set(names) | set(((slots or {}).get("cards") or {}).keys())

def _clicked():
    """
    Whether the callback answers an actual click. Dash also calls it when a
    card holding one of its buttons is added to the page: the button is new,
    and has never been clicked.
    """
    return bool(ctx.triggered and ctx.triggered[0].get("value"))


######################################
# Callbacks
######################################

# Adding, duplicating or deleting a card updates one slot of the row, never the
# row itself (see _slotted): on a workflow of forty tasks the row is half a
# megabyte, and even a Patch of it took seconds to land in the browser.

@dash.callback(
    Output({"type": "wf-task-slot", "slot": dash.ALL}, "children"),
    Output("wf-task-slots", "data", allow_duplicate=True),
    Input("wf-task-new", "n_clicks"),
    Input({"type": "wf-duplicate-task", "name": dash.ALL}, "n_clicks"),
    Input({"type": "wf-delete-task", "name": dash.ALL}, "n_clicks"),
    State({"type": "wf-task-card", "name": dash.ALL}, "id"),
    State({"type": "wf-task-slot", "slot": dash.ALL}, "id"),
    State("wf-task-slots", "data"),
    *te.task_field_dependencies("wf", State),
    State({"type": "wf-task-field-phony", "name": dash.ALL}, "id"),
    State({"type": "wf-task-field-phony", "name": dash.ALL}, "value"),
    prevent_initial_call=True,
)
def update_wf_task_cards(new_click, duplicate_clicks, delete_clicks, card_ids, slot_ids, slots, *task_fields):
    trigger_id = ctx.triggered_id
    if not _clicked():
        raise PreventUpdate
    field_values = task_fields[:len(te.TASK_FIELDS)]
    phony_ids, phony_values = task_fields[len(te.TASK_FIELDS):] or ([], [])
    names = [card_id.get("name") for card_id in card_ids or [] if isinstance(card_id, dict)]
    add_card = wf_add_card(prefix="wf-task", text="Add new task", mode="task")

    if trigger_id == "wf-task-new":
        name = _free_name("task", _taken_names(names, slots))
        return _slot_update("task", slot_ids, slots, add_card, new_card=wf_task_card(name=name), new_name=name)

    if not isinstance(trigger_id, dict) or trigger_id.get("name") not in names:
        raise PreventUpdate
    trig_name = trigger_id.get("name")
    idx = names.index(trig_name)

    if trigger_id.get("type") == "wf-delete-task":
        if trig_name == "main":
            # A workflow always has its "main" task.
            raise PreventUpdate
        return _slot_update("task", slot_ids, slots, add_card, deleted=trig_name)

    taken = _taken_names(names, slots)
    copy_idx = 1
    while f"{trig_name}_copy{copy_idx}" in taken:
        copy_idx += 1
    values = te.card_values(field_values, idx)
    values["phony"] = te.phony_by_name(phony_ids, phony_values).get(trig_name, True)
    name = f"{trig_name}_copy{copy_idx}"
    return _slot_update("task", slot_ids, slots, add_card, new_card=wf_task_card(name=name, **values), new_name=name)

@dash.callback(
    Output("workflow-form-container", "children"),
    Output("workflow-initial-settings", "data"),
    Output("wf-task-cards-row", "children"),
    Output("wf-variable-cards-row", "children"),
    Output("workflow-form-token", "data"),
    Output("workflow-loaded-name", "data"),
    Output("wf-task-slots", "data"),
    Output("wf-variable-slots", "data"),
    Input(f"url_{page_path}", "search"),
    State(f"url_{page_path}", "pathname"),
    State("workflow-loaded-name", "data"),
    State("workflow-form-token", "data"),
    State("odatix-settings", "data"),
)
def init_form(search, page, loaded_name, token, odatix_settings):
    if page != page_path:
        raise PreventUpdate

    workflow_name = get_key_from_url(search, "workflow")
    # The address names the workflow the form already shows: it is the one just
    # saved under a new name. The form says what was saved, and the message
    # saying so stays.
    if workflow_name and workflow_name == loaded_name:
        raise PreventUpdate

    token = (token or 0) + 1
    settings = {}
    if workflow_name:
        workflows = get_workspace(odatix_settings).workflows
        settings = normalize_workflow_settings(workflows.entry(workflow_name).settings.to_dict())
    task_row, task_slots = _slotted("task", wf_cards_from_tasks(settings.get("tasks", [])))
    variable_row, variable_slots = _slotted("variable", wf_cards_from_variables(settings.get("variables", {})))
    return (
        workflow_form(settings), settings, task_row, variable_row,
        token, workflow_name or "", task_slots, variable_slots,
    )

@dash.callback(
    Output("wf-hl-param-domains", "data"),
    Input(f"url_{page_path}", "search"),
    State(f"url_{page_path}", "pathname"),
    State("odatix-settings", "data"),
)
def update_wf_param_domains(search, page, odatix_settings):
    """
    The workflow's parameter domains (its subdirectories), so the command
    highlighter can color them apart from defined variables. Empty for a new,
    unsaved workflow.
    """
    if page != page_path:
        return dash.no_update
    workflow_name = get_key_from_url(search, "workflow")
    if not workflow_name:
        return []
    try:
        return get_workspace(odatix_settings).workflows.entry(workflow_name).domains.sub_names()
    except Exception:
        return []


# Push the parameter domains to the client and ask the highlighter to redraw.
dash.clientside_callback(
    dash.ClientsideFunction(namespace="odatix_highlight", function_name="push_names"),
    Output("wf-hl-dummy", "data"),
    Input("wf-hl-param-domains", "data"),
)


#: What the form holds, in the order the save callback receives it.
_FORM_FIELDS = [
    Input("workflow-title", "value"),
    Input("wf-source-path", "value"),
    Input("wf-source-whitelist", "value"),
    Input("wf-source-blacklist", "value"),
    Input("wf-use-parameters", "value"),
    Input("wf-param-target-file", "value"),
    Input("wf-start-delimiter", "value"),
    Input("wf-stop-delimiter", "value"),
    Input("wf-progress-file", "value"),
    Input("wf-progress-regex", "value"),
    *te.task_field_dependencies("wf", Input),
    Input({"type": "wf-task-field-phony", "name": dash.ALL}, "value"),
] + [
    Input({"type": "wf-variable-" + kind, "name": dash.ALL, **VE_SCOPE}, "value")
    for kind in (
        "title", "type", "field-base", "field-from", "field-to", "field-from_2_pow", "field-to_2_pow",
        "field-from_type", "field-to_type", "field-step", "field-op", "field-list", "field-source",
        "field-sources", "field-format", "field-group", "field-unit",
    )
]

def _as_states(dependencies):
    return [State(dependency.component_id, dependency.component_property) for dependency in dependencies]

#: The fields not typed into (dropdowns, switches): a change to them is one
#: event, it may trigger save_status at once.
_CLICKED_FIELDS = ("wf-use-parameters", "wf-task-field-phony", "wf-variable-type",
                   "wf-variable-field-from_type", "wf-variable-field-to_type")

def _save_status_dependencies(dependencies):
    """The form fields as save_status reads them: clicked ones first, as Input, then the typed ones, as State."""
    def type_of(dependency):
        component_id = dependency.component_id
        return component_id["type"] if isinstance(component_id, dict) else component_id
    clicked = [dependency for dependency in dependencies if type_of(dependency) in _CLICKED_FIELDS]
    typed = [dependency for dependency in dependencies if type_of(dependency) not in _CLICKED_FIELDS]
    return clicked + _as_states(typed)


# Whether there is anything to save is answered on the client, at each
# keystroke: it compares what the form holds with what it held when it was
# filled or last saved (assets/workflow_editor.js). Sending the whole form to
# the server at each keystroke is what made a big workflow take seconds to
# answer a key.
page_clientside_callback(
    PAGE_SCOPE,
    dash.ClientsideFunction(namespace="odatix_workflow_editor", function_name="save_status"),
    Output({"page": page_path, "action": "save-all"}, "className"),
    Output({"page": page_path, "action": "save-all"}, "data-tooltip"),
    Output("workflow-snapshot", "data"),
    Input("workflow-form-token", "data"),
    Input("workflow-save-request", "data"),
    Input("workflow-save-result", "data"),
    # Typing reaches it through this store only, which assets/workflow_editor.js
    # stamps once the keys have rested: a keystroke must not dispatch a
    # callback reading a few thousand fields (each dispatch re-renders the
    # store of every component of the page in Dash).
    Input("workflow-form-edit", "data"),
    # A card added, duplicated or deleted.
    Input("wf-task-slots", "data"),
    Input("wf-variable-slots", "data"),
    *_save_status_dependencies(_FORM_FIELDS),
    State("workflow-snapshot", "data"),
    State("workflow-loaded-name", "data"),
    State("workflow-invalid-chars", "data"),
)

# Saving can take a moment on a big workflow: save_status says so on the
# button at once. It is the only callback writing the state of the button
# (Dash refuses two writers of a pattern id), so the click and the answer of
# the server reach it through stores.
page_clientside_callback(
    PAGE_SCOPE,
    dash.ClientsideFunction(namespace="odatix_workflow_editor", function_name="save_request"),
    Output("workflow-save-request", "data"),
    Input({"page": page_path, "action": "save-all"}, "n_clicks"),
    prevent_initial_call=True,
)

def _same_value(value, other):
    """Whether two settings values say the same, an absent value being empty."""
    def empty_as_none(item):
        item = _plain(item)
        return None if item in ("", [], {}) else item
    return empty_as_none(value) == empty_as_none(other)

def _differences(written, reread):
    """The settings written that the file does not say, by name."""
    keys = []
    for key in ("sources", "progress"):
        for sub in written.get(key, {}):
            if not _same_value(written[key][sub], (reread.get(key) or {}).get(sub)):
                keys.append(f"{key}.{sub}")
    for key in ("use_parameters", "param_target_file", "start_delimiter", "stop_delimiter"):
        if key in written and not _same_value(written[key], reread.get(key)):
            keys.append(key)
    if "tasks" in written and not same_tasks(written["tasks"], reread.get("tasks", [])):
        keys.append("tasks")
    if "variables" in written and not _same_value(written["variables"], reread.get("variables", {})):
        keys.append("variables")
    return keys

@page_callback(PAGE_SCOPE,
    Output("workflow-save-result", "data"),
    Output(f"url_{page_path}", "search"),
    Output("workflow-form-token", "data", allow_duplicate=True),
    Output("workflow-loaded-name", "data", allow_duplicate=True),
    Output("workflow-save-feedback", "children"),
    Input({"page": page_path, "action": "save-all"}, "n_clicks"),
    *_as_states(_FORM_FIELDS),
    # Which task each switch belongs to: "main" has none.
    State({"type": "wf-task-field-phony", "name": dash.ALL}, "id"),
    State(f"url_{page_path}", "search"),
    State("workflow-form-token", "data"),
    State("odatix-settings", "data"),
    prevent_initial_call=True,
)
def save_workflow(
    n_clicks,
    workflow_title_value,
    source_path,
    source_whitelist,
    source_blacklist,
    use_parameters,
    param_target_file,
    start_delimiter,
    stop_delimiter,
    progress_file,
    progress_regex,
    task_names,
    task_dependencies,
    task_commands,
    task_on_failure_commands,
    task_paths,
    task_platforms,
    task_phony_values,
    variable_titles,
    variable_types,
    variable_base_vals,
    variable_from_vals,
    variable_to_vals,
    variable_from_2_pow_vals,
    variable_to_2_pow_vals,
    variable_from_type_vals,
    variable_to_type_vals,
    variable_step_vals,
    variable_op_vals,
    variable_list_vals,
    variable_source_vals,
    variable_sources_vals,
    variable_format_vals,
    variable_group_vals,
    variable_unit_vals,
    task_phony_ids,
    search,
    token,
    odatix_settings,
):
    # The button is part of the title, which a callback renders: a new button
    # triggers this too, without anyone clicking it. Only a click saves.
    if not n_clicks:
        raise PreventUpdate

    def failed(message):
        return (
            {"error": message, "clicks": n_clicks},
            dash.no_update, dash.no_update, dash.no_update, ui.error(f"Not saved: {message}"),
        )

    if not workflow_title_value:
        return failed("Workflow name cannot be empty")
    for character in hard_settings.invalid_filename_characters:
        if character in workflow_title_value:
            label = "' ' (space)" if character == " " else f"'{character}'"
            return failed(f"Unauthorized character in workflow name: {label}")
    names = [str(title).strip() for title in variable_titles or []]
    if any(name == "" for name in names):
        return failed("A variable has no name")
    duplicates = sorted(set(name for name in names if names.count(name) > 1))
    if duplicates:
        return failed(f"Duplicate variable name: '{duplicates[0]}'")

    parsed_tasks = wf_build_tasks_list(
        task_names, task_dependencies, task_commands, task_on_failure_commands, task_paths, task_platforms,
        phony=te.phony_by_name(task_phony_ids, task_phony_values),
    )
    variables = wf_build_variables_dict(
        variable_titles, variable_types, variable_base_vals, variable_from_vals, variable_to_vals,
        variable_from_2_pow_vals, variable_to_2_pow_vals, variable_from_type_vals, variable_to_type_vals,
        variable_step_vals, variable_op_vals, variable_list_vals, variable_source_vals, variable_sources_vals,
        variable_format_vals, variable_group_vals, unit_vals=variable_unit_vals,
    )

    workflow_name = get_key_from_url(search, "workflow")
    workflows = get_workspace(odatix_settings).workflows
    new_search = dash.no_update

    try:
        if workflow_name and workflow_title_value != workflow_name:
            if workflow_title_value in workflows:
                return failed(f"'{workflow_title_value}' already exists")
            if workflow_name in workflows:
                workflows.rename(workflow_name, workflow_title_value)
            workflow_name = workflow_title_value
            new_search = f"?workflow={workflow_name}"
        elif not workflow_name:
            workflow_name = workflow_title_value
            new_search = f"?workflow={workflow_name}"

        workflow = workflows.get(workflow_name)
        if workflow is None:
            workflow = workflows.create(workflow_name)

        # What is written is what the cards say, not its normalized form (which
        # spells every list entry as text, for comparing only), with what the
        # cards do not edit kept as the file has it, where the file has it. A
        # list the form did not change is not written at all: the file keeps
        # its own layout ("dependencies: [a, b]").
        stored = workflow.settings.to_dict()
        stored_variables, _legacy = get_variables(stored)
        to_write = {
            "use_parameters": True if use_parameters else False,
            "param_target_file": param_target_file or "",
            "start_delimiter": start_delimiter or "",
            "stop_delimiter": stop_delimiter or "",
        }
        blocks = {
            "sources": {
                "path": source_path or "",
                "whitelist": _normalize_list(source_whitelist),
                "blacklist": _normalize_list(source_blacklist),
            },
            "progress": {
                "file": progress_file or "",
                "regex": progress_regex or "",
            },
        }
        tasks = keep_unmanaged_task_keys(parsed_tasks, stored.get("tasks"), managed=TASK_MANAGED_KEYS)
        if not same_tasks(tasks, stored.get("tasks")):
            to_write["tasks"] = tasks
        if not same_variables(variables, stored_variables):
            to_write["variables"] = ve.keep_unmanaged_keys(variables, stored_variables, managed=ve.MANAGED_KEYS_WITH_UNIT)

        settings = workflow.settings
        for key, values in blocks.items():
            block = getattr(settings, key, None)
            if isinstance(block, Settings):
                # Field by field: the block keeps what the file says around it.
                for sub, value in values.items():
                    setattr(block, sub, value)
            else:
                to_write[key] = values
        settings.update(to_write)
        workflow.save()

        # "Saved." only once the file says so.
        written = dict(to_write, **blocks)
        reread = get_workspace(odatix_settings).workflows.entry(workflow_name).settings.to_dict()
        reread_variables, _legacy = get_variables(reread)
        reread["variables"] = reread_variables
        missing = _differences(written, reread)
        if missing:
            return failed("the file does not say what was saved (" + ", ".join(missing) + ")")
    except Exception as e:
        return failed(str(e))

    return (
        {"error": None, "clicks": n_clicks},
        new_search,
        # A new snapshot of the form: what it holds now is what is saved.
        (token or 0) + 1,
        workflow_name,
        ui.success(),
    )

@dash.callback(
    Output("wf-params-config-fields", "className"),
    Input("wf-use-parameters", "value"),
)
def toggle_parameter_fields(use_parameters):
    return "animated-section" if use_parameters else "animated-section hide"

@dash.callback(
    Output({"page": page_path, "type": "workflow-title-div"}, "children"),
    Input(f"url_{page_path}", "search"),
)
def update_workflow_title(search):
    workflow_name = get_key_from_url(search, "workflow")
    if not workflow_name:
        workflow_name = ""
    return workflow_title(workflow_name)

# Which fields of a variable card its type uses is answered on the client too
# (assets/workflow_editor.js), from ve.FIELD_VISIBILITY handed over in a store.
page_clientside_callback(
    PAGE_SCOPE,
    dash.ClientsideFunction(namespace="odatix_workflow_editor", function_name="field_visibility"),
    [Output({"type": f"wf-variable-field-{field}-div", "name": dash.ALL, **VE_SCOPE}, "style") for field in ve.VARIABLE_FIELDS],
    Input({"type": "wf-variable-type", "name": dash.ALL, **VE_SCOPE}, "value"),
    State("wf-variable-field-visibility", "data"),
    [State({"type": f"wf-variable-field-{field}-div", "name": dash.ALL, **VE_SCOPE}, "style") for field in ve.VARIABLE_FIELDS],
)

# Folding the extra fields away is done on the client, on the document, by the
# handler in assets/folds.js: nothing outside the browser reads whether a fold
# is open, and a fold answered by Dash costs a walk over every pattern-matched
# component of the page.

#: The fields of a variable card a duplicate copies, as the arguments of
#: variable_editor.variable_card.
_VARIABLE_COPY_FIELDS = (
    ("type", "type_value"), ("field-base", "base_value"), ("field-from", "from_value"),
    ("field-to", "to_value"), ("field-from_2_pow", "from_2_pow_value"), ("field-to_2_pow", "to_2_pow_value"),
    ("field-from_type", "from_type_value"), ("field-to_type", "to_type_value"), ("field-step", "step_value"),
    ("field-op", "op_value"), ("field-list", "list_value"), ("field-source", "source_value"),
    ("field-sources", "sources_value"), ("field-format", "format_value"), ("field-group", "group_value"),
    ("field-unit", "unit_value"),
)

@dash.callback(
    Output({"type": "wf-variable-slot", "slot": dash.ALL}, "children"),
    Output("wf-variable-slots", "data", allow_duplicate=True),
    Input("wf-variable-new", "n_clicks"),
    Input({"type": "wf-duplicate-var", "name": dash.ALL, **VE_SCOPE}, "n_clicks"),
    Input({"type": "wf-delete-var", "name": dash.ALL, **VE_SCOPE}, "n_clicks"),
    State({"type": "wf-variable-card", "name": dash.ALL, **VE_SCOPE}, "id"),
    State({"type": "wf-variable-slot", "slot": dash.ALL}, "id"),
    State("wf-variable-slots", "data"),
    *[State({"type": f"wf-variable-{kind}", "name": dash.ALL, **VE_SCOPE}, "value") for kind, _arg in _VARIABLE_COPY_FIELDS],
    prevent_initial_call=True,
)
def update_wf_variable_cards(new_click, duplicate_clicks, delete_clicks, card_ids, slot_ids, slots, *field_values):
    trigger_id = ctx.triggered_id
    if not _clicked():
        raise PreventUpdate
    names = [card_id.get("name") for card_id in card_ids or [] if isinstance(card_id, dict)]
    add_card = wf_add_card(prefix="wf-variable", text="Add new variable")

    if trigger_id == "wf-variable-new":
        name = _free_name("var", _taken_names(names, slots))
        return _slot_update("variable", slot_ids, slots, add_card, new_card=wf_variable_card(name), new_name=name)

    if not isinstance(trigger_id, dict) or trigger_id.get("name") not in names:
        raise PreventUpdate
    trig_name = trigger_id.get("name")
    idx = names.index(trig_name)

    if trigger_id.get("type") == "wf-delete-var":
        return _slot_update("variable", slot_ids, slots, add_card, deleted=trig_name)

    taken = _taken_names(names, slots)
    copy_idx = 1
    while f"{trig_name}_copy{copy_idx}" in taken:
        copy_idx += 1
    values = {}
    for (_kind, argument), column in zip(_VARIABLE_COPY_FIELDS, field_values):
        column = column or []
        value = column[idx] if idx < len(column) else None
        values[argument] = "" if value is None else value
    name = f"{trig_name}_copy{copy_idx}"
    return _slot_update("variable", slot_ids, slots, add_card, new_card=wf_variable_card(name, **values), new_name=name)


######################################
# Layout
######################################

layout = html.Div(
    children=[
        # The address changes when a workflow is saved under a new name: the
        # page stays, with what it holds.
        dcc.Location(id=f"url_{page_path}", refresh=False),
        html.Div(id={"page": page_path, "type": "workflow-title-div"}, style={"marginTop": "20px"}),
        html.Div(ui.feedback("workflow-save-feedback"), className="card-matrix config"),
        # Rendered empty from the start, then filled by init_form: the fields
        # are inputs of save_status, which must find them on load.
        html.Div(workflow_form({}), id="workflow-form-container"),
        html.Div(
            children=[
                ui.title_tile(
                    text="Task definition", id="wf-task-title",
                    tooltip="Tasks can be used to define the steps of the workflow.",
                    buttons=builtin_variables.variable_list("workflow", id="wf-builtin-variables"),
                ),
                html.Div([
                    html.Div(
                        id="wf-task-cards-row",
                        children=[wf_add_card(prefix="wf-task", text="Add new task", mode="task")],
                        className="tiles-container config",
                        style={"display": "flex", "justifyContent": "flex-start", "alignItems": "flex-start", "flexWrap": "wrap", "marginBottom": "30px", "columnGap": "var(--tile-gap)"},
                    ),
                ]),
                ui.title_tile(text="Variable definition", id="wf-variable-title", tooltip="Variables can be used inside commands and can also be used to generate configurations."),
                html.Div([
                    html.Div(
                        id="wf-variable-cards-row",
                        children=[wf_add_card(prefix="wf-variable", text="Add new variable")],
                        className="card-matrix configs",
                        style={"marginBottom": "30px"},
                    ),
                ]),
            ],
        ),
        dcc.Store(id="workflow-initial-settings", data=None),
        # The form as it was filled or last saved, which save_status compares
        # the fields with; renewed each time the token changes.
        dcc.Store(id="workflow-form-token", data=None),
        dcc.Store(id="workflow-snapshot", data=None),
        dcc.Store(id="workflow-form-edit", data=None),
        # Where each card of the two rows is (see _slotted).
        dcc.Store(id="wf-task-slots", data=None),
        dcc.Store(id="wf-variable-slots", data=None),
        # A click on the save button, and how the save went (see save_status).
        dcc.Store(id="workflow-save-request", data=None),
        dcc.Store(id="workflow-save-result", data=None),
        # The workflow the form shows, as saved (None before it is filled).
        dcc.Store(id="workflow-loaded-name", data=None),
        dcc.Store(id="workflow-invalid-chars", data=hard_settings.invalid_filename_characters),
        dcc.Store(
            id="wf-variable-field-visibility",
            data={"fields": ve.VARIABLE_FIELDS, "types": {key: sorted(value) for key, value in ve.FIELD_VISIBILITY.items()}},
        ),
        # Physical parameter domains of the workflow (directory names), pushed to
        # the client so the command highlighter can tell them apart from defined
        # variables (which it reads live from the variable cards).
        dcc.Store(id="wf-hl-param-domains", data=[]),
        dcc.Store(id="wf-hl-dummy", data=""),
        # A workflow command has no built-in variable, but declaring the (empty)
        # list keeps a stale one from another editor out of this page.
        builtin_variables.highlight_data("workflow", id="wf-hl-builtins", declares_variables=True),
    ],
    className="page-content workflow-editor-page",
    style={
        "display": "flex",
        "flexDirection": "column",
        "min-height": f"calc(100vh - {navigation.top_bar_height})",
    },
)

# Anchor of PAGE_SCOPE: makes this page the only one dispatching its callbacks.
layout = scoped(PAGE_SCOPE, layout)
