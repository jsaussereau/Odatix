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
Exported Metrics Editor page.

Edits how results are extracted from each run at export time, in two modes:

  - workflow mode (/metric_editor?workflow=<name>, from the Workflow Editor):
    the workflow's "_metrics.yml" (see
    odatix.components.export_workflow_results);
  - simulation mode (/metric_editor?simulation=<name>, from the Simulation
    Editor or /architectures): the simulation's "_metrics.yml" (see
    odatix.components.export_simulation_results). Simulations converged with
    workflows, so this mode is the workflow one with a different file to write;
  - tool mode (/metric_editor?tool=<name>, from /tools or the Tool Editor): the
    metrics of an eda tool (see odatix.components.export_results).

In tool mode the page shows both layers of the tool's metrics (see
odatix.lib.metrics): the ones shipped with Odatix and the workspace
"metrics.yml" that completes, overrides or removes them. Every card is editable,
built-in metrics included — editing one writes an override in the workspace and
never touches what Odatix ships. Only the workspace layer is written, and only
what it actually changes: a card left exactly as the built-in metric defines it
saves nothing and keeps following it.

Each card says what your workspace holds for that metric, recomputed live as the
fields are edited: "built-in" (nothing of yours), "overridden" (your definition
wins) or "removed" (excluded from the exported results, saved as an empty
entry). Its reset button drops whatever the workspace says about it, whether an
override or its removal. Workflow mode has a single layer, so its cards have
neither badge nor reset button.

The workflow mode has two independent sections, stored under the "metrics" and
"metadata" keys of the same "_metrics.yml" file:
  - Metrics:  the result values you compare and plot (area, frequency, ...).
  - Metadata: extra dimensions that describe/index the metrics (e.g. a sweep
    variable). Combined with "Multiple values", a single run expands into one
    result entry per metadata value.

Both sections share the exact same card UI: it is built once, parametrized by an
id prefix ("metric" / "metadata"), and its per-section callbacks are registered
for each prefix. The card layout follows the shared variable-editor style of the
Configuration Generator / Workflow Editor pages.
"""

import dash
from dash import html, dcc, Input, Output, State, ctx

import odatix.lib.metrics as metrics_lib
from odatix.gui.icons import icon
from odatix.gui.utils import get_key_from_url, get_workspace
from odatix.gui.css_helper import Style
import odatix.gui.ui_components as ui
import odatix.gui.navigation as navigation
import odatix.lib.hard_settings as hard_settings
from odatix.gui.page_scope import page_callback, page_clientside_callback, scoped

# Scope anchoring the callbacks below: they are dispatched only on the pages
# embedding the matching anchor store (see odatix.gui.page_scope).
PAGE_SCOPE = "metric_editor"

page_path = "/metric_editor"

# The page has two edit modes, selected by the URL query:
#   ?workflow=<name>  -> workflow metrics: two sections (metrics + metadata),
#                        stored in the workflow's "_metrics.yml".
#   ?simulation=<name>-> simulation metrics: same two sections, stored in the
#                        simulation's "_metrics.yml".
#   ?tool=<name>      -> eda tool metrics: three sections (fmax synthesis /
#                        custom frequency synthesis / common), stored in the
#                        tool's "metrics.yml".
# The same prefixed card UI is reused for every section; only the section labels
# and the load/save target differ between modes.

dash.register_page(
    __name__,
    path=page_path,
    title="Odatix - Exported Metrics Editor",
    name="Exported Metrics Editor",
    order=6,
)

# The three reusable section card-rows. Workflow mode uses the first two;
# tool mode uses all three (see WORKFLOW_SECTIONS / TOOL_SECTIONS below).
METRIC_PREFIX = "metric"
META_PREFIX = "metadata"
THIRD_PREFIX = "metric3"

# Explanations of what each section is, shown as tooltips and reused in code.
METRIC_TOOLTIP = (
    "Result values extracted from each workflow run: the quantities you compare and plot."
)
META_TOOLTIP = (
    "Extra dimensions extracted from each run that describe or index the metrics. "
    "It can be used to group or filter metrics. "
    "Combined with a metric's 'Multiple values' option, a single run expands into "
    "one result entry per metadata value."
)

# Tool metric sections: (card-row prefix, section label, tooltip, metrics.yml key).
FMAX_TOOLTIP = "Metrics extracted only for maximum-frequency synthesis."
CUSTOM_FREQ_TOOLTIP = "Metrics extracted only for custom-frequency synthesis."
COMMON_TOOLTIP = "Metrics extracted for every flow (e.g. area, resource counts)."

WORKFLOW_SECTIONS = [
    (METRIC_PREFIX, "Metrics", METRIC_TOOLTIP, "metrics"),
    (META_PREFIX, "Metadata Dimensions", META_TOOLTIP, "metadata"),
]
TOOL_SECTIONS = [
    (METRIC_PREFIX, "Fmax synthesis metrics", FMAX_TOOLTIP, "fmax_synthesis_metrics"),
    (META_PREFIX, "Custom frequency synthesis metrics", CUSTOM_FREQ_TOOLTIP, "custom_freq_synthesis_metrics"),
    (THIRD_PREFIX, "Common metrics", COMMON_TOOLTIP, "metrics"),
]

def _sections_for_mode(is_tool):
    return TOOL_SECTIONS if is_tool else WORKFLOW_SECTIONS

# Metric extraction types and the fields each of them uses.
METRIC_TYPE_OPTIONS = [
    {"label": "Regex", "value": "regex"},
    {"label": "CSV", "value": "csv"},
    {"label": "YAML", "value": "yaml"},
    {"label": "JSON", "value": "json"},
    {"label": "XML", "value": "xml"},
    {"label": "Operation", "value": "operation"},
]

# Fields shown for each extraction type, in render order.
METRIC_FIELDS = ["file", "pattern", "group_id", "key", "op"]

FIELD_VISIBILITY = {
    "regex":     {"file", "pattern", "group_id"},
    "csv":       {"file", "key"},
    "yaml":      {"file", "key"},
    "json":      {"file", "key"},
    "xml":       {"file", "key"},
    "operation": {"op"},
}

def field_style(field, metric_type):
  """Whether `field` is shown for `metric_type`, as a style.

  Cards are built with the right fields already shown: leaving it to the
  callback that follows the type dropdown meant every card rendered with its
  default fields first, then had them rewritten a moment later.
  """
  return Style.visible if field in FIELD_VISIBILITY.get(metric_type, set()) else Style.hidden

# What a card's metric is, in tool mode (see odatix.lib.metrics). Every card is
# editable; this only says what saving it will write to the workspace
# metrics.yml, and is recomputed live as the fields are edited:
#   - "builtin":   still exactly what Odatix defines. Nothing is written for it:
#                  the built-in definition keeps being used.
#   - "workspace": a metric of your own, or a built-in one you changed. Saved as
#                  a definition in the workspace metrics.yml, which overrides
#                  the built-in one.
#   - "removed":   a built-in metric excluded from the exported results. Saved as
#                  an empty ("null") entry.
# Workflow mode has a single layer, so its cards are always "workspace".
ORIGIN_WORKSPACE = "workspace"
ORIGIN_BUILTIN = "builtin"
ORIGIN_REMOVED = "removed"

# Badge shown at the top of a card, telling what the workspace holds for that
# metric. A metric of your own that no built-in one shares a name with gets no
# badge: there is nothing to compare it to.
ORIGIN_NOTES = {
    ORIGIN_BUILTIN: (
        "built-in",
        "Defined by Odatix. Edit any field to override it in your workspace; "
        "the built-in definition stays untouched.",
    ),
    ORIGIN_WORKSPACE: (
        "overridden",
        "This built-in metric is overridden in your workspace. Use the reset button "
        "to drop your changes and go back to the built-in definition.",
    ),
    ORIGIN_REMOVED: (
        "removed",
        "This built-in metric is excluded from the exported results. Use the reset "
        "button to bring it back.",
    ),
}


######################################
# Helpers
######################################

def _checked(value):
    """Turn a checklist value ([True]/[]) or bool into a plain bool."""
    if isinstance(value, (list, tuple)):
        return bool(value)
    return bool(value)

def build_metric_definition(
    metric_type, file_value, pattern_value, group_id_value, key_value, op_value,
    unit_value, format_value, error_if_missing, multiple,
):
    """Build a single metric definition dict from a card's field values."""
    settings = {}
    if metric_type == "regex":
        settings["file"] = file_value or ""
        settings["pattern"] = pattern_value or ""
        group_id = group_id_value
        try:
            group_id = int(group_id_value)
        except (TypeError, ValueError):
            group_id = group_id_value if group_id_value else 0
        settings["group_id"] = group_id
    elif metric_type in ("csv", "yaml", "json", "xml"):
        settings["file"] = file_value or ""
        if key_value:
            settings["key"] = key_value
    elif metric_type == "operation":
        settings["op"] = op_value or ""

    definition = {"type": metric_type, "settings": settings}
    if unit_value:
        definition["unit"] = unit_value
    if format_value:
        definition["format"] = format_value
    if not _checked(error_if_missing):
        definition["error_if_missing"] = False
    if _checked(multiple):
        definition["multiple"] = True
    return definition

