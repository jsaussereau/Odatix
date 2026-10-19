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
from dash import html, dcc, Input, Output, State, ALL, ctx
from dash.exceptions import PreventUpdate

from odatix.gui.icons import icon
from odatix.gui.utils import get_workspace
import odatix.gui.ui_components as ui
import odatix.gui.navigation as navigation
from odatix.lib.settings import OdatixSettings
from odatix.gui.page_scope import page_callback, scoped
from odatix.workspace import Workspace
from odatix.workspace import migrate as workspace_migrate
from odatix.workspace.core import PATH_SETTINGS, WorkspaceSettings
from odatix.workspace.yaml_io import read_yaml

# Scope anchoring the callbacks below: they are dispatched only on the pages
# embedding the matching anchor store (see odatix.gui.page_scope).
PAGE_SCOPE = "workspace_settings"

page_path = "/workspace"

dash.register_page(
    __name__,
    path=page_path,
    title='Odatix - Workspace settings',
    name='Workspace',
    order=10,
)

######################################
# Fields
######################################
#
# The form is generated from WorkspaceSettings, the class that reads and writes
# "odatix.yml": every key it declares gets a field, in file order, grouped by
# the sections of the file. The table below only says how a key reads in the
# page; a key it does not know about still gets a text field, labelled after
# its name and explained by the documentation of the setting.

#: Type of the pattern-matching ids of the fields: {"type": ..., "key": <setting>}.
FIELD_TYPE = "workspace-setting"

#: Keys of odatix.yml that are not settings a user edits.
HIDDEN_KEYS = ("workspace",)

#: How each setting reads in the page. "kind" is "text" when left out.
FIELDS = {
    "default_tool": {
        "label": "Default tool",
        "kind": "tool",
        "tooltip": "The tool the run commands use when -t/--tool does not name one. "
                   "Left empty, a workspace with a single target file uses that tool.",
    },
    "arch_path": {
        "label": "Architecture directory",
        "tooltip": "Where the architecture definitions are.",
    },
    "sim_path": {
        "label": "Simulation directory",
        "tooltip": "Where the simulation definitions are.",
    },
    "workflow_path": {
        "label": "Workflow directory",
        "tooltip": "Where the workflow definitions are.",
    },
    "tools_path": {
        "label": "Tool directory",
        "tooltip": "Where the tools defined by this workspace are, next to the built-in ones.",
    },
    "target_path": {
        "label": "Target definition directory",
        "tooltip": "Where the target files of every tool are. "
                   "Files not found here are also looked up in odatix_userconfig.",
    },
    "gui_theme_path": {
        "label": "GUI theme directory",
        "tooltip": "Where the themes of this workspace are, next to the built-in ones.",
    },
    "clean_settings_file": {
        "label": "Clean settings",
        "tooltip": "What \"odatix clean\" removes.",
    },
    "sim_settings_file": {
        "label": "Simulation settings",
        "tooltip": "The settings file of \"odatix sim\".",
    },
    "fmax_settings_file": {
        "label": "Fmax synthesis settings",
        "tooltip": "The settings file of \"odatix fmax\".",
    },
    "synth_settings_file": {
        "label": "Fixed-frequency synthesis settings",
        "tooltip": "The settings file of \"odatix synth\".",
    },
    "pnr_settings_file": {
        "label": "Place & route settings",
        "tooltip": "The settings file of \"odatix pnr\".",
    },
    "analyze_settings_file": {
        "label": "Analysis settings",
        "tooltip": "The settings file of \"odatix analyze\".",
    },
    "workflow_settings_file": {
        "label": "Workflow settings",
        "tooltip": "The settings file of \"odatix workflow\".",
    },
    "dse_settings_file": {
        "label": "Exploration settings",
        "tooltip": "The settings file of \"odatix dse\".",
    },
    "dse_campaign_path": {
        "label": "Campaign directory",
        "tooltip": "Where the design space exploration campaigns are kept.",
    },
    "derived_metrics_file": {
        "label": "Derived metrics",
        "tooltip": "The metrics computed from the ones the runs produce.",
    },
    "work_path": {
        "label": "Main work path",
        "tooltip": "Where every job runs. The work paths below are relative to it.",
    },
    "simulation_work_path": {
        "label": "Simulation work path",
        "tooltip": "Where simulations run, relative to the main work path.",
    },
    "fmax_synthesis_work_path": {
        "label": "Fmax synthesis work path",
        "tooltip": "Where Fmax synthesis runs, relative to the main work path.",
    },
    "custom_freq_synthesis_work_path": {
        "label": "Fixed-frequency synthesis work path",
        "tooltip": "Where fixed-frequency synthesis runs, relative to the main work path.",
    },
    "pnr_work_path": {
        "label": "Place & route work path",
        "tooltip": "Where place & route runs, relative to the main work path.",
    },
    "analysis_work_path": {
        "label": "Analysis work path",
        "tooltip": "Where analyses run, relative to the main work path.",
    },
    "workflow_work_path": {
        "label": "Workflow work path",
        "tooltip": "Where workflows run, relative to the main work path.",
    },
    "result_path": {
        "label": "Result path",
        "tooltip": "Where the result files are written.",
    },
    "resource_guard": {
        "label": "Pause jobs on overload",
        "kind": "yes_no",
        "tooltip": "Pause running jobs while the CPU or memory usage of the machine is above the limits below, "
                   "and resume them once it settles back down. Applies to the sessions started afterwards; "
                   "a running session is switched from the monitor.",
    },
    "cpu_limit": {
        "label": "CPU limit (%)",
        "kind": "number",
        "tooltip": "CPU usage of the machine above which a running job is paused.",
    },
    "mem_limit": {
        "label": "Memory limit (%)",
        "kind": "number",
        "tooltip": "Memory usage of the machine above which a running job is paused.",
    },
    "session_access": {
        "label": "Shared with",
        "kind": "access",
        "tooltip": "Who may use the sessions started in this workspace besides you: monitor them, add, pause or "
                   "kill their jobs, stop them. Using a session is running commands as you, so share it only "
                   "with people you trust. Applies to the sessions started afterwards.",
    },
}

