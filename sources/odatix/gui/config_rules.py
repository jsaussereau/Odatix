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
The rules of a parameter domain, edited in place inside the configuration
editor.

A domain either holds configuration files written by hand, or describes its
configurations with a name template, a content template and a set of variables
-- or both, since a file always wins over what a rule produces. This module is
the second half of that: the panel that edits the rules, one per parameter
domain, folded away until asked for.

It used to be a page of its own ("/config_generator"), reached from the domain
it belonged to and generating files as its only way of doing anything. There is
nothing to generate any more -- a run resolves what the rules describe -- so
what was a separate step is now part of editing the domain, next to the
configurations it produces.

Every component id carries the uuid of its domain (see the ``scope`` argument of
odatix.gui.variable_editor), so several domains edit their rules side by side on
the same page.
"""

import re

import dash
from dash import html, dcc, Input, Output, State, ctx
from natsort import natsorted

import odatix.gui.ui_components as ui
import odatix.gui.variable_editor as ve
from odatix.gui.css_helper import Style
from odatix.gui.icons import icon
from odatix.gui.utils import get_instance_collection_context
import odatix.lib.hard_settings as hard_settings
from odatix.workspace.domains import ParameterDomain
from odatix.workspace.configs import CONFIGURATIONS_KEY
from odatix.workspace.configs import CONFIG_EXTENSION
from odatix.workspace.space import (
    ORIGIN_BLACKLISTED, ORIGIN_EDITED, ORIGIN_GENERATED, config_set_rules, implicit_config_name,
    implicit_template,
)
from odatix.gui.page_scope import page_callback

# Scope anchoring the callbacks below: they are dispatched only on the pages
# embedding the matching anchor store (see odatix.gui.page_scope).
PAGE_SCOPE = "config_editor"

#: Id namespace of the variable cards of this editor.
VE_PREFIX = "cfg-"

#: The page these panels live in. Kept as a literal rather than imported from
#: the page module, which imports this one.
PAGE_PATH = "/config_editor"

#: What a domain with no rules yet starts from, once the user asks for rules.
DEFAULT_NAME = "${var}"
DEFAULT_TEMPLATE = "${var}"
DEFAULT_VARIABLE_SETTINGS = {"type": "range", "settings": {"from": 1, "to": 4, "step": 1}}

#: What a variable may be called, so that ``${name}`` resolves to it.
VARIABLE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def default_variable_name(taken=()):
    """
    What a variable is called until it is renamed: "var", then "var2", "var3"...
    The first one of a domain is what the templates spell by default.
    """
    candidate = "var"
    index = 1
    while candidate in taken:
        index += 1
        candidate = "var{0}".format(index)
    return candidate


def default_variables():
    """The variables a domain starts from: one, called "var"."""
    return {default_variable_name(): dict(DEFAULT_VARIABLE_SETTINGS)}


######################################
# Settings <-> form
######################################

def configuration_blacklist(settings):
    """The generated configuration names explicitly excluded by saved rules."""
    configurations = (settings or {}).get(CONFIGURATIONS_KEY, {})
    blacklist = configurations.get("blacklist", ()) if isinstance(configurations, dict) else ()
    if not isinstance(blacklist, (list, tuple, set)):
        return []
    return [str(name) for name in blacklist if str(name)]


def rules_settings(name, template, variables, enabled=False, blacklist=()):
    """The settings block a domain writes to say how it describes its configurations."""
    configurations = {
        "name": name or "",
        "template": template or "",
    }
    if enabled:
        configurations["enabled"] = True
    if blacklist:
        configurations["blacklist"] = list(blacklist)
    return {
        CONFIGURATIONS_KEY: configurations,
        "variables": variables,
    }


def configuration_defaults_enabled(settings):
    """Whether the saved rules explicitly choose both implicit templates."""
    configurations = (settings or {}).get(CONFIGURATIONS_KEY, {})
    return isinstance(configurations, dict) and bool(configurations.get("enabled"))


def form_rules_settings(name, template, variables, domain_name, saved=None):
    """The rules the form currently means, including the main-domain defaults."""
    enabled = configuration_defaults_enabled(saved) or (
        domain_name == hard_settings.main_parameter_domain
        and bool(variables)
        and not name
        and not template
    )
    return rules_settings(
        name, template, variables, enabled=enabled,
        blacklist=configuration_blacklist(saved),
    )


def effective_rules(name, template, variables, implicit=True, blacklist=()):
    """
    The rules as Odatix reads them, from what the form holds: a domain of a
    single variable says everything by declaring it, and both templates are
    then filled in for it (see :func:`implicit_template`).
    """
    return config_set_rules(
        rules_settings(name, template, variables, blacklist=blacklist), implicit=implicit,
    )


def rules_of_settings(settings, implicit=True):
    """
    The name template, the content template and the variables a domain's
    settings describe.

    Every way Odatix has had of saying this is read here -- by the same
    function the runtime reads them with -- so a workspace written before the
    "configurations" block opens with its rules already filled in, and saving
    writes them the way they are written now.
    """
    space = config_set_rules(settings or {}, implicit=implicit)
    # As the form will hand them back, so that a panel whose rules are exactly
    # what its file says does not open showing unsaved changes. What the file
    # leaves unsaid stays unsaid: an implicit template is a placeholder of the
    # field, not text to put in it.
    variables = ve.normalized_variables(dict(space.variables))
    name = "" if space.implicit_name else space.name
    template = "" if space.implicit_template or space.template is None else space.template
    return name, template, variables


def describes_configurations(settings, implicit=True):
    """Whether these settings describe configurations at all."""
    return config_set_rules(settings or {}, implicit=implicit).generates


######################################
# UI Components
######################################

def add_variable_card(domain_uuid):
    """The last row of the list: one more variable, in the shape of the others."""
    return html.Div(
        html.Div(
            children=[
                html.Div("+", style={"fontSize": "1.6em", "lineHeight": "1"}),
                html.Div("Add new variable", style={"fontWeight": "bold"}),
            ],
            id={"type": "cfg-new-variable", "domain_uuid": domain_uuid},
            n_clicks=0,
            style={"display": "flex", "alignItems": "center", "gap": "10px",
                   "textDecoration": "none", "width": "100%"},
        ),
        className="card configs add hover odx-variable-row odx-variable-add",
        id={"type": "cfg-add-variable-card", "domain_uuid": domain_uuid},
        style={
            "padding": "10px 12px",
            "margin": "8px 0px",
            "display": "block",
            "width": "auto",
            "boxSizing": "border-box",
        },
    )


def rules_form(domain_uuid, name, template, variables=None, implicit=True):
    """The two templates: what a configuration is called, and what it writes."""
    # A domain does not have to write either of them down: the placeholder is
    # then what Odatix would actually use, not an example.
    # Either field left empty means the same thing in every domain, the main one
    # included: the values themselves. The placeholders say so.
    implicit_name = implicit_config_name(variables or {})
    implicit_content = implicit_template(variables or {})
    return html.Div(
        children=[
            html.Div([
                html.Label("Configuration name"),
                ui.tooltip_icon(
                    "How the configurations of this domain are named. Use a variable name prefixed by a dollar sign "
                    "and enclosed in curly braces (e.g. ${width}) where its value belongs. The '.txt' extension is not required. "
                    "Leaving this empty names the configurations after the values themselves, joined by an underscore when there are several variables."
                ),
                dcc.Input(
                    id={"type": "cfg-gen-name", "domain_uuid": domain_uuid},
                    value=name,
                    type="text",
                    placeholder=implicit_name or DEFAULT_NAME,
                    # The ${...} of both templates are highlighted, in the color
                    # of what they resolve to among the variables of this very
                    # domain (see assets/variable_highlight.js and the scope the
                    # panel declares).
                    className="odatix-command-field",
                    style={"width": "100%", "fontFamily": "monospace", "fontWeight": "500"},
                ),
            ], style={"marginBottom": "12px"}),
            html.Div([
                html.Label("Content template"),
                ui.tooltip_icon(
                    "What each configuration writes between the delimiters, with ${variable_name} replaced by its value. "
                    "Leaving this empty writes the values themselves, one per line."
                ),
                dcc.Textarea(
                    id={"type": "cfg-gen-template", "domain_uuid": domain_uuid},
                    value=template,
                    className="auto-resize-textarea odatix-command-field",
                    placeholder=implicit_content or DEFAULT_TEMPLATE,
                    style={"width": "calc(100% - 12px)", "resize": "none", "fontFamily": "monospace", "fontWeight": "500"},
                ),
            ], style={"marginBottom": "12px"}),
        ],
    )


def advanced_section(domain_uuid, name, template, variables, implicit, open=False):
    """
    The two templates, behind a fold: a domain says everything by declaring its
    variables, and only a domain that names or writes its configurations some
    other way has to open this.

    Folded by the same Show/Hide button the rest of the editor uses -- a "more"
    icon that rotates -- rather than by a header of its own that happens to be
    clickable.
    """
    return html.Div(
        children=[
            html.Div(
                children=[
                    ui.icon_button(
                        icon=icon(
                            "more",
                            className="icon normal rotate rotated" if open else "icon normal rotate",
                            id={"type": "cfg-advanced-icon", "domain_uuid": domain_uuid},
                        ),
                        color="default",
                        id={"type": "cfg-advanced-toggle", "domain_uuid": domain_uuid},
                        tooltip="Show/Hide the name and content templates",
                        tooltip_options="bottom small",
                    ),
                    html.H3("Advanced", style={"margin": "0px"}),
                ],
                style={"display": "flex", "alignItems": "center", "gap": "10px", "flexWrap": "wrap"},
            ),
            html.Div(
                children=[
                    html.Span(
                        "how a configuration is named and what it contains",
                        style={"opacity": "0.65", "fontSize": "13px"},
                    ),
                    rules_form(domain_uuid, name, template, variables, implicit),
                ],
                id={"type": "cfg-advanced-panel", "domain_uuid": domain_uuid},
                style={"marginTop": "12px"} if open else Style.hidden,
            ),
        ],
        style={"marginTop": "10px"},
    )


def domain_advanced_section(domain_uuid, settings, domain_name=None):
    """
    The two templates of a domain, folded, as the configuration-parameters tile
    shows them: they say what is written into the target file set right above,
    which is the one place they belong.
    """
    name, template, variables = rules_of_settings(settings)
    return advanced_section(
        domain_uuid, name, template, variables, True,
        # Opened by itself only when it holds something: templates already
        # written. Empty, it stays folded, main domain included.
        open=bool(name or template),
    )


def rules_section(domain_uuid, settings, open=False, domain_name=None):
    """
    The variables of one parameter domain, and what they add up to.

    No fold of its own any more: a variable is a row saying its name, its type
    and the values it takes, so the whole list is readable at a glance and there
    is nothing to hide it behind. The two templates it feeds are edited next to
    the target file, under "Advanced" (see :func:`advanced_section`), which is
    where the rest of what the replacement does is set up.

    ``open`` is kept for callers that used to open this panel; nothing is folded
    here now.
    """
    space = config_set_rules(settings or {}, implicit=True)
    name, template, variables = rules_of_settings(settings)
    has_rules = space.generates
    # Counted here as well as by the preview callback, so the header says what
    # the domain holds from the first paint rather than a moment later.
    try:
        count = space.count() if has_rules else None
    except Exception:
        count = None

    # A page shows every domain of an instance at once, so each variable is a
    # folded row: its name, its type and its values on one line.
    cards = ve.variable_cards_from_dict(VE_PREFIX, variables, scope={"domain_uuid": domain_uuid}, collapsible=True)
    cards.append(add_variable_card(domain_uuid))

    header = html.Div(
        children=[
            html.Div(
                children=[
                    html.H3("Variables", style={"margin": "0px"}),
                    html.Div(
                        rules_summary(has_rules, len(variables), count),
                        id={"type": "cfg-rules-summary", "domain_uuid": domain_uuid},
                        style={"display": "flex", "alignItems": "center", "gap": "10px"},
                    ),
                ],
                style={"display": "flex", "alignItems": "center", "gap": "10px", "flexWrap": "wrap"},
            ),
            html.Div(
                children=[
                    ui.icon_button(
                        icon=icon("save", className="icon"),
                        color="disabled",
                        text="Save rules",
                        width="120px",
                        id={"type": "cfg-save-rules", "domain_uuid": domain_uuid},
                        tooltip="Nothing to save",
                        tooltip_options="bottom auto caution",
                    ),
                ],
                className="inline-flex-buttons",
            ),
        ],
        style={"display": "flex", "alignItems": "center", "justifyContent": "space-between", "gap": "10px"},
    )

    return html.Div(
        children=[
            # In a grid, like every other title of the page: a "tile title"
            # centers itself with justify-self, which does nothing outside one.
            html.Div(
                html.Div([header], className="tile title", style={"marginTop": "10px"}),
                className="card-matrix config",
            ),
            html.Div(
                children=cards,
                id={"type": "cfg-variable-cards-row", "domain_uuid": domain_uuid},
                className="card-matrix configs odx-variable-list",
            ),
            # What is saved on disk, and what the dirty state is measured against.
            dcc.Store(
                id={"type": "cfg-rules-store", "domain_uuid": domain_uuid},
                data=rules_settings(
                    name, template, variables,
                    enabled=configuration_defaults_enabled(settings),
                    blacklist=configuration_blacklist(settings),
                ),
            ),
            # Bumped on every save, so the configurations of the domain are read again.
            dcc.Store(id={"type": "cfg-rules-saved", "domain_uuid": domain_uuid}, data=0),
        ],
    )


def rules_summary(has_rules, variable_count, config_count):
    """The one-line state of a domain's rules, shown next to the fold."""
    if not has_rules:
        return [
            ui.badge("no rules"),
            html.Span("the configurations of this domain are the files it holds",
                      style={"opacity": "0.65", "fontSize": "13px"}),
        ]
    badges = []
    if config_count is not None:
        badges.append(ui.badge("{0} configurations".format(config_count), color="primary"))
    badges.append(html.Span(
        "from {0} variable{1}".format(variable_count, "" if variable_count == 1 else "s"),
        style={"opacity": "0.65", "fontSize": "13px"},
    ))
    return badges