def card_fields_of(definition):
    """
    The card field values a metric definition is rendered with, as the keyword
    arguments of metric_card. Used both to build a card and to compare a card
    with the built-in definition of the same metric.
    """
    d = definition if isinstance(definition, dict) else {}
    settings = d.get("settings", {})
    if not isinstance(settings, dict):
        settings = {}
    return dict(
        type_value=d.get("type", "regex"),
        file_value=str(settings.get("file", "")),
        pattern_value=str(settings.get("pattern", "")),
        group_id_value=str(settings.get("group_id", "")),
        key_value=str(settings.get("key", "")),
        op_value=str(settings.get("op", "")),
        unit_value=str(d.get("unit", "")),
        format_value=str(d.get("format", "")),
        error_if_missing_value=bool(d.get("error_if_missing", True)),
        multiple_value=bool(d.get("multiple", False)),
    )

def normalized_definition(definition):
    """
    A metric definition as the editor would save it: the same definition read
    into a card and built back from it. Comparing a card with a built-in metric
    goes through this, so that differences of writing (a group id written as a
    string, a default spelled out) do not read as a change.
    """
    fields = card_fields_of(definition)
    return build_metric_definition(
        fields["type_value"], fields["file_value"], fields["pattern_value"],
        fields["group_id_value"], fields["key_value"], fields["op_value"],
        fields["unit_value"], fields["format_value"],
        fields["error_if_missing_value"], fields["multiple_value"],
    )

def card_origin(name, definition, removed, builtin_section):
    """
    What a card currently is with respect to the built-in metrics (see ORIGIN_*):
    a metric no built-in one shares its name with is always the workspace's own.
    """
    if name not in (builtin_section or {}):
        return ORIGIN_WORKSPACE
    if removed:
        return ORIGIN_REMOVED
    if definition == normalized_definition(builtin_section[name]):
        return ORIGIN_BUILTIN
    return ORIGIN_WORKSPACE

def section_definitions(
    names, types, file_vals, pattern_vals, group_id_vals, key_vals, op_vals,
    unit_vals, format_vals, error_vals, multiple_vals,
):
    """The definition each card of a section currently holds, in card order."""
    definitions = []
    for idx in range(len(names) if isinstance(names, list) else 0):
        definitions.append(build_metric_definition(
            types[idx] if idx < len(types) else "regex",
            file_vals[idx] if idx < len(file_vals) else "",
            pattern_vals[idx] if idx < len(pattern_vals) else "",
            group_id_vals[idx] if idx < len(group_id_vals) else "",
            key_vals[idx] if idx < len(key_vals) else "",
            op_vals[idx] if idx < len(op_vals) else "",
            unit_vals[idx] if idx < len(unit_vals) else "",
            format_vals[idx] if idx < len(format_vals) else "",
            error_vals[idx] if idx < len(error_vals) else [True],
            multiple_vals[idx] if idx < len(multiple_vals) else [],
        ))
    return definitions

def card_origins(names, definitions, origins, builtin_section):
    """
    What each card of a section currently is (see ORIGIN_*), from the values
    being edited rather than from what it was rendered as. `origins` is only
    read for the cards excluded from the export, which are not editable.
    """
    result = []
    for idx, definition in enumerate(definitions):
        name = str(names[idx]).strip() if idx < len(names) and names[idx] is not None else ""
        removed = (origins[idx] if idx < len(origins) else "") == ORIGIN_REMOVED
        result.append(card_origin(name, definition, removed, builtin_section))
    return result