#: The choices of "session_access", as the page names them.
ACCESS_OPTIONS = [
    {"label": "Nobody (user)", "value": "user"},
    {"label": "The group of the workspace (group)", "value": "group"},
    {"label": "Every user of the machine (other)", "value": "other"},
]

#: Kinds of field whose empty value is None (a dropdown) rather than "".
DROPDOWN_KINDS = ("tool", "yes_no", "access")


def field_id(key):
    return {"type": FIELD_TYPE, "key": key}


def setting_keys():
    """The keys of odatix.yml the page has a field for, in file order."""
    return [spec.key or spec.name for spec in WorkspaceSettings.specs()
            if spec.stored and (spec.key or spec.name) not in HIDDEN_KEYS]


def field_kind(key):
    return FIELDS.get(key, {}).get("kind", "text")


def field_label(key):
    return FIELDS.get(key, {}).get("label") or key.replace("_", " ").capitalize()


def field_tooltip(key):
    tooltip = FIELDS.get(key, {}).get("tooltip")
    if tooltip:
        return tooltip
    spec = WorkspaceSettings.spec(key)
    return (spec.doc or "") if spec is not None else ""


_PATH_DEFAULTS = dict(PATH_SETTINGS)


def field_placeholder(key):
    """What Odatix uses when the field is left empty."""
    if key in _PATH_DEFAULTS:
        return str(getattr(OdatixSettings, _PATH_DEFAULTS[key], ""))
    if key == "default_tool":
        return "None"
    if key == "resource_guard":
        return "Yes" if OdatixSettings.DEFAULT_RESOURCE_GUARD else "No"
    if key == "cpu_limit":
        return "{0:g}".format(OdatixSettings.DEFAULT_CPU_LIMIT)
    if key == "mem_limit":
        return "{0:g}".format(OdatixSettings.DEFAULT_MEM_LIMIT)
    if key == "session_access":
        return ACCESS_OPTIONS[0]["label"]
    return ""