######################################
# Grouping the fields of every domain
######################################

#: The variable-card patterns this module reads, in the order the callbacks
#: below take them. They all carry the same ids, so one order fits all.
FIELD_PATTERNS = [
    "variable-title", "variable-type",
    "variable-field-base", "variable-field-from", "variable-field-to",
    "variable-field-from_2_pow", "variable-field-to_2_pow",
    "variable-field-from_type", "variable-field-to_type",
    "variable-field-step", "variable-field-op", "variable-field-list",
    "variable-field-source", "variable-field-sources",
    "variable-field-format", "variable-field-group",
]


def variable_inputs():
    """The Input() list for every variable field, in FIELD_PATTERNS order."""
    return [Input({"type": VE_PREFIX + pattern, "name": dash.ALL, "domain_uuid": dash.ALL}, "value")
            for pattern in FIELD_PATTERNS]


def variable_states():
    """The same fields, as State()."""
    return [State({"type": VE_PREFIX + pattern, "name": dash.ALL, "domain_uuid": dash.ALL}, "value")
            for pattern in FIELD_PATTERNS]


def field_ids(pattern):
    """
    The ids Dash matched for one variable-field pattern, in the order the
    values came back. Every pattern of a variable card matches the same ids, so
    this is also the order of every other field list.
    """
    wanted = VE_PREFIX + pattern
    for group in list(ctx.inputs_list or []) + list(ctx.states_list or []):
        if isinstance(group, list) and group and isinstance(group[0], dict):
            if group[0].get("id", {}).get("type") == wanted:
                return [item.get("id", {}) for item in group]
    return []


