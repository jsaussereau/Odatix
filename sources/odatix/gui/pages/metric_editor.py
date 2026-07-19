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

Edits the metrics definition file ("_metrics.yml") of a workflow, i.e. how the
workflow results are extracted from each run at export time (see
odatix.components.export_workflow_results). Reached from the Workflow Editor via
its "Edit Metrics" button (/metric_editor?workflow={workflow_name}).

The page has two independent sections, stored under the "metrics" and "metadata"
keys of the same "_metrics.yml" file:
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

import odatix.components.workspace as workspace
from odatix.gui.icons import icon
from odatix.gui.utils import get_key_from_url
from odatix.gui.css_helper import Style
import odatix.gui.ui_components as ui
import odatix.gui.navigation as navigation
import odatix.lib.hard_settings as hard_settings
from odatix.lib.settings import OdatixSettings

page_path = "/metric_editor"

dash.register_page(
    __name__,
    path=page_path,
    title="Odatix - Exported Metrics Editor",
    name="Exported Metrics Editor",
    order=6,
)

# The two sections and the "_metrics.yml" key each of them is stored under.
METRIC_PREFIX = "metric"
META_PREFIX = "metadata"

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

# Metric extraction types and the fields each of them uses.
METRIC_TYPE_OPTIONS = [
    {"label": "Regex", "value": "regex"},
    {"label": "CSV", "value": "csv"},
    {"label": "YAML", "value": "yaml"},
    {"label": "JSON", "value": "json"},
    {"label": "Operation", "value": "operation"},
]

# Fields shown for each extraction type, in render order.
METRIC_FIELDS = ["file", "pattern", "group_id", "key", "op"]

FIELD_VISIBILITY = {
    "regex":     {"file", "pattern", "group_id"},
    "csv":       {"file", "key"},
    "yaml":      {"file", "key"},
    "json":      {"file", "key"},
    "operation": {"op"},
}


######################################
# Helpers
######################################

def _get_workflow_path(odatix_settings):
    workflow_path = odatix_settings.get("workflow_path", "") if isinstance(odatix_settings, dict) else ""
    if workflow_path:
        return workflow_path

    settings_data = OdatixSettings.get_settings_file_dict(silent=True)
    if isinstance(settings_data, dict):
        return settings_data.get("workflow_path", OdatixSettings.DEFAULT_WORKFLOW_PATH)

    return OdatixSettings.DEFAULT_WORKFLOW_PATH

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
    elif metric_type in ("csv", "yaml", "json"):
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

def build_section_dict(
    names, types, file_vals, pattern_vals, group_id_vals, key_vals, op_vals,
    unit_vals, format_vals, error_vals, multiple_vals,
):
    """Build a name -> definition dict from one section's card field values."""
    result = {}
    nb = len(names) if isinstance(names, list) else 0
    for idx in range(nb):
        name = str(names[idx]).strip() if idx < len(names) and names[idx] is not None else ""
        if name == "":
            continue
        result[name] = build_metric_definition(
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
    return result


######################################
# UI Components
######################################

def metric_title(workflow_name):
    title_buttons = html.Div(
        children=[
            ui.icon_button(
                id="button-open-workflow-editor",
                icon=icon("gear", className="icon blue"),
                text="Workflow Settings",
                tooltip="Back to the Workflow Editor for this workflow",
                tooltip_options="bottom delay",
                color="default",
                link=f"/workflow_editor?workflow={workflow_name}",
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
                                    f"{workflow_name}" if workflow_name else "No workflow selected",
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
                ui.back_button(link=f"/workflow_editor?workflow={workflow_name}" if workflow_name else "/workflows"),
            ],
            className="tile title",
            style={"position": "relative"},
        ),
        className="card-matrix config",
        style={"marginTop": "0px", "marginBottom": "10px"},
    )

def metric_field(prefix, var, name, label, value="", placeholder="", type="text", options=None, default_style=Style.hidden, tooltip=""):
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
                        style={"fontSize": "0.95em", "zIndex": "900", "width": "100%"},
                    ),
                ],
                style={"marginTop": "5px", "width": "100%"},
            ),
        ],
        id={"type": f"{prefix}-field-{name}-div", "name": var},
        style=default_style,
    )