def build_section_dict(
    names, types, file_vals, pattern_vals, group_id_vals, key_vals, op_vals,
    unit_vals, format_vals, error_vals, multiple_vals, origins=None,
    builtin_section=None,
):
    """
    Build the workspace content of one section from its card field values:
    a name -> definition dict, where a metric excluded from the export maps to
    None.

    A card left exactly as the built-in metric defines it is not written at all:
    the workspace file holds only what it changes, so a built-in metric Odatix
    later improves keeps improving unless you took it over.
    """
    result = {}
    nb = len(names) if isinstance(names, list) else 0
    for idx in range(nb):
        name = str(names[idx]).strip() if idx < len(names) and names[idx] is not None else ""
        if name == "":
            continue
        origin = origins[idx] if origins is not None and idx < len(origins) else ORIGIN_WORKSPACE
        if origin == ORIGIN_REMOVED:
            result[name] = None
            continue
        definition = build_metric_definition(
            types[idx] if idx < len(types) else "regex",
            file_vals[idx] if idx < len(file_vals) else "",
            pattern_vals[idx] if idx < len(pattern_vals) else "",
            group_id_vals[idx] if idx < len(group_id_vals) else "",
            key_vals[idx] if idx < len(key_vals) else "",
            op_vals[idx] if idx < len(op_vals) else "",
            unit_vals[idx] if idx < len(unit_vals) else "",
            format_vals[idx] if idx < len(format_vals) else "",
            error_vals[idx] if idx < len(error_vals) else [True],
            multiple_vals[idx] if idx < len(multiple_vals) else [],
        )
        if card_origin(name, definition, False, builtin_section) == ORIGIN_BUILTIN:
            continue
        result[name] = definition
    return result


######################################
# UI Components
######################################

def metric_title(name, is_tool=False, mode="workflow"):
    if is_tool:
        settings_link = f"/tool_editor?tool={name}"
        settings_text = "Tool Settings"
        settings_tooltip = "Back to the Tool Editor for this tool"
        back_link = f"/tool_editor?tool={name}" if name else "/tools"
        empty_text = "No tool selected"
    elif mode == "simulation":
        settings_link = f"/sim_editor?sim={name}"
        settings_text = "Simulation Settings"
        settings_tooltip = "Back to the Simulation Editor for this simulation"
        back_link = f"/sim_editor?sim={name}" if name else "/architectures"
        empty_text = "No simulation selected"
    else:
        settings_link = f"/workflow_editor?workflow={name}"
        settings_text = "Workflow Settings"
        settings_tooltip = "Back to the Workflow Editor for this workflow"
        back_link = f"/workflow_editor?workflow={name}" if name else "/workflows"
        empty_text = "No workflow selected"

    title_buttons = html.Div(
        children=[
            ui.icon_button(
                id="button-open-workflow-editor",
                icon=icon("gear", className="icon blue"),
                text=settings_text,
                tooltip=settings_tooltip,
                tooltip_options="bottom delay",
                color="default",
                link=settings_link,
                multiline=False,
                width="150px",
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
                                html.H3(
                                    f"{name}" if name else empty_text,
                                    id="metric-workflow-title",
                                    style={"marginBottom": "0px"},
                                )
                            ],
                            id="metric-workflow-title-container",
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
                ui.back_button(link=back_link),
            ],
            className="tile title",
            style={"position": "relative"},
        ),
        className="card-matrix config",
        style={"marginTop": "0px", "marginBottom": "10px"},
    )

def metric_field(prefix, var, name, label, value="", placeholder="", type="text", options=None, default_style=Style.hidden, tooltip="", disabled=False):
    return html.Div(
        children=[
            html.Div(
                children=[
                    html.Label(label, style={"fontWeight": "bold", "fontSize": "1em"}),
                    ui.tooltip_icon(tooltip) if tooltip else None,
                    dcc.Input(
                        value=value,
                        type=type,
                        placeholder=placeholder,
                        disabled=disabled,
                        id={"type": f"{prefix}-field-{name}", "name": var},
                        className="value-input",
                        style={
                            "width": "calc(100% - 10px)",
                            "marginLeft": "5px",
                            "marginRight": "5px",
                            "marginBottom": "5px",
                            "fontSize": "0.9em",
                            "height": "10px",
                            "zIndex": "900",
                            "padding": "15px 10px",
                        },
                    ) if options is None else dcc.Dropdown(
                        id={"type": f"{prefix}-field-{name}", "name": var},
                        options=options,
                        value=value,
                        clearable=False,
                        disabled=disabled,
                        style={"fontSize": "0.95em", "zIndex": "900", "width": "100%"},
                    ),
                ],
                style={"marginTop": "5px", "width": "100%"},
            ),
        ],
        id={"type": f"{prefix}-field-{name}-div", "name": var},
        style=default_style,
    )

def origin_note_children(origin, has_builtin):
    """The badge content of a card: what your workspace says about that metric."""
    note = ORIGIN_NOTES.get(origin) if has_builtin else None
    if note is None:
        return []
    return [html.Span(note[0]), ui.tooltip_icon(note[1])]

def origin_note_style(origin, has_builtin):
    """The badge style: hidden for a metric there is nothing to say about."""
    if not has_builtin or origin not in ORIGIN_NOTES:
        return {"display": "none"}
    return {
        "display": "flex",
        "alignItems": "center",
        "fontSize": "0.75em",
        "opacity": "0.75" if origin != ORIGIN_BUILTIN else "0.6",
        "color": "var(--theme-warning-color)" if origin != ORIGIN_BUILTIN else "inherit",
        "textTransform": "uppercase",
        "letterSpacing": "0.05em",
        "whiteSpace": "nowrap",
        "margin": "0 6px",
    }