def domain_indices(ids, domain_uuids):
    """Which entries of a flat field list belong to each domain, in order."""
    indices = {domain_uuid: [] for domain_uuid in domain_uuids}
    for i, identifier in enumerate(ids):
        domain_uuid = identifier.get("domain_uuid")
        if domain_uuid in indices:
            indices[domain_uuid].append(i)
    return indices


def variables_of(field_values, indices):
    """The variables dict of one domain, out of the flat field lists."""
    picked = [[values[i] if i < len(values) else "" for i in indices] for values in field_values]
    titles, types, base, frm, to, from_2, to_2, from_t, to_t, step, op, lst, source, sources, fmt, group = picked
    return ve.build_variables_dict(
        titles, types, base, frm, to, from_2, to_2, from_t, to_t, step, op, lst, source, sources, fmt, group,
    )


def domain_uuids_of(domain_metadata):
    return [data.get("domain_uuid", "") for data in (domain_metadata or [])]


def domain_names_of(domain_metadata):
    return {data.get("domain_uuid", ""): data.get("domain_name", "") for data in (domain_metadata or [])}


######################################
# Callbacks
######################################

@page_callback(PAGE_SCOPE,
    Output({"type": "cfg-advanced-panel", "domain_uuid": dash.ALL}, "style"),
    Output({"type": "cfg-advanced-icon", "domain_uuid": dash.ALL}, "className"),
    Input({"type": "cfg-advanced-toggle", "domain_uuid": dash.ALL}, "n_clicks"),
    State({"type": "cfg-advanced-panel", "domain_uuid": dash.ALL}, "style"),
    prevent_initial_call=True,
)
def toggle_advanced_panel(n_clicks, styles):
    """
    Show the two templates of a domain only when they are asked for.

    Read from what the panel shows now rather than from a click count: a section
    built open and a section built closed both start at zero clicks.
    """
    trigger = ctx.triggered_id
    if not isinstance(trigger, dict):
        return [dash.no_update] * len(styles), [dash.no_update] * len(styles)
    uuids = [item.get("id", {}).get("domain_uuid") for item in (ctx.inputs_list[0] if ctx.inputs_list else [])]
    try:
        index = uuids.index(trigger.get("domain_uuid"))
    except ValueError:
        return [dash.no_update] * len(styles), [dash.no_update] * len(styles)

    new_styles = [dash.no_update] * len(styles)
    new_classes = [dash.no_update] * len(styles)
    if index < len(styles):
        hidden = (styles[index] or {}).get("display") == "none"
        new_styles[index] = {"marginTop": "12px"} if hidden else dict(Style.hidden)
        new_classes[index] = "icon normal rotate rotated" if hidden else "icon normal rotate"
    return new_styles, new_classes