def comparable(value):
    """A field value as the page compares it: empty (None, "") means "use the default"."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return value


def read_settings(path=None):
    """
    What odatix.yml says, one value per field (empty when the file leaves the
    key out). A settings file still naming a key the way a former version did
    shows it under the current name, where saving writes it.
    """
    data = read_yaml(path or Workspace.SETTINGS_FILENAME, default={})
    settings = WorkspaceSettings.from_dict(data if isinstance(data, dict) else {}).normalize()
    return dict((key, comparable(settings[key])) for key in setting_keys())


def values_to_save(values):
    """The field values as save_workspace_settings takes them: empty means "use the default"."""
    return dict((key, None if comparable(value) == "" else comparable(value)) for key, value in values.items())


######################################
# UI Components
######################################

def tool_options():
    """Every tool the workspace can run, built-in ones included."""
    try:
        return [{"label": name, "value": name} for name in get_workspace().tools.all_names()]
    except Exception:
        return []


def setting_field(key, value):
    kind = field_kind(key)
    common = dict(
        label=field_label(key),
        id=field_id(key),
        tooltip=field_tooltip(key),
        placeholder=field_placeholder(key),
    )
    if kind == "tool":
        return ui.form_dropdown(options=tool_options(), value=value or None, **common)
    if kind == "yes_no":
        return ui.form_dropdown(
            options=[{"label": "Yes", "value": True}, {"label": "No", "value": False}],
            value=None if value == "" else value,
            **common
        )
    if kind == "access":
        return ui.form_dropdown(options=ACCESS_OPTIONS, value=value or None, **common)
    if kind == "number":
        return ui.form_field(type="number", value=value, **common)
    return ui.form_field(value=value, **common)


def workspace_form(settings):
    """One panel per section of odatix.yml, one field per key."""
    settings = settings or {}
    panels = []
    for spec in WorkspaceSettings.specs():
        key = spec.key or spec.name
        if not spec.stored or key in HIDDEN_KEYS:
            continue
        if spec.section or not panels:
            panels.append([ui.caption(spec.section or "Settings")])
        panels[-1].append(setting_field(key, comparable(settings.get(key))))
    return ui.grid(children=[ui.panel(body=body) for body in panels])


######################################
# Callbacks
######################################

SAVED_CLASS = "color-button disabled icon-button tooltip delay bottom small"
DIRTY_CLASS = "color-button warning icon-button tooltip bottom small tooltip"
ERROR_CLASS = "color-button error-status icon-button tooltip bottom small"


@page_callback(PAGE_SCOPE,
    Output("workspace-form-container", "children"),
    Output("workspace-initial-settings", "data"),
    Input(f"url_{page_path}", "search"),
    State(f"url_{page_path}", "pathname"),
)
def init_form(search, page):
    if page != page_path:
        return dash.no_update, dash.no_update

    try:
        settings = read_settings()
    except Exception as e:
        return ui.empty_state("Could not read {0}: {1}".format(Workspace.SETTINGS_FILENAME, e)), None
    return workspace_form(settings), settings


# The fields are pattern-matching inputs: the form is built by init_form, and a
# plain id would not exist yet when the page first renders (Dash then reports a
# "nonexistent object used in an Input" error on every visit).
@page_callback(PAGE_SCOPE,
    Output({"page": page_path, "action": "save-all"}, "className"),
    Output({"page": page_path, "action": "save-all"}, "data-tooltip"),
    Output("odatix-settings", "data", allow_duplicate=True),
    Output("workspace-saved-settings", "data"),
    Output("workspace-save-feedback", "children"),
    Input({"page": page_path, "action": "save-all"}, "n_clicks"),
    Input({"type": FIELD_TYPE, "key": ALL}, "value"),
    State({"type": FIELD_TYPE, "key": ALL}, "id"),
    State("workspace-initial-settings", "data"),
    State("workspace-saved-settings", "data"),
    prevent_initial_call=True,
)
def save_and_status(save_n_clicks, values, ids, initial_settings, saved_settings):
    current = dict((field["key"], value) for field, value in zip(ids or [], values or []))
    if not current:
        raise PreventUpdate
    current_comparable = dict((key, comparable(value)) for key, value in current.items())

    if ctx.triggered_id == {"page": page_path, "action": "save-all"}:
        try:
            workspace = Workspace.open()
            workspace.save_settings(values_to_save(current))
            store = workspace.odatix_settings().to_dict()
        except Exception as e:
            return ERROR_CLASS, "Failed to save...", dash.no_update, dash.no_update, ui.error(f"Not saved: {e}")
        return SAVED_CLASS, "Nothing to save", store, current_comparable, ui.success()

    # Compare against what the settings file actually holds (read by init_form,
    # or the last save), not against the defaults: a blank field means "use the
    # default", which the file does not spell out.
    reference = saved_settings if saved_settings is not None else (initial_settings or {})
    saved = dict((key, comparable(reference.get(key))) for key in current_comparable)
    if current_comparable != saved:
        return DIRTY_CLASS, "Unsaved changes!", dash.no_update, dash.no_update, dash.no_update
    return SAVED_CLASS, "Nothing to save", dash.no_update, dash.no_update, dash.no_update


@page_callback(PAGE_SCOPE,
    Output({"type": FIELD_TYPE, "key": ALL}, "value"),
    Input({"page": page_path, "action": "reset-defaults"}, "n_clicks"),
    State({"type": FIELD_TYPE, "key": ALL}, "id"),
    prevent_initial_call=True,
)
def reset_to_defaults(reset_n_clicks, ids):
    """Empty every field: each setting falls back on its default once saved."""
    if not reset_n_clicks:
        raise PreventUpdate
    return [None if field_kind(field["key"]) in DROPDOWN_KINDS else "" for field in (ids or [])]

@page_callback(PAGE_SCOPE,
    Output("workspace-migration", "className"),
    Output("workspace-migration-text", "children"),
    Output("workspace-migration-feedback", "children"),
    Input(f"url_{page_path}", "search"),
    Input("workspace-migrate", "n_clicks"),
    State("odatix-settings", "data"),
)
def migration(search, n_clicks, odatix_settings):
    """Offer to rewrite the settings files still written in a former format."""
    feedback = dash.no_update
    try:
        workspace = get_workspace(odatix_settings)
        if ctx.triggered_id == "workspace-migrate" and n_clicks:
            migrations = workspace_migrate.migrate(workspace)
            rewritten = [migration for migration in migrations if migration.changed]
            left = [reason for migration in migrations for reason in migration.left]
            if left:
                feedback = ui.error("Rewritten: {0} file(s). Left to rewrite by hand: {1}".format(len(rewritten), " ".join(left)))
            else:
                feedback = ui.success("Migrated: {0} file(s). Each rewritten file keeps its former version as a .bak file.".format(len(rewritten)))
        found = workspace_migrate.pending(workspace)
    except Exception as e:
        return "odx-migration hide", "", ui.error(f"Could not migrate: {e}")
    if not found:
        return "odx-migration hide", "", feedback
    text = "{0} settings file(s) use a former format, still read but no longer documented.".format(len(found))
    return "odx-migration", text, feedback


######################################
# Layout
######################################

title_buttons = html.Div(
    children=[
        ui.icon_button(
            id={"page": page_path, "action": "reset-defaults"},
            icon=icon("reset", className="icon"),
            tooltip="Restore default workspace settings",
            tooltip_options="bottom",
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
        html.Div(
            ui.page_bar(
                "Workspace settings",
                actions=title_buttons,
                back_link="/",
                extra=html.Div(
                    "Every path is relative to the workspace. Leave a field blank to use its default value.",
                    className="odx-summary odx-status",
                ),
            ),
            id={"page": page_path, "type": "workspace-title-div"},
        ),
        ui.feedback("workspace-save-feedback"),
        html.Div(
            [
                html.Span(id="workspace-migration-text"),
                ui.icon_button(
                    id="workspace-migrate",
                    icon=icon("check", className="icon"),
                    text="Migrate",
                    color="secondary",
                    tooltip="Rewrite them in the current format, as \"odatix migrate\" does, keeping each former version as a .bak file",
                ),
            ],
            id="workspace-migration",
            className="odx-migration hide",
        ),
        ui.feedback("workspace-migration-feedback"),
        html.Div(id="workspace-form-container"),
        dcc.Store(id="save-state", data=""),
        dcc.Store(id="workspace-initial-settings", data=None),
        dcc.Store(id="workspace-saved-settings", data=None),
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