def metric_card(
    prefix,
    name,
    type_value="regex",
    file_value="", pattern_value="", group_id_value="", key_value="", op_value="",
    unit_value="", format_value="", error_if_missing_value=True, multiple_value=False,
):
    return html.Div([
        html.Div([
            dcc.Input(
                value=name,
                type="text",
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
                style={"width": "100%"},
            ),
            html.Div(
                children=[
                    metric_field(prefix, name, "file", "File", value=file_value, default_style=Style.visible,
                                 tooltip="File (relative to the run directory) the value is extracted from."),
                    metric_field(prefix, name, "pattern", "Pattern", value=pattern_value,
                                 tooltip="Regular expression to search for in the file."),
                    metric_field(prefix, name, "group_id", "Group ID", value=group_id_value, type="number",
                                 tooltip="Index of the regex capture group to use as the value."),
                    metric_field(prefix, name, "key", "Key", value=key_value,
                                 tooltip="Column (CSV) or key (YAML/JSON) to read the value from. Leave empty for the whole file."),
                    metric_field(prefix, name, "op", "Operation", value=op_value,
                                 tooltip="Expression evaluated from other metric values (e.g. area / frequency)."),
                    html.Div(
                        children=[
                            metric_field(prefix, name, "unit", "Unit", value=unit_value, default_style=Style.visible,
                                         tooltip="Optional unit displayed with the metric."),
                            metric_field(prefix, name, "format", "Format", value=format_value, default_style=Style.visible,
                                         tooltip="Optional printf-style format applied to the numeric value (e.g. %.2f)."),
                            html.Div(
                                children=[
                                    dcc.Checklist(
                                        options=[{"label": "Error if missing", "value": True}],
                                        value=[True] if error_if_missing_value else [],
                                        id={"type": f"{prefix}-field-error_if_missing", "name": name},
                                        className="checklist-switch",
                                        style={"marginTop": "8px", "marginBottom": "4px", "display": "inline-block"},
                                    ),
                                    ui.tooltip_icon("If checked, an error is raised when the value cannot be extracted. If unchecked, the run is simply skipped for this field."),
                                    dcc.Checklist(
                                        options=[{"label": "Multiple values", "value": True}],
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
                id=f"{prefix}-fields-container",
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
            html.Div([
                ui.duplicate_button(id={"type": f"{prefix}-duplicate", "name": name}),
                ui.delete_button(id={"type": f"{prefix}-delete", "name": name}),
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
    })

def add_card(prefix, text):
    return html.Div(
        html.Div(
            html.Div(
                children=[
                    html.Div(text, style={"fontWeight": "bold", "fontSize": "1.2em", "paddingTop": "20px"}),
                    html.Div("+", style={"fontSize": "2.5em", "lineHeight": "80px", "height": "80px"}),
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

def metric_card_from_def(prefix, name, definition):
    d = definition if isinstance(definition, dict) else {}
    settings = d.get("settings", {})
    if not isinstance(settings, dict):
        settings = {}
    return metric_card(
        prefix,
        name=name,
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

def cards_from_section(prefix, definitions, add_text):
    cards = []
    if isinstance(definitions, dict):
        for name, definition in definitions.items():
            cards.append(metric_card_from_def(prefix, name, definition))
    cards.append(add_card(prefix, add_text))
    return cards


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
        prevent_initial_call=True,
    )
    def update_cards(
        new_click, duplicate_clicks, delete_clicks, cards,
        types, file_vals, pattern_vals, group_id_vals, key_vals, op_vals,
        unit_vals, format_vals, error_vals, multiple_vals,
    ):
        trigger_id = ctx.triggered_id

        if cards is None:
            cards = []

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
                cards = [
                    card for card in cards
                    if not (
                        isinstance(card.get("props", {}).get("id", {}), dict)
                        and card.get("props", {}).get("id", {}).get("type") == f"{prefix}-card"
                        and card.get("props", {}).get("id", {}).get("name") == trig_name
                    )
                ]
            elif trig_type == f"{prefix}-duplicate" and idx is not None and idx < len(duplicate_clicks) and duplicate_clicks[idx]:
                existing_names = [
                    card.get("props", {}).get("id", {}).get("name", "")
                    for card in cards if isinstance(card.get("props", {}).get("id", {}), dict)
                ]
                copy_idx = 1
                while f"{trig_name}_copy{copy_idx}" in existing_names:
                    copy_idx += 1
                new_name = f"{trig_name}_copy{copy_idx}"
                cards.append(metric_card(
                    prefix,
                    name=new_name,
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
                ))

        cards.append(add_card(prefix, add_text))
        return cards

    @dash.callback(
        [
            Output({"type": f"{prefix}-field-file-div", "name": dash.ALL}, "style"),
            Output({"type": f"{prefix}-field-pattern-div", "name": dash.ALL}, "style"),
            Output({"type": f"{prefix}-field-group_id-div", "name": dash.ALL}, "style"),
            Output({"type": f"{prefix}-field-key-div", "name": dash.ALL}, "style"),
            Output({"type": f"{prefix}-field-op-div", "name": dash.ALL}, "style"),
        ],
        Input({"type": f"{prefix}-type", "name": dash.ALL}, "value"),
    )
    def update_fields_visibility(types):
        styles_by_field = {field: [] for field in METRIC_FIELDS}
        for metric_type in types:
            visible = FIELD_VISIBILITY.get(metric_type, set())
            for field in METRIC_FIELDS:
                styles_by_field[field].append(Style.visible if field in visible else Style.hidden)
        return (
            styles_by_field["file"],
            styles_by_field["pattern"],
            styles_by_field["group_id"],
            styles_by_field["key"],
            styles_by_field["op"],
        )

    @dash.callback(
        Output({"type": f"{prefix}-more-field-div", "name": dash.ALL}, "style"),
        Output({"type": f"{prefix}-more-fields-icon", "name": dash.ALL}, "className"),
        Input({"type": f"{prefix}-more-fields", "name": dash.ALL}, "n_clicks"),
        State({"type": f"{prefix}-more-field-div", "name": dash.ALL}, "style"),
        State({"type": f"{prefix}-more-fields-icon", "name": dash.ALL}, "className"),
        State({"type": f"{prefix}-title", "name": dash.ALL}, "value"),
    )
    def toggle_more_fields(n_clicks, expandable_area_styles, icon_classes, names):
        trigger_id = ctx.triggered_id
        if not isinstance(trigger_id, dict) or "name" not in trigger_id:
            return [dash.no_update] * len(n_clicks), [dash.no_update] * len(n_clicks)

        index = None
        for i, current_name in enumerate(names):
            if trigger_id.get("name") == current_name:
                index = i
                break

        new_styles = list(expandable_area_styles)
        new_classes = list(icon_classes)
        if index is not None:
            if n_clicks[index] % 2 == 0:
                new_styles[index] = Style.hidden
                new_classes[index] = "icon normal rotate"
            else:
                new_styles[index] = Style.visible
                new_classes[index] = "icon normal rotate rotated"
        return new_styles, new_classes


register_section_callbacks(METRIC_PREFIX, "metric", "Add new metric")
register_section_callbacks(META_PREFIX, "meta", "Add new metadata")


######################################
# Page-level callbacks
######################################

@dash.callback(
    Output({"page": page_path, "type": "metric-title-div"}, "children"),
    Output(f"{METRIC_PREFIX}-cards-row", "children"),
    Output(f"{META_PREFIX}-cards-row", "children"),
    Output("metric-initial", "data"),
    Input(f"url_{page_path}", "search"),
    State(f"url_{page_path}", "pathname"),
    State("odatix-settings", "data"),
)
def init_page(search, page, odatix_settings):
    if page != page_path:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update

    workflow_name = get_key_from_url(search, "workflow")
    if not workflow_name:
        return (
            metric_title(""),
            [add_card(METRIC_PREFIX, "Add new metric")],
            [add_card(META_PREFIX, "Add new metadata")],
            {"metrics": {}, "metadata": {}},
        )

    workflow_path = _get_workflow_path(odatix_settings)
    metrics, metadata = workspace.load_workflow_metrics(workflow_path, workflow_name)
    return (
        metric_title(workflow_name),
        cards_from_section(METRIC_PREFIX, metrics, "Add new metric"),
        cards_from_section(META_PREFIX, metadata, "Add new metadata"),
        {"metrics": metrics, "metadata": metadata},
    )

@dash.callback(
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
    State(f"url_{page_path}", "search"),
    State(f"url_{page_path}", "pathname"),
    State("metric-initial", "data"),
    State("metric-saved", "data"),
    State("odatix-settings", "data"),
    prevent_initial_call=True,
)
def save_and_status(
    n_clicks,
    m_names, m_types, m_file, m_pattern, m_group_id, m_key, m_op, m_unit, m_format, m_error, m_multiple,
    d_names, d_types, d_file, d_pattern, d_group_id, d_key, d_op, d_unit, d_format, d_error, d_multiple,
    search, page, initial, saved, odatix_settings,
):
    triggered_id = ctx.triggered_id
    if triggered_id == f"url_{page_path}" and page != page_path:
        return dash.no_update, dash.no_update, dash.no_update

    disabled = ("color-button disabled icon-button tooltip delay bottom small", "Nothing to save")
    warning = ("color-button warning icon-button tooltip bottom small", "Unsaved changes!")
    error = "color-button error-status icon-button tooltip bottom small"

    metrics = build_section_dict(
        m_names, m_types, m_file, m_pattern, m_group_id, m_key, m_op, m_unit, m_format, m_error, m_multiple,
    )
    metadata = build_section_dict(
        d_names, d_types, d_file, d_pattern, d_group_id, d_key, d_op, d_unit, d_format, d_error, d_multiple,
    )
    current = {"metrics": metrics, "metadata": metadata}

    reference = saved if saved is not None else initial
    if not isinstance(reference, dict):
        reference = {"metrics": {}, "metadata": {}}

    # Reject empty / duplicate names, per section.
    for label, section_names in (("metric", m_names or []), ("metadata", d_names or [])):
        seen = set()
        for name in section_names:
            clean = str(name).strip() if name is not None else ""
            if clean == "":
                return error, f"{label.capitalize()} name cannot be empty", dash.no_update
            for character in hard_settings.invalid_filename_characters:
                if character in clean and character != " ":
                    return error, f"Unauthorized character in {label} name: '{character}'", dash.no_update
            if clean in seen:
                return error, f"Duplicate {label} name: '{clean}'", dash.no_update
            seen.add(clean)

    workflow_name = get_key_from_url(search, "workflow")

    if triggered_id == {"page": page_path, "action": "save-all"}:
        if not workflow_name:
            return error, "No workflow selected", dash.no_update
        workflow_path = _get_workflow_path(odatix_settings)
        try:
            workspace.save_workflow_metrics(workflow_path, workflow_name, metrics, metadata)
            return disabled[0], disabled[1], current
        except Exception:
            return error, "Failed to save...", dash.no_update

    if current != reference:
        return warning[0], warning[1], dash.no_update

    return disabled[0], disabled[1], dash.no_update


######################################
# Layout
######################################

layout = html.Div(
    children=[
        dcc.Location(id=f"url_{page_path}"),
        html.Div(id={"page": page_path, "type": "metric-title-div"}, style={"marginTop": "20px"}),
        ui.title_tile(
            text="Metrics",
            id="metric-section-title",
            tooltip=METRIC_TOOLTIP,
        ),
        html.Div([
            html.Div(
                id=f"{METRIC_PREFIX}-cards-row",
                children=[add_card(METRIC_PREFIX, "Add new metric")],
                className="card-matrix configs",
                style={"marginBottom": "30px"},
            ),
        ]),
        ui.title_tile(
            text="Metadata Dimensions",
            id="metadata-section-title",
            tooltip=META_TOOLTIP,
        ),
        html.Div([
            html.Div(
                id=f"{META_PREFIX}-cards-row",
                children=[add_card(META_PREFIX, "Add new metadata")],
                className="card-matrix configs",
                style={"marginBottom": "30px"},
            ),
        ]),
        dcc.Store(id="metric-initial", data={"metrics": {}, "metadata": {}}),
        dcc.Store(id="metric-saved", data=None),
    ],
    className="page-content",
    style={
        "padding": "0 16%",
        "display": "flex",
        "flexDirection": "column",
        "min-height": f"calc(100vh - {navigation.top_bar_height})",
    },
)