@page_callback(PAGE_SCOPE,
    [
        Output({"type": "cfg-variable-field-from-div", "name": dash.ALL, "domain_uuid": dash.ALL}, "style"),
        Output({"type": "cfg-variable-field-to-div", "name": dash.ALL, "domain_uuid": dash.ALL}, "style"),
        Output({"type": "cfg-variable-field-from_2_pow-div", "name": dash.ALL, "domain_uuid": dash.ALL}, "style"),
        Output({"type": "cfg-variable-field-to_2_pow-div", "name": dash.ALL, "domain_uuid": dash.ALL}, "style"),
        Output({"type": "cfg-variable-field-from_type-div", "name": dash.ALL, "domain_uuid": dash.ALL}, "style"),
        Output({"type": "cfg-variable-field-to_type-div", "name": dash.ALL, "domain_uuid": dash.ALL}, "style"),
        Output({"type": "cfg-variable-field-base-div", "name": dash.ALL, "domain_uuid": dash.ALL}, "style"),
        Output({"type": "cfg-variable-field-step-div", "name": dash.ALL, "domain_uuid": dash.ALL}, "style"),
        Output({"type": "cfg-variable-field-op-div", "name": dash.ALL, "domain_uuid": dash.ALL}, "style"),
        Output({"type": "cfg-variable-field-list-div", "name": dash.ALL, "domain_uuid": dash.ALL}, "style"),
        Output({"type": "cfg-variable-field-source-div", "name": dash.ALL, "domain_uuid": dash.ALL}, "style"),
        Output({"type": "cfg-variable-field-sources-div", "name": dash.ALL, "domain_uuid": dash.ALL}, "style"),
        Output({"type": "cfg-variable-field-format-div", "name": dash.ALL, "domain_uuid": dash.ALL}, "style"),
        Output({"type": "cfg-variable-field-group-div", "name": dash.ALL, "domain_uuid": dash.ALL}, "style"),
    ],
    Input({"type": "cfg-variable-type", "name": dash.ALL, "domain_uuid": dash.ALL}, "value"),
)
def update_variable_fields_visibility(types):
    """
    Show the fields the type of each variable actually uses. Every pattern here
    matches the same cards in the same order, whichever domain they belong to,
    so this needs no grouping.
    """
    styles_by_field = ve.field_styles_for_types(types)
    return [styles_by_field[field] for field in ve.VARIABLE_FIELDS]