def metric_card(
    prefix,
    name,
    type_value="regex",
    file_value="", pattern_value="", group_id_value="", key_value="", op_value="",
    unit_value="", format_value="", error_if_missing_value=True, multiple_value=False,
    origin=ORIGIN_WORKSPACE,
    has_builtin=None,
):
    """
    One metric card. Every field is editable, whatever the metric is: editing a
    built-in metric writes an override in the workspace, it never touches what
    Odatix ships.

    `origin` (see ORIGIN_*) is what the card is when it is rendered, shown as a
    badge and recomputed live while the fields are edited. `has_builtin` says
    whether a built-in metric of that name exists, which is what the reset
    button goes back to; it defaults to what `origin` implies.

    Every card carries all of its buttons, hidden when they do not apply, so
    each button list stays aligned with the card list in the callbacks.
    """
    removed = origin == ORIGIN_REMOVED
    if has_builtin is None:
        has_builtin = origin in (ORIGIN_BUILTIN, ORIGIN_REMOVED)
    # A removed metric is not edited: its fields are shown greyed out, as the
    # built-in definition the reset button brings back.
    read_only = removed

    def button_style(shown):
        return {"display": "flex", "alignItems": "center"} if shown else {"display": "none"}

    return html.Div([
        html.Div([
            dcc.Input(
                value=origin,
                type="text",
                id={"type": f"{prefix}-origin", "name": name},
                style={"display": "none"},
            ),
            dcc.Input(
                value=name,
                type="text",
                disabled=read_only,
                id={"type": f"{prefix}-title", "name": name},
                className="title-input",
                style={
                    "width": "calc(100% - 20px)",
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
            dcc.Dropdown(
                id={"type": f"{prefix}-type", "name": name},
                options=METRIC_TYPE_OPTIONS,
                value=type_value,
                clearable=False,
                disabled=read_only,
                style={"width": "100%"},
            ),
            html.Div(
                children=[
                    metric_field(prefix, name, "file", "File", value=file_value, default_style=field_style("file", type_value), disabled=read_only,
                                 tooltip="File (relative to the run directory) the value is extracted from."),
                    metric_field(prefix, name, "pattern", "Pattern", value=pattern_value, default_style=field_style("pattern", type_value), disabled=read_only,
                                 tooltip="Regular expression to search for in the file."),
                    metric_field(prefix, name, "group_id", "Group ID", value=group_id_value, type="number", default_style=field_style("group_id", type_value), disabled=read_only,
                                 tooltip="Index of the regex capture group to use as the value."),
                    metric_field(prefix, name, "key", "Key", value=key_value, default_style=field_style("key", type_value), disabled=read_only,
                                 tooltip="Column (CSV), key (YAML/JSON) or element path (XML, e.g. 'timing/slack' or 'cell@area') to read the value from. Leave empty for the whole file."),
                    metric_field(prefix, name, "op", "Operation", value=op_value, default_style=field_style("op", type_value), disabled=read_only,
                                 tooltip="Expression evaluated from other metric values (e.g. area / frequency)."),
                    html.Div(
                        children=[
                            metric_field(prefix, name, "unit", "Unit", value=unit_value, default_style=Style.visible, disabled=read_only,
                                         tooltip="Optional unit displayed with the metric."),
                            metric_field(prefix, name, "format", "Format", value=format_value, default_style=Style.visible, disabled=read_only,
                                         tooltip="Optional printf-style format applied to the numeric value (e.g. %.2f)."),
                            html.Div(
                                children=[
                                    dcc.Checklist(
                                        options=[{"label": "Error if missing", "value": True, "disabled": read_only}],
                                        value=[True] if error_if_missing_value else [],
                                        id={"type": f"{prefix}-field-error_if_missing", "name": name},
                                        className="checklist-switch",
                                        style={"marginTop": "8px", "marginBottom": "4px", "display": "inline-block"},
                                    ),
                                    ui.tooltip_icon("If checked, an error is raised when the value cannot be extracted. If unchecked, the run is simply skipped for this field."),
                                    dcc.Checklist(
                                        options=[{"label": "Multiple values", "value": True, "disabled": read_only}],
                                        value=[True] if multiple_value else [],
                                        id={"type": f"{prefix}-field-multiple", "name": name},
                                        className="checklist-switch",
                                        style={"marginBottom": "4px", "display": "inline-block"},
                                    ),
                                    ui.tooltip_icon("Extract every match as a list. The run then expands into one result entry per value, indexed by the metadata dimensions."),
                                ],
                            ),
                        ],
                        id={"type": f"{prefix}-more-field-div", "name": name},
                        className="expandable-area",
                        style=Style.hidden,
                    ),
                ],
                id={"type": f"{prefix}-fields-container", "name": name},
            ),
        ]),
        html.Div([
            html.Div([
                ui.icon_button(
                    icon=icon("more", className="icon normal rotate", id={"type": f"{prefix}-more-fields-icon", "name": name}),
                    color="default",
                    id={"type": f"{prefix}-more-fields", "name": name},
                    tooltip="Show/Hide extra fields",
                    tooltip_options="bottom small",
                )
            ], id={"type": f"{prefix}-more-fields-div", "name": name}, style={"display": "flex", "alignItems": "center"}),
            # What your workspace holds for this metric, between the two button
            # groups of the card footer (see origin_note_style).
            html.Div(
                children=origin_note_children(origin, has_builtin),
                id={"type": f"{prefix}-origin-note", "name": name},
                style=origin_note_style(origin, has_builtin),
            ),
            html.Div([
                html.Div(
                    [ui.icon_button(
                        icon=icon("reset", className="icon default"),
                        color="default",
                        id={"type": f"{prefix}-reset", "name": name},
                        tooltip="Reset to the built-in metric: drop what your workspace says about it",
                        tooltip_options="bottom auto",
                    )],
                    id={"type": f"{prefix}-reset-div", "name": name},
                    style=button_style(has_builtin),
                ),
                html.Div(
                    [ui.duplicate_button(
                        id={"type": f"{prefix}-duplicate", "name": name},
                        tooltip="Duplicate into a metric of your own",
                    )],
                    style=button_style(not removed),
                ),
                html.Div(
                    [ui.delete_button(
                        id={"type": f"{prefix}-delete", "name": name},
                        tooltip="Exclude this built-in metric from the exported results"
                                if has_builtin else "Delete",
                    )],
                    style=button_style(not removed),
                ),
            ], style={"display": "flex", "flexDirection": "row", "alignItems": "center", "gap": "5px"}),
        ], style={
            "marginTop": "8px",
            "display": "flex",
            "flexDirection": "row",
            "width": "100%",
            "justifyContent": "space-between",
        }),
    ],
    className="card configs",
    id={"type": f"{prefix}-card", "name": name},
    style={
        "padding": "10px",
        "margin": "5px",
        "display": "inline-block",
        "verticalAlign": "top",
        **({"opacity": "0.55"} if removed else {}),
    })

def add_card(prefix, text):
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
        className="card configs add hover",
        id=f"{prefix}-add-card",
        style={
            "padding": "10px",
            "margin": "5px",
            "display": "inline-block",
            "verticalAlign": "top",
            "boxSizing": "border-box",
        },
    )

def metric_card_from_def(prefix, name, definition, origin=ORIGIN_WORKSPACE, has_builtin=None):
    return metric_card(
        prefix,
        name=name,
        origin=origin,
        has_builtin=has_builtin,
        **card_fields_of(definition),
    )

def cards_from_section(prefix, entries, add_text):
    """
    Build the card row of a section from an ordered list of
    (name, definition, origin, has_builtin) tuples. A plain {name: definition}
    mapping is accepted too and read as metrics with no built-in counterpart
    (workflow mode).
    """
    cards = []
    if isinstance(entries, dict):
        entries = [(name, definition, ORIGIN_WORKSPACE, False) for name, definition in entries.items()]
    for name, definition, origin, has_builtin in entries or []:
        cards.append(metric_card_from_def(prefix, name, definition, origin=origin, has_builtin=has_builtin))
    cards.append(add_card(prefix, add_text))
    return cards


def section_entries(builtin_section, workspace_section):
    """
    The cards to show for one section: every built-in metric, in the order the
    built-in file declares them, overridden or removed by what the workspace
    metrics.yml says about it, followed by the metrics only the workspace has.

    Returns a list of (name, definition, origin, has_builtin) tuples.
    """
    builtin_section = builtin_section if isinstance(builtin_section, dict) else {}
    workspace_section = workspace_section if isinstance(workspace_section, dict) else {}

    entries = []
    for name, definition in builtin_section.items():
        if name not in workspace_section:
            entries.append((name, definition, ORIGIN_BUILTIN, True))
        elif workspace_section[name] is None:
            entries.append((name, definition, ORIGIN_REMOVED, True))
        else:
            entries.append((name, workspace_section[name], ORIGIN_WORKSPACE, True))

    for name, definition in workspace_section.items():
        if name in builtin_section:
            continue
        # A "removed" entry for a metric that no longer exists built-in is stale:
        # show it as a metric of the workspace rather than hiding it silently.
        entries.append((name, definition if definition is not None else {}, ORIGIN_WORKSPACE, False))

    return entries


######################################
# Per-section callbacks (registered once per prefix)
######################################

def register_section_callbacks(prefix, name_stem, add_text):
    """Register the add/duplicate/delete, field-visibility and more-fields
    toggle callbacks for one section, namespaced by its id prefix."""

    @dash.callback(
        Output(f"{prefix}-cards-row", "children", allow_duplicate=True),
        Input(f"{prefix}-new", "n_clicks"),
        Input({"type": f"{prefix}-duplicate", "name": dash.ALL}, "n_clicks"),
        Input({"type": f"{prefix}-delete", "name": dash.ALL}, "n_clicks"),
        Input({"type": f"{prefix}-reset", "name": dash.ALL}, "n_clicks"),
        State(f"{prefix}-cards-row", "children"),
        State({"type": f"{prefix}-type", "name": dash.ALL}, "value"),
        State({"type": f"{prefix}-field-file", "name": dash.ALL}, "value"),
        State({"type": f"{prefix}-field-pattern", "name": dash.ALL}, "value"),
        State({"type": f"{prefix}-field-group_id", "name": dash.ALL}, "value"),
        State({"type": f"{prefix}-field-key", "name": dash.ALL}, "value"),
        State({"type": f"{prefix}-field-op", "name": dash.ALL}, "value"),
        State({"type": f"{prefix}-field-unit", "name": dash.ALL}, "value"),
        State({"type": f"{prefix}-field-format", "name": dash.ALL}, "value"),
        State({"type": f"{prefix}-field-error_if_missing", "name": dash.ALL}, "value"),
        State({"type": f"{prefix}-field-multiple", "name": dash.ALL}, "value"),
        State({"type": f"{prefix}-origin", "name": dash.ALL}, "value"),
        State("metric-builtin", "data"),
        prevent_initial_call=True,
    )
    def update_cards(
        new_click, duplicate_clicks, delete_clicks, reset_clicks, cards,
        types, file_vals, pattern_vals, group_id_vals, key_vals, op_vals,
        unit_vals, format_vals, error_vals, multiple_vals, origins, builtin_data,
    ):
        trigger_id = ctx.triggered_id

        if cards is None:
            cards = []

        # The built-in definitions of this section, to rebuild a card as Odatix
        # defines it when its override is reset or dropped.
        builtin_defs = {}
        if isinstance(builtin_data, dict):
            section = builtin_data.get(prefix)
            if isinstance(section, dict):
                builtin_defs = section

        def card_values(idx):
            """The current field values of the card at `idx`, as a definition."""
            return dict(
                type_value=types[idx] if idx < len(types) else "regex",
                file_value=file_vals[idx] if idx < len(file_vals) else "",
                pattern_value=pattern_vals[idx] if idx < len(pattern_vals) else "",
                group_id_value=group_id_vals[idx] if idx < len(group_id_vals) else "",
                key_value=key_vals[idx] if idx < len(key_vals) else "",
                op_value=op_vals[idx] if idx < len(op_vals) else "",
                unit_value=unit_vals[idx] if idx < len(unit_vals) else "",
                format_value=format_vals[idx] if idx < len(format_vals) else "",
                error_if_missing_value=_checked(error_vals[idx]) if idx < len(error_vals) else True,
                multiple_value=_checked(multiple_vals[idx]) if idx < len(multiple_vals) else False,
            )

        # Remove the Add card if present
        if cards and isinstance(cards[-1], dict) and cards[-1].get("props", {}).get("id") == f"{prefix}-add-card":
            cards = cards[:-1]

        if trigger_id == f"{prefix}-new" and new_click:
            existing_names = [
                card.get("props", {}).get("id", {}).get("name", "")
                for card in cards if isinstance(card.get("props", {}).get("id", {}), dict)
            ]
            idx = 1
            while f"{name_stem}{idx}" in existing_names:
                idx += 1
            cards.append(metric_card(prefix, name=f"{name_stem}{idx}"))

        if isinstance(trigger_id, dict):
            trig_type = trigger_id.get("type")
            trig_name = trigger_id.get("name")

            idx = None
            for i, card in enumerate(cards):
                card_id = card.get("props", {}).get("id", {})
                if isinstance(card_id, dict) and card_id.get("type") == f"{prefix}-card" and card_id.get("name") == trig_name:
                    idx = i
                    break

            if trig_type == f"{prefix}-delete" and idx is not None and idx < len(delete_clicks) and delete_clicks[idx]:
                if trig_name in builtin_defs:
                    # Deleting a metric that also exists built-in does not make it
                    # disappear: it excludes the built-in one from the export, and
                    # the card stays, greyed out, for the reset button to bring
                    # back.
                    cards[idx] = metric_card_from_def(
                        prefix, trig_name, builtin_defs[trig_name], origin=ORIGIN_REMOVED
                    )
                else:
                    cards = [
                        card for card in cards
                        if not (
                            isinstance(card.get("props", {}).get("id", {}), dict)
                            and card.get("props", {}).get("id", {}).get("type") == f"{prefix}-card"
                            and card.get("props", {}).get("id", {}).get("name") == trig_name
                        )
                    ]
            elif trig_type == f"{prefix}-reset" and idx is not None and idx < len(reset_clicks) and reset_clicks[idx]:
                # Back to what Odatix defines: whatever the workspace said about
                # this metric (an override or its removal) is dropped.
                cards[idx] = metric_card_from_def(
                    prefix, trig_name, builtin_defs.get(trig_name, {}), origin=ORIGIN_BUILTIN
                )
            elif trig_type == f"{prefix}-duplicate" and idx is not None and idx < len(duplicate_clicks) and duplicate_clicks[idx]:
                existing_names = [
                    card.get("props", {}).get("id", {}).get("name", "")
                    for card in cards if isinstance(card.get("props", {}).get("id", {}), dict)
                ]
                copy_idx = 1
                while f"{trig_name}_copy{copy_idx}" in existing_names:
                    copy_idx += 1
                new_name = f"{trig_name}_copy{copy_idx}"
                # A copy is a metric of your own, even when made from a built-in
                # card: no built-in metric goes by that new name.
                cards.append(metric_card(
                    prefix,
                    name=new_name,
                    origin=ORIGIN_WORKSPACE,
                    has_builtin=False,
                    **card_values(idx),
                ))

        cards.append(add_card(prefix, add_text))
        return cards

    @dash.callback(
        Output({"type": f"{prefix}-origin-note", "name": dash.ALL}, "children"),
        Output({"type": f"{prefix}-origin-note", "name": dash.ALL}, "style"),
        Output({"type": f"{prefix}-reset-div", "name": dash.ALL}, "style"),
        Input({"type": f"{prefix}-title", "name": dash.ALL}, "value"),
        Input({"type": f"{prefix}-type", "name": dash.ALL}, "value"),
        Input({"type": f"{prefix}-field-file", "name": dash.ALL}, "value"),
        Input({"type": f"{prefix}-field-pattern", "name": dash.ALL}, "value"),
        Input({"type": f"{prefix}-field-group_id", "name": dash.ALL}, "value"),
        Input({"type": f"{prefix}-field-key", "name": dash.ALL}, "value"),
        Input({"type": f"{prefix}-field-op", "name": dash.ALL}, "value"),
        Input({"type": f"{prefix}-field-unit", "name": dash.ALL}, "value"),
        Input({"type": f"{prefix}-field-format", "name": dash.ALL}, "value"),
        Input({"type": f"{prefix}-field-error_if_missing", "name": dash.ALL}, "value"),
        Input({"type": f"{prefix}-field-multiple", "name": dash.ALL}, "value"),
        Input({"type": f"{prefix}-origin", "name": dash.ALL}, "value"),
        Input("metric-builtin", "data"),
    )
    def update_origin_notes(
        names, types, file_vals, pattern_vals, group_id_vals, key_vals, op_vals,
        unit_vals, format_vals, error_vals, multiple_vals, origins, builtin_data,
    ):
        """
        Keep each card's badge (and its reset button) in step with what is being
        typed: a built-in metric becomes "overridden" as soon as one of its
        fields differs from the built-in definition, and goes back to "built-in"
        when it matches again, so what saving will write is never a surprise.
        """
        builtin_defs = {}
        if isinstance(builtin_data, dict):
            section = builtin_data.get(prefix)
            if isinstance(section, dict):
                builtin_defs = section

        definitions = section_definitions(
            names, types, file_vals, pattern_vals, group_id_vals, key_vals, op_vals,
            unit_vals, format_vals, error_vals, multiple_vals,
        )
        card_states = card_origins(names, definitions, origins, builtin_defs)

        children, styles, reset_styles = [], [], []
        for idx, origin in enumerate(card_states):
            name = str(names[idx]).strip() if names[idx] is not None else ""
            has_builtin = name in builtin_defs
            children.append(origin_note_children(origin, has_builtin))
            styles.append(origin_note_style(origin, has_builtin))
            reset_styles.append(
                {"display": "flex", "alignItems": "center"} if has_builtin else {"display": "none"}
            )
        return children, styles, reset_styles

    # Which fields an extraction type uses, and folding the extra fields of a
    # card away, are done on the client (assets/metric_editor.js): neither is a
    # question the server has an answer to, and the fields of a card would
    # otherwise be rewritten by the server a moment after the card is rendered.
    # The fold has no callback at all -- it is a click handler on the document.
    page_clientside_callback(
        PAGE_SCOPE,
        dash.ClientsideFunction(namespace="odatix_metric_editor", function_name="field_visibility"),
        [
            Output({"type": f"{prefix}-field-{field}-div", "name": dash.ALL}, "style")
            for field in METRIC_FIELDS
        ],
        Input({"type": f"{prefix}-type", "name": dash.ALL}, "value"),
        *[
            State({"type": f"{prefix}-field-{field}-div", "name": dash.ALL}, "style")
            for field in METRIC_FIELDS
        ],
    )


register_section_callbacks(METRIC_PREFIX, "metric", "Add new metric")
register_section_callbacks(META_PREFIX, "meta", "Add new metadata")
register_section_callbacks(THIRD_PREFIX, "metric", "Add new metric")


######################################
# Page-level callbacks
######################################

def _section_title_children(sections):
    """Title tiles for the (up to three) sections, keyed by their card-row prefix."""
    children = {METRIC_PREFIX: None, META_PREFIX: None, THIRD_PREFIX: None}
    for prefix, label, tooltip, _key in sections:
        children[prefix] = ui.title_tile(text=label, id=f"{prefix}-section-title", tooltip=tooltip)
    return children

@dash.callback(
    Output({"page": page_path, "type": "metric-title-div"}, "children"),
    Output(f"{METRIC_PREFIX}-section-title-div", "children"),
    Output(f"{META_PREFIX}-section-title-div", "children"),
    Output(f"{THIRD_PREFIX}-section-title-div", "children"),
    Output(f"{THIRD_PREFIX}-section-wrapper", "style"),
    Output(f"{METRIC_PREFIX}-cards-row", "children"),
    Output(f"{META_PREFIX}-cards-row", "children"),
    Output(f"{THIRD_PREFIX}-cards-row", "children"),
    Output("metric-initial", "data"),
    Output("metric-builtin", "data"),
    Input(f"url_{page_path}", "search"),
    State(f"url_{page_path}", "pathname"),
    State("odatix-settings", "data"),
)
def init_page(search, page, odatix_settings):
    if page != page_path:
        return (dash.no_update,) * 10

    tool_name = get_key_from_url(search, "tool")
    workflow_name = get_key_from_url(search, "workflow")
    simulation_name = get_key_from_url(search, "simulation")
    is_tool = bool(tool_name)
    is_simulation = (not is_tool) and bool(simulation_name)
    mode = "tool" if is_tool else ("simulation" if is_simulation else "workflow")
    name = tool_name if is_tool else (simulation_name if is_simulation else workflow_name)

    sections = _sections_for_mode(is_tool)
    titles = _section_title_children(sections)
    third_style = {"display": "block"} if is_tool else {"display": "none"}

    # Load the definitions for each section (empty when nothing selected).
    # In tool mode the cards show both layers: what Odatix defines (read-only)
    # and what the workspace metrics.yml adds, overrides or removes. Only the
    # workspace layer is edited and saved.
    builtin_defs = {prefix: {} for prefix in (METRIC_PREFIX, META_PREFIX, THIRD_PREFIX)}
    entries = {}
    if is_tool and name:
        tools_path = get_workspace(odatix_settings).paths.tools_path
        builtin, workspace_metrics = metrics_lib.load_metrics_layers(name, tools_path=tools_path)
        section_defs = {prefix: workspace_metrics.get(key, {}) for prefix, _l, _t, key in sections}
        for prefix, _l, _t, key in sections:
            builtin_defs[prefix] = builtin.get(key, {})
            entries[prefix] = section_entries(builtin.get(key, {}), workspace_metrics.get(key, {}))
    elif (not is_tool) and name:
        ws = get_workspace(odatix_settings)
        instances = ws.simulations if is_simulation else ws.workflows
        metrics_file = instances.entry(name).metrics
        metrics, metadata = metrics_file.metrics, metrics_file.metadata
        by_key = {"metrics": metrics, "metadata": metadata}
        section_defs = {prefix: by_key.get(key, {}) for prefix, _l, _t, key in sections}
        entries = {prefix: section_defs[prefix] for prefix, _l, _t, _k in sections}
    else:
        section_defs = {prefix: {} for prefix, _l, _t, _k in sections}
        entries = dict(section_defs)

    rows = {}
    for prefix, _l, _t, _key in sections:
        rows[prefix] = cards_from_section(prefix, entries.get(prefix, {}), "Add new metric")
    # Prefixes not used by this mode still need a valid (empty) card row.
    for prefix in (METRIC_PREFIX, META_PREFIX, THIRD_PREFIX):
        if prefix not in rows:
            rows[prefix] = [add_card(prefix, "Add new metric")]

    initial = {
        "mode": mode,
        "sections": {prefix: section_defs.get(prefix, {}) for prefix, _l, _t, _k in sections},
    }

    return (
        metric_title(name, is_tool=is_tool, mode=mode),
        titles[METRIC_PREFIX],
        titles[META_PREFIX],
        titles[THIRD_PREFIX],
        third_style,
        rows[METRIC_PREFIX],
        rows[META_PREFIX],
        rows[THIRD_PREFIX],
        initial,
        builtin_defs,
    )

@page_callback(PAGE_SCOPE,
    Output({"page": page_path, "action": "save-all"}, "className"),
    Output({"page": page_path, "action": "save-all"}, "data-tooltip"),
    Output("metric-saved", "data"),
    Input({"page": page_path, "action": "save-all"}, "n_clicks"),
    # Metrics section
    Input({"type": f"{METRIC_PREFIX}-title", "name": dash.ALL}, "value"),
    Input({"type": f"{METRIC_PREFIX}-type", "name": dash.ALL}, "value"),
    Input({"type": f"{METRIC_PREFIX}-field-file", "name": dash.ALL}, "value"),
    Input({"type": f"{METRIC_PREFIX}-field-pattern", "name": dash.ALL}, "value"),
    Input({"type": f"{METRIC_PREFIX}-field-group_id", "name": dash.ALL}, "value"),
    Input({"type": f"{METRIC_PREFIX}-field-key", "name": dash.ALL}, "value"),
    Input({"type": f"{METRIC_PREFIX}-field-op", "name": dash.ALL}, "value"),
    Input({"type": f"{METRIC_PREFIX}-field-unit", "name": dash.ALL}, "value"),
    Input({"type": f"{METRIC_PREFIX}-field-format", "name": dash.ALL}, "value"),
    Input({"type": f"{METRIC_PREFIX}-field-error_if_missing", "name": dash.ALL}, "value"),
    Input({"type": f"{METRIC_PREFIX}-field-multiple", "name": dash.ALL}, "value"),
    Input({"type": f"{METRIC_PREFIX}-origin", "name": dash.ALL}, "value"),
    # Metadata section
    Input({"type": f"{META_PREFIX}-title", "name": dash.ALL}, "value"),
    Input({"type": f"{META_PREFIX}-type", "name": dash.ALL}, "value"),
    Input({"type": f"{META_PREFIX}-field-file", "name": dash.ALL}, "value"),
    Input({"type": f"{META_PREFIX}-field-pattern", "name": dash.ALL}, "value"),
    Input({"type": f"{META_PREFIX}-field-group_id", "name": dash.ALL}, "value"),
    Input({"type": f"{META_PREFIX}-field-key", "name": dash.ALL}, "value"),
    Input({"type": f"{META_PREFIX}-field-op", "name": dash.ALL}, "value"),
    Input({"type": f"{META_PREFIX}-field-unit", "name": dash.ALL}, "value"),
    Input({"type": f"{META_PREFIX}-field-format", "name": dash.ALL}, "value"),
    Input({"type": f"{META_PREFIX}-field-error_if_missing", "name": dash.ALL}, "value"),
    Input({"type": f"{META_PREFIX}-field-multiple", "name": dash.ALL}, "value"),
    Input({"type": f"{META_PREFIX}-origin", "name": dash.ALL}, "value"),
    # Third section (tool "common metrics"; unused/empty in workflow mode)
    Input({"type": f"{THIRD_PREFIX}-title", "name": dash.ALL}, "value"),
    Input({"type": f"{THIRD_PREFIX}-type", "name": dash.ALL}, "value"),
    Input({"type": f"{THIRD_PREFIX}-field-file", "name": dash.ALL}, "value"),
    Input({"type": f"{THIRD_PREFIX}-field-pattern", "name": dash.ALL}, "value"),
    Input({"type": f"{THIRD_PREFIX}-field-group_id", "name": dash.ALL}, "value"),
    Input({"type": f"{THIRD_PREFIX}-field-key", "name": dash.ALL}, "value"),
    Input({"type": f"{THIRD_PREFIX}-field-op", "name": dash.ALL}, "value"),
    Input({"type": f"{THIRD_PREFIX}-field-unit", "name": dash.ALL}, "value"),
    Input({"type": f"{THIRD_PREFIX}-field-format", "name": dash.ALL}, "value"),
    Input({"type": f"{THIRD_PREFIX}-field-error_if_missing", "name": dash.ALL}, "value"),
    Input({"type": f"{THIRD_PREFIX}-field-multiple", "name": dash.ALL}, "value"),
    Input({"type": f"{THIRD_PREFIX}-origin", "name": dash.ALL}, "value"),
    State(f"url_{page_path}", "search"),
    State(f"url_{page_path}", "pathname"),
    State("metric-initial", "data"),
    State("metric-saved", "data"),
    State("metric-builtin", "data"),
    State("odatix-settings", "data"),
    prevent_initial_call=True,
)
def save_and_status(
    n_clicks,
    m_names, m_types, m_file, m_pattern, m_group_id, m_key, m_op, m_unit, m_format, m_error, m_multiple, m_origin,
    d_names, d_types, d_file, d_pattern, d_group_id, d_key, d_op, d_unit, d_format, d_error, d_multiple, d_origin,
    t_names, t_types, t_file, t_pattern, t_group_id, t_key, t_op, t_unit, t_format, t_error, t_multiple, t_origin,
    search, page, initial, saved, builtin_data, odatix_settings,
):
    triggered_id = ctx.triggered_id
    if triggered_id == f"url_{page_path}" and page != page_path:
        return dash.no_update, dash.no_update, dash.no_update

    disabled = ("color-button disabled icon-button tooltip delay bottom small", "Nothing to save")
    warning = ("color-button warning icon-button tooltip bottom small", "Unsaved changes!")
    error = "color-button error-status icon-button tooltip bottom small"

    tool_name = get_key_from_url(search, "tool")
    workflow_name = get_key_from_url(search, "workflow")
    simulation_name = get_key_from_url(search, "simulation")
    is_tool = bool(tool_name)
    is_simulation = (not is_tool) and bool(simulation_name)
    mode = "tool" if is_tool else ("simulation" if is_simulation else "workflow")
    sections = _sections_for_mode(is_tool)

    section_fields = {
        METRIC_PREFIX: (m_names, m_types, m_file, m_pattern, m_group_id, m_key, m_op, m_unit, m_format, m_error, m_multiple, m_origin),
        META_PREFIX: (d_names, d_types, d_file, d_pattern, d_group_id, d_key, d_op, d_unit, d_format, d_error, d_multiple, d_origin),
        THIRD_PREFIX: (t_names, t_types, t_file, t_pattern, t_group_id, t_key, t_op, t_unit, t_format, t_error, t_multiple, t_origin),
    }

    builtin_sections = builtin_data if isinstance(builtin_data, dict) else {}

    # Build what the workspace holds for each section used by the current mode:
    # the metrics of its own, the built-in ones it changes, and the ones it
    # removes. A card left as the built-in metric defines it writes nothing.
    current_sections = {}
    for prefix, label, _t, _key in sections:
        fields = section_fields[prefix]
        builtin_section = builtin_sections.get(prefix)
        current_sections[prefix] = build_section_dict(
            *fields, builtin_section=builtin_section if isinstance(builtin_section, dict) else {}
        )

        # Reject empty / duplicate names in this section.
        seen = set()
        for name in (fields[0] or []):
            clean = str(name).strip() if name is not None else ""
            if clean == "":
                return error, f"{label} name cannot be empty", dash.no_update
            for character in hard_settings.invalid_filename_characters:
                if character in clean and character != " ":
                    return error, f"Unauthorized character in {label} name: '{character}'", dash.no_update
            if clean in seen:
                return error, f"Duplicate {label} name: '{clean}'", dash.no_update
            seen.add(clean)

    current = {"mode": mode, "sections": current_sections}

    reference = saved if saved is not None else initial
    if not isinstance(reference, dict) or "sections" not in reference:
        reference = {"mode": current["mode"], "sections": {p: {} for p, _l, _t, _k in sections}}

    if triggered_id == {"page": page_path, "action": "save-all"}:
        if is_tool:
            if not tool_name:
                return error, "No tool selected", dash.no_update
            key_sections = {key: current_sections[prefix] for prefix, _l, _t, key in sections}
            try:
                tool_metrics = get_workspace(odatix_settings).tools.entry(tool_name).metrics
                tool_metrics.sections = key_sections
                tool_metrics.save()
                return disabled[0], disabled[1], current
            except Exception:
                return error, "Failed to save...", dash.no_update
        elif is_simulation:
            try:
                metrics_file = get_workspace(odatix_settings).simulations.entry(simulation_name).metrics
                metrics_file.metrics = current_sections.get(METRIC_PREFIX, {})
                metrics_file.metadata = current_sections.get(META_PREFIX, {})
                metrics_file.save()
                return disabled[0], disabled[1], current
            except Exception:
                return error, "Failed to save...", dash.no_update
        else:
            if not workflow_name:
                return error, "No workflow selected", dash.no_update
            try:
                metrics_file = get_workspace(odatix_settings).workflows.entry(workflow_name).metrics
                metrics_file.metrics = current_sections.get(METRIC_PREFIX, {})
                metrics_file.metadata = current_sections.get(META_PREFIX, {})
                metrics_file.save()
                return disabled[0], disabled[1], current
            except Exception:
                return error, "Failed to save...", dash.no_update

    if current.get("sections") != reference.get("sections"):
        return warning[0], warning[1], dash.no_update

    return disabled[0], disabled[1], dash.no_update


######################################
# Layout
######################################

def _section_block(prefix, default_title, default_tooltip, wrapper_style=None):
    """One editable section: a dynamic title tile placeholder + its cards row."""
    return html.Div(
        children=[
            html.Div(
                id=f"{prefix}-section-title-div",
                children=ui.title_tile(text=default_title, id=f"{prefix}-section-title", tooltip=default_tooltip),
            ),
            html.Div([
                html.Div(
                    id=f"{prefix}-cards-row",
                    children=[add_card(prefix, "Add new metric")],
                    className="card-matrix configs",
                    style={"marginBottom": "30px"},
                ),
            ]),
        ],
        id=f"{prefix}-section-wrapper",
        style=wrapper_style or {},
    )

layout = html.Div(
    children=[
        dcc.Location(id=f"url_{page_path}"),
        html.Div(id={"page": page_path, "type": "metric-title-div"}, style={"marginTop": "20px"}),
        _section_block(METRIC_PREFIX, "Metrics", METRIC_TOOLTIP),
        _section_block(META_PREFIX, "Metadata Dimensions", META_TOOLTIP),
        _section_block(THIRD_PREFIX, "Common metrics", COMMON_TOOLTIP, wrapper_style={"display": "none"}),
        dcc.Store(id="metric-initial", data={"mode": "workflow", "sections": {}}),
        dcc.Store(id="metric-saved", data=None),
        # The built-in definitions of each section, kept so a deleted override
        # or a restored metric can be rendered back as a read-only card.
        dcc.Store(id="metric-builtin", data={}),
    ],
    className="page-content",
    style={
        "padding": "0 16%",
        "display": "flex",
        "flexDirection": "column",
        "min-height": f"calc(100vh - {navigation.top_bar_height})",
    },
)

# Anchor of PAGE_SCOPE: makes this page the only one dispatching its callbacks.
layout = scoped(PAGE_SCOPE, layout)