@page_callback(PAGE_SCOPE,
    Output({"type": "cfg-variable-fields-container", "name": dash.ALL, "domain_uuid": dash.ALL}, "style"),
    Output({"type": "cfg-variable-collapse-icon", "name": dash.ALL, "domain_uuid": dash.ALL}, "className"),
    Input({"type": "cfg-variable-collapse", "name": dash.ALL, "domain_uuid": dash.ALL}, "n_clicks"),
    State({"type": "cfg-variable-fields-container", "name": dash.ALL, "domain_uuid": dash.ALL}, "style"),
    State({"type": "cfg-variable-collapse-icon", "name": dash.ALL, "domain_uuid": dash.ALL}, "className"),
    prevent_initial_call=True,
)
def toggle_variable_card(n_clicks, styles, icon_classes):
    """Fold one variable card away, or open it, leaving every other one alone."""
    trigger = ctx.triggered_id
    if not isinstance(trigger, dict):
        return [dash.no_update] * len(styles), [dash.no_update] * len(icon_classes)
    keys = [(item.get("id", {}).get("name"), item.get("id", {}).get("domain_uuid"))
            for item in (ctx.inputs_list[0] if ctx.inputs_list else [])]
    try:
        index = keys.index((trigger.get("name"), trigger.get("domain_uuid")))
    except ValueError:
        return [dash.no_update] * len(styles), [dash.no_update] * len(icon_classes)

    new_styles = [dash.no_update] * len(styles)
    new_classes = [dash.no_update] * len(icon_classes)
    if index < len(styles):
        # What it shows now, rather than a click count: a card built collapsed
        # and a card built open both start at zero clicks.
        hidden = (styles[index] or {}).get("display") == "none"
        new_styles[index] = {} if hidden else dict(Style.hidden)
        if index < len(icon_classes):
            new_classes[index] = "icon normal rotate rotated" if hidden else "icon normal rotate"
    return new_styles, new_classes


@page_callback(PAGE_SCOPE,
    Output({"type": "cfg-variable-cards-row", "domain_uuid": dash.ALL}, "children"),
    Input({"type": "cfg-new-variable", "domain_uuid": dash.ALL}, "n_clicks"),
    Input({"type": "cfg-duplicate-var", "name": dash.ALL, "domain_uuid": dash.ALL}, "n_clicks"),
    Input({"type": "cfg-delete-var", "name": dash.ALL, "domain_uuid": dash.ALL}, "n_clicks"),
    State({"type": "cfg-variable-cards-row", "domain_uuid": dash.ALL}, "children"),
    State({"type": "domain-metadata", "domain_uuid": dash.ALL}, "data"),
    *variable_states(),
    prevent_initial_call=True,
)
def update_variable_cards(new_clicks, duplicate_clicks, delete_clicks, rows, domain_metadata, *field_values):
    """Add, duplicate and delete the variables of one domain, leaving the others alone."""
    trigger = ctx.triggered_id
    if not isinstance(trigger, dict):
        return [dash.no_update] * len(rows)

    domain_uuid = trigger.get("domain_uuid", "")
    uuids = domain_uuids_of(domain_metadata)
    if domain_uuid not in uuids:
        return [dash.no_update] * len(rows)
    row_index = uuids.index(domain_uuid)
    if row_index >= len(rows):
        return [dash.no_update] * len(rows)

    cards = list(rows[row_index] or [])
    # The add card is always last, and is put back at the end.
    if cards and _card_type(cards[-1]) == "cfg-add-variable-card":
        cards = cards[:-1]

    names = [_card_name(card) for card in cards]
    scope = {"domain_uuid": domain_uuid}

    if trigger.get("type") == "cfg-new-variable":
        new_name = default_variable_name(names)
        # Collapsible like every other card of the page: the two lists the fold
        # callback reads are the same cards, in the same order.
        cards.append(ve.variable_card(VE_PREFIX, new_name, scope=scope, collapsible=True))

    elif trigger.get("type") == "cfg-delete-var":
        cards = [card for card in cards if _card_name(card) != trigger.get("name")]

    elif trigger.get("type") == "cfg-duplicate-var":
        source_name = trigger.get("name")
        index = 1
        while "{0}_copy{1}".format(source_name, index) in names:
            index += 1
        new_name = "{0}_copy{1}".format(source_name, index)
        # Duplicate what the form shows now, not what was last saved.
        ids = field_ids("variable-title")
        position = next(
            (i for i, identifier in enumerate(ids)
             if identifier.get("name") == source_name and identifier.get("domain_uuid") == domain_uuid),
            None,
        )
        if position is not None:
            def value(field):
                values = field_values[FIELD_PATTERNS.index(field)]
                return values[position] if position < len(values) else ""
            cards.append(ve.variable_card(
                VE_PREFIX,
                name=new_name,
                type_value=value("variable-type"),
                base_value=value("variable-field-base"),
                from_value=value("variable-field-from"),
                to_value=value("variable-field-to"),
                from_2_pow_value=value("variable-field-from_2_pow"),
                to_2_pow_value=value("variable-field-to_2_pow"),
                from_type_value=value("variable-field-from_type"),
                to_type_value=value("variable-field-to_type"),
                step_value=value("variable-field-step"),
                op_value=value("variable-field-op"),
                list_value=value("variable-field-list"),
                source_value=value("variable-field-source"),
                sources_value=value("variable-field-sources"),
                format_value=value("variable-field-format"),
                group_value=value("variable-field-group"),
                scope=scope,
                collapsible=True,
            ))

    cards.append(add_variable_card(domain_uuid))
    return [cards if i == row_index else dash.no_update for i in range(len(rows))]


def _card_id(card):
    """
    The id of a card, whichever side of the wire it comes from: a component
    when the section was just built, a plain dict when Dash sends it back.
    """
    if isinstance(card, dict):
        identifier = card.get("props", {}).get("id")
    else:
        identifier = getattr(card, "id", None)
    return identifier if isinstance(identifier, dict) else {}


def _card_type(card):
    return _card_id(card).get("type")


def _card_name(card):
    return _card_id(card).get("name")


@dash.callback(
    # The values of every variable, said on the row of that variable.
    Output({"type": "cfg-variable-values", "name": dash.ALL, "domain_uuid": dash.ALL}, "children"),
    Output({"type": "cfg-rules-summary", "domain_uuid": dash.ALL}, "children"),
    Output({"type": "cfg-config-preview", "domain_uuid": dash.ALL}, "children"),
    # Both fields say what leaving them empty would mean, and follow the
    # variables: a domain of a single variable needs neither template.
    Output({"type": "cfg-gen-name", "domain_uuid": dash.ALL}, "placeholder"),
    Output({"type": "cfg-gen-template", "domain_uuid": dash.ALL}, "placeholder"),
    Input({"type": "cfg-gen-name", "domain_uuid": dash.ALL}, "value"),
    Input({"type": "cfg-gen-template", "domain_uuid": dash.ALL}, "value"),
    Input({"type": "cfg-rules-store", "domain_uuid": dash.ALL}, "data"),
    # The preview cards follow the configuration cards below them, layout
    # included: they are the same list, one part of it not written yet.
    Input("config-layout-dropdown", "value"),
    *variable_inputs(),
    # Blacklisting a configuration replaces the cards of its domain. Their stores
    # are new components, which do not trigger a callback of their own, so the
    # row they live in is what says the domain changed: without it the preview
    # would keep describing the domain as it was before that click.
    Input({"type": "config-cards-row", "domain_uuid": dash.ALL}, "children"),
    # What the domain holds right now, to say what the edited rules would change
    # about it rather than listing everything they produce.
    State({"type": "config-metadata", "domain_uuid": dash.ALL, "config_uuid": dash.ALL}, "data"),
    State({"type": "domain-metadata", "domain_uuid": dash.ALL}, "data"),
)
def update_rules_preview(names, templates, stores, layout, *rest):
    """
    What the rules of each domain currently say: the values of every variable,
    how many configurations they add up to, and -- while they differ from what
    the settings file holds -- what they would change about the configurations
    of the domain, above them. This follows the form, not the file, so the
    effect of a change is visible before it is saved.
    """
    field_values = rest[:len(FIELD_PATTERNS)]
    config_metadata = rest[len(FIELD_PATTERNS) + 1] if len(rest) > len(FIELD_PATTERNS) + 1 else []
    domain_metadata = rest[len(FIELD_PATTERNS) + 2] if len(rest) > len(FIELD_PATTERNS) + 2 else []

    uuids = domain_uuids_of(domain_metadata)
    domain_names = domain_names_of(domain_metadata)
    title_ids = field_ids("variable-title")
    indices = domain_indices(title_ids, uuids)
    titles = field_values[0] if field_values else []

    # One entry per variable row of the page, in the order Dash matched them --
    # the same order every variable field comes back in.
    row_values = [[] for _ in title_ids]

    def say(domain_uuid, values=None, message=None):
        """What each row of one domain shows next to its name."""
        for position in indices.get(domain_uuid, []):
            if message is not None:
                row_values[position] = html.Span(message, className="odx-variable-values-empty")
                continue
            title = titles[position] if position < len(titles) else ""
            row_values[position] = variable_values_inline((values or {}).get(title))

    summaries = []
    config_previews = []
    placeholders = []
    for i, domain_uuid in enumerate(uuids):
        name = names[i] if i < len(names) else ""
        template = templates[i] if i < len(templates) else ""
        variables = variables_of(field_values, indices.get(domain_uuid, []))
        saved = stores[i] if i < len(stores) and stores[i] else rules_settings("", "", {})
        blacklist = configuration_blacklist(saved)
        space = effective_rules(name, template, variables, blacklist=blacklist)
        placeholders.append((
            implicit_config_name(variables),
            implicit_template(variables),
        ))
        # Once the form says what the file says, the configuration cards below
        # are the real thing: previewing them again would only be noise.
        current = form_rules_settings(name, template, variables, domain_names.get(domain_uuid), saved)
        unsaved = current != saved
        held = held_configurations(config_metadata, domain_uuid)
        if not space.generates:
            say(domain_uuid, message="no values")
            summaries.append(rules_summary(False, 0, None))
            # Dropping the rules takes every configuration they produced with
            # them: that is a change of the list, and is shown as one.
            config_previews.append(configurations_preview({}, held, layout) if unsaved else [])
            continue
        try:
            configurations = {point.name: point.content for point in space.points()}
            values = space.values()
        except Exception as error:
            say(domain_uuid, message=str(error) or "these rules cannot be resolved")
            summaries.append([ui.badge("invalid", color="caution")])
            config_previews.append([])
            continue
        say(domain_uuid, values=values)
        summaries.append(rules_summary(True, len(variables), len(configurations)))
        config_previews.append(configurations_preview(configurations, held, layout) if unsaved else [])
    return (
        row_values, summaries, config_previews,
        [name or DEFAULT_NAME for name, _ in placeholders],
        [template or DEFAULT_TEMPLATE for _, template in placeholders],
    )


#: How many configurations the preview shows before saying how many are left.
MAX_PREVIEW_CONFIGS = 8


def held_configurations(config_metadata, domain_uuid):
    """
    What one domain holds on the page, as ``(name, origin, content)`` in the
    order of its cards. The name is the one the rules speak in: a card names its
    file, and the ".txt" is a detail of how a configuration is stored.
    """
    held = []
    for data in (config_metadata or []):
        data = data or {}
        if data.get("domain_uuid") != domain_uuid:
            continue
        name = str(data.get("config_name", ""))
        if name.endswith(CONFIG_EXTENSION):
            name = name[:-len(CONFIG_EXTENSION)]
        held.append((name, data.get("origin", ""), data.get("config_content", "")))
    return held


#: What each origin says on a configuration card, and how it is presented. Kept
#: here rather than in the page, which imports this module: the preview labels
#: the configurations a domain holds exactly like the cards of that domain do.
ORIGIN_LABELS = {
    ORIGIN_GENERATED: ("generated", "primary",
        "Produced by the rules of this domain. Its name comes from the name template, so it cannot be renamed here — edit the rules instead."),
    ORIGIN_EDITED: ("edited", "warning",
        "Produced by the rules of this domain, then edited. This version is the one runs use, and generating again leaves it alone."),
    ORIGIN_BLACKLISTED: ("blacklisted", "caution",
        "Excluded from runs by this domain's configuration blacklist. Restore it to include it again."),
}


def preview_card(name, content, layout="normal", state="added", origin=""):
    """
    One configuration of the list the edited rules would leave behind, in the
    shape of the cards of the domain -- same grid, same silhouette.

    Four ways to be in that list. A configuration the rules would *add* is
    plainly unwritten: dashed, quiet, and holding a "preview" chip where a saved
    card holds its origin. One the domain *keeps* is what it already holds, said
    as its card says it, origin included. One whose generated *content changes*
    shows the replacement text. One the rules would *remove* is the same card on
    its way out: struck through and in the color of a warning.
    """
    wide = " wide" if layout == "wide" else ""
    if state == "removed":
        chip = ui.badge("removed", color="caution")
    elif state == "changed":
        chip = ui.badge("content changed", color="warning")
    elif state == "kept":
        # A hand-written configuration wears no badge on its own card; here,
        # where every other card says what it is, staying silent would read as
        # an oversight rather than as "nothing to say".
        text, color, _tooltip = ORIGIN_LABELS.get(origin, ("manual", "", ""))
        chip = ui.badge(text, color=color)
    else:
        chip = ui.badge("preview")
    return html.Div(
        children=[
            html.Div(name, className="odx-config-preview-title"),
            html.Pre(content, className="odx-config-preview-content"),
            html.Div(chip, className="odx-config-preview-footer"),
        ],
        className="card configs odx-config-preview-card odx-config-preview-{0}".format(state) + wide,
    )


def more_card(count, layout="normal"):
    wide = " wide" if layout == "wide" else ""
    return html.Div(
        html.Div([
            html.Span("+{0}".format(count), className="odx-stat-value"),
            html.Span("more", className="odx-stat-label"),
        ], className="odx-stat"),
        className="card configs odx-config-preview-card odx-config-preview-more" + wide,
    )


def configurations_preview(configurations, held, layout="normal"):
    """
    The list of configurations the edited rules would leave behind: the ones the
    domain keeps, the ones the rules add, and the ones they take away, together
    and in order.

    One list rather than a preview above the real one: what matters about a
    change is the list it results in, and reading it means seeing the new
    configurations in their place among the old, not gathered apart from them.
    While this is shown, the cards of the domain are hidden behind it (see
    ``.odx-configs-diff`` in the stylesheet) -- otherwise a configuration on its
    way out would appear twice, once as itself and once as its own removal.

    A configuration written by hand is never taken away by a rule, so it is
    always kept -- only what the rules themselves produced can stop being
    produced or change content.
    """
    names = set(configurations)
    holds = {name for name, _, _ in (held or [])}
    added = [name for name in configurations if name not in holds]
    removed = [name for name, origin, _ in (held or [])
               if origin in (ORIGIN_GENERATED, ORIGIN_EDITED) and name not in names]
    changed = [
        name for name, origin, content in (held or [])
        if origin == ORIGIN_GENERATED and name in names and configurations[name] != content
    ]
    if not added and not removed and not changed:
        return []

    entries = []
    for name, origin, content in (held or []):
        if name in removed:
            entries.append((name, "removed", origin, content))
        elif name in changed:
            entries.append((name, "changed", origin, configurations[name]))
        else:
            entries.append((name, "kept", origin, content))
    entries += [(name, "added", "", configurations[name]) for name in added]
    entries = natsorted(entries, key=lambda entry: entry[0])

    wide = " wide" if layout == "wide" else ""
    cards = [preview_card(name, content, layout, state=state, origin=origin)
             for name, state, origin, content in entries[:MAX_PREVIEW_CONFIGS]]
    if len(entries) > MAX_PREVIEW_CONFIGS:
        cards.append(more_card(len(entries) - MAX_PREVIEW_CONFIGS, layout))

    stats = []
    if added:
        stats.append(ui.stat(len(added), "added by these rules", className="accent"))
    if removed:
        stats.append(ui.stat(len(removed), "no longer described", className="caution"))
    if changed:
        stats.append(ui.stat(
            len(changed), "content update" if len(changed) == 1 else "content updates", className="accent",
        ))

    return [
        html.Div(
            children=stats + [ui.badge("not saved yet", color="warning")],
            className="odx-config-preview-header",
        ),
        html.Div(cards, className="card-matrix configs odx-configs-diff odx-config-preview-row" + wide),
    ]


def variable_values_inline(values):
    """
    The values one variable takes, on its own row: how many of them, then the
    values themselves, cut short when there are many.

    This is what makes a folded row worth reading -- the variable is named, and
    then said.
    """
    if values is None:
        return html.Span("no values", className="odx-variable-values-empty")
    values = list(values)
    shown = values
    if len(shown) > hard_settings.max_preview_values:
        shown = shown[:hard_settings.max_preview_values - 2] + ["[...]"] + [shown[-1]]
    return [
        html.Span(f"{len(values)} values", className="odx-variable-count"),
        html.Span(", ".join(map(str, shown)), className="odx-variable-values-list"),
    ]


@page_callback(PAGE_SCOPE,
    Output({"type": "cfg-save-rules", "domain_uuid": dash.ALL}, "className"),
    Output({"type": "cfg-save-rules", "domain_uuid": dash.ALL}, "data-tooltip"),
    Input({"type": "cfg-gen-name", "domain_uuid": dash.ALL}, "value"),
    Input({"type": "cfg-gen-template", "domain_uuid": dash.ALL}, "value"),
    Input({"type": "cfg-rules-store", "domain_uuid": dash.ALL}, "data"),
    *variable_inputs(),
    State({"type": "domain-metadata", "domain_uuid": dash.ALL}, "data"),
)
def update_save_rules_button(names, templates, stores, *rest):
    """
    Light up the save button of a domain whose rules differ from what its
    settings file says. The page-wide save button of the configuration editor
    looks for the same "warning" class, so unsaved rules are caught by the
    leaving-the-page guard too.
    """
    field_values = rest[:len(FIELD_PATTERNS)]
    domain_metadata = rest[len(FIELD_PATTERNS)]

    disabled = "color-button disabled icon-button tooltip bottom auto caution"
    enabled = "color-button warning icon-button tooltip bottom auto caution"

    uuids = domain_uuids_of(domain_metadata)
    names_by_uuid = domain_names_of(domain_metadata)
    indices = domain_indices(field_ids("variable-title"), uuids)

    classes = []
    tooltips = []
    for i, domain_uuid in enumerate(uuids):
        saved = stores[i] if i < len(stores) and stores[i] else rules_settings("", "", {})
        current = form_rules_settings(
            names[i] if i < len(names) else "",
            templates[i] if i < len(templates) else "",
            variables_of(field_values, indices.get(domain_uuid, [])),
            names_by_uuid.get(domain_uuid),
            saved,
        )
        if current != saved:
            classes.append(enabled)
            tooltips.append("Save the rules of this parameter domain")
        else:
            classes.append(disabled)
            tooltips.append("Nothing to save")
    return classes, tooltips


@page_callback(PAGE_SCOPE,
    Output({"type": "cfg-rules-store", "domain_uuid": dash.ALL}, "data"),
    Output({"type": "cfg-rules-saved", "domain_uuid": dash.ALL}, "data"),
    Input({"type": "cfg-save-rules", "domain_uuid": dash.ALL}, "n_clicks"),
    Input({"page": PAGE_PATH, "action": "save-all"}, "n_clicks"),
    State({"type": "cfg-gen-name", "domain_uuid": dash.ALL}, "value"),
    State({"type": "cfg-gen-template", "domain_uuid": dash.ALL}, "value"),
    *variable_states(),
    State({"type": "domain-metadata", "domain_uuid": dash.ALL}, "data"),
    State({"type": "cfg-rules-store", "domain_uuid": dash.ALL}, "data"),
    State({"type": "cfg-rules-saved", "domain_uuid": dash.ALL}, "data"),
    State("url", "search"),
    State("odatix-settings", "data"),
    prevent_initial_call=True,
)
def save_rules(n_clicks, save_all_clicks, names, templates, *rest):
    """
    Write the rules of a domain, in the form Odatix reads now -- a
    "configurations" block and the variables at the root of the settings file.

    Saves the domain whose own button was pressed, or every domain whose rules
    differ from their file when the page-wide save button was, so that "Save
    all changes" means what it says.
    """
    field_values = rest[:len(FIELD_PATTERNS)]
    domain_metadata, stores, saved_counters, search, odatix_settings = rest[len(FIELD_PATTERNS):]

    uuids = domain_uuids_of(domain_metadata)
    nothing = [dash.no_update] * len(uuids)

    trigger = ctx.triggered_id
    if not isinstance(trigger, dict):
        return nothing, nothing

    if trigger.get("action") == "save-all":
        if not save_all_clicks:
            return nothing, nothing
        targets = list(range(len(uuids)))
    else:
        if trigger.get("domain_uuid") not in uuids:
            return nothing, nothing
        index = uuids.index(trigger.get("domain_uuid"))
        if not (n_clicks[index] if index < len(n_clicks) else 0):
            return nothing, nothing
        targets = [index]

    mode, instance_name, instances = get_instance_collection_context(search, odatix_settings)
    if not instance_name:
        return nothing, nothing

    indices = domain_indices(field_ids("variable-title"), uuids)
    names_by_uuid = domain_names_of(domain_metadata)

    new_stores = list(nothing)
    bumps = list(nothing)
    for index in targets:
        domain_uuid = uuids[index]
        saved = stores[index] if index < len(stores) and stores[index] else None
        settings = form_rules_settings(
            names[index] if index < len(names) else "",
            templates[index] if index < len(templates) else "",
            variables_of(field_values, indices.get(domain_uuid, [])),
            names_by_uuid.get(domain_uuid),
            saved,
        )
        if settings == saved:
            continue
        domain_name = names_by_uuid.get(domain_uuid, hard_settings.main_parameter_domain)
        ParameterDomain(instances.entry(instance_name), domain_name).update(settings)
        counter = (saved_counters[index] or 0) if index < len(saved_counters) else 0
        new_stores[index] = settings
        bumps[index] = counter + 1
    return new_stores, bumps
