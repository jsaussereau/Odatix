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
from odatix.lib.config_generator import parse_constraints, parse_rule_sets
import odatix.workspace.selectors as selectors
from odatix.workspace.configs import CONFIGURATIONS_KEY
from odatix.workspace.configs import CONFIG_EXTENSION
from odatix.workspace.space import (
    ORIGIN_BLACKLISTED, ORIGIN_EDITED, ORIGIN_GENERATED, config_set_rules, implicit_config_name,
    implicit_template,
)
from odatix.gui.page_scope import input_ids, page_callback

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
#: Shown in the empty constraints field: what one looks like, not one that is used.
DEFAULT_CONSTRAINTS = "${var} <= ${other_var}"
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

def _blacklist_of(block):
    """The names one rules block excludes."""
    blacklist = block.get("blacklist", ()) if isinstance(block, dict) else ()
    if not isinstance(blacklist, (list, tuple, set)):
        return []
    return [str(name) for name in blacklist if str(name)]


def configuration_blacklist(settings):
    """
    The generated configuration names explicitly excluded by saved rules.

    Read over every rule set when several are declared: what they describe is
    the union of what each produces, so what is hidden from it is the union of
    what each hides.
    """
    configurations = (settings or {}).get(CONFIGURATIONS_KEY, {})
    if isinstance(configurations, (list, tuple)):
        names = []
        for block in configurations:
            for name in _blacklist_of(block):
                if name not in names:
                    names.append(name)
        return names
    return _blacklist_of(configurations)


def rules_with_blacklisted_rule_set_configuration(rules, config_name, blacklisted):
    """
    Saved rules declaring several rule sets, with one configuration added to or
    removed from what they hide.

    The names of the union are unique -- two rule sets naming the same
    configuration is an error reported on its own -- so an entry hides the same
    point whichever block carries it, and a new one goes to the first.
    """
    updated = dict(rules or {})
    blocks = [dict(block) if isinstance(block, dict) else block for block in updated.get(CONFIGURATIONS_KEY, ())]
    for block in blocks:
        if not isinstance(block, dict):
            continue
        kept = [name for name in _blacklist_of(block) if name != config_name]
        if kept:
            block["blacklist"] = kept
        else:
            block.pop("blacklist", None)
    if blacklisted and blocks and isinstance(blocks[0], dict):
        blocks[0]["blacklist"] = _blacklist_of(blocks[0]) + [config_name]
    updated[CONFIGURATIONS_KEY] = blocks
    return updated


def rule_set_constraints(block):
    """The constraints one rules block puts on the values of its variables."""
    if not isinstance(block, dict):
        return []
    return [expression for expression, _message in parse_constraints(block)]


def constraints_text(constraints):
    """The constraints as the field shows them: one expression per line."""
    return "\n".join(constraints or ())


def constraints_of_text(text):
    """The constraints a field holds, blank lines and comments left out."""
    lines = str(text or "").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]


######################################
# Selectors ("match")
######################################

#: What separates a selector from the configuration it substitutes, as the field
#: is written back. A colon is read as well, since that is how the settings file
#: writes it, but the arrow is what a selector holding a colon of its own needs.
MATCH_SEPARATOR = "->"

DEFAULT_MATCH = 'P*            -> the_configuration\n$value > 7    -> another_one\n*             -> the_default_one'


def configuration_match(settings):
    """The selectors saved in a directory's settings, in the order written."""
    declared = (settings or {}).get(selectors.MATCH_KEY, {})
    if not isinstance(declared, dict):
        return {}
    return dict(
        (str(selector).strip(), str(target if target is not None else "").strip())
        for selector, target in declared.items()
        if str(selector).strip()
    )


def match_text(match):
    """
    The selectors as the field shows them: one "selector -> configuration" per
    line, the arrows lined up so the configurations read as a column.
    """
    match = match or {}
    if not match:
        return ""
    width = max(len(selector) for selector in match)
    return "\n".join(
        selector.ljust(width) + " " + MATCH_SEPARATOR + " " + target
        for selector, target in match.items()
    )


def match_of_text(text):
    """
    The selectors a field holds, blank lines and comments left out.

    Both separators are read: the arrow the field writes, and the colon the
    settings file uses -- a line written by hand as YAML says the same thing.
    The arrow is looked for first, since a selector may hold a colon of its own
    (a regular expression) but never an arrow.
    """
    match = {}
    for line in str(text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        selector, separator, target = line.partition(MATCH_SEPARATOR)
        if not separator:
            selector, separator, target = line.rpartition(":")
        if not separator:
            # A selector on its own says nothing about what to substitute for
            # it: kept as it is written, so a line being typed is not thrown
            # away between two keystrokes.
            selector, target = line, ""
        selector = selector.strip()
        if selector:
            match[selector] = target.strip()
    return match


def match_form(domain_uuid, match, visible=True):
    """
    The selectors of a directory of configurations: which configuration is
    substituted for the ones it does not hold, one per line.

    Only a simulation looks a configuration up by selector (see
    :mod:`odatix.workspace.selectors`), so this is shown on the "?sim=&arch="
    page only -- and built, hidden, everywhere else, so that every callback
    keeps seeing one field per domain.
    """
    return html.Div(
        children=[
            html.Div([
                html.H3("Matching", style={"margin": "0px"}),
                ui.tooltip_icon(
                    "Which configuration of this directory is substituted for the configurations of the "
                    "parameter domain it does not hold, one \"selector -> configuration\" per line. "
                    "A selector is a name, a pattern (\"P*\", \"M?0[01]\"), a regular expression "
                    "(\"/^M[0-9]+$/\") or a condition on $name (the configuration being run) and $value "
                    "(what it substitutes, when it is a single number), as in \"$value > 7\". "
                    "A configuration this directory holds under its own name is always used as it is: "
                    "selectors only answer for the rest. When several of them match, the most specific "
                    "wins, and the first one written breaks a tie. Lines starting with '#' are ignored."
                ),
                html.Div(
                    ui.icon_button(
                        icon=icon("save", className="icon"),
                        color="disabled",
                        text="Save selectors",
                        width="150px",
                        id={"type": "cfg-save-match", "domain_uuid": domain_uuid},
                        tooltip="Nothing to save",
                        tooltip_options="bottom auto caution",
                    ),
                    className="inline-flex-buttons",
                    style={"marginLeft": "auto"},
                ),
            ], style={"display": "flex", "alignItems": "center", "gap": "10px"}),
            html.Span(
                "one configuration for a whole family, instead of one file each",
                style={"opacity": "0.65", "fontSize": "13px"},
            ),
            dcc.Textarea(
                id={"type": "cfg-match", "domain_uuid": domain_uuid},
                value=match_text(match),
                # Highlighted as selectors -- values, wildcards and the
                # configuration each one points at -- rather than as a command
                # (see the "odatix-selector-field" mode of
                # assets/variable_highlight.js).
                className="auto-resize-textarea odatix-command-field odatix-selector-field",
                placeholder=DEFAULT_MATCH,
                style={"width": "100%", "boxSizing": "border-box", "resize": "none", "fontFamily": "monospace", "fontWeight": "500"},
            ),
            html.Div(
                id={"type": "cfg-match-summary", "domain_uuid": domain_uuid},
                style={"opacity": "0.75", "fontSize": "13px", "marginTop": "-4px"},
            ),
        ],
        id={"type": "cfg-match-panel", "domain_uuid": domain_uuid},
        style={"display": "flex", "flexDirection": "column", "gap": "8px", "marginTop": "10px"}
        if visible else Style.hidden,
    )


#: What the form owns in a rules block. Everything else a block says -- the
#: names it hides, the variables it restricts itself to -- is not edited here,
#: and is written back exactly as it was found.
BLOCK_FORM_KEYS = ("name", "template", "constraints", "enabled")


def _block_settings(name, template, enabled=False, blacklist=(), constraints=(), extra=None):
    """One rules block, as the settings file writes it."""
    block = {
        "name": name or "",
        "template": template or "",
    }
    if enabled:
        block["enabled"] = True
    if constraints:
        block["constraints"] = list(constraints)
    if blacklist:
        block["blacklist"] = list(blacklist)
    for key, value in (extra or {}).items():
        block.setdefault(key, value)
    return block


def rule_sets_settings(blocks, variables, match=None):
    """
    The settings a domain writes to say how it describes its configurations.

    One block is written the way it always was, as a mapping. Several are
    written as a list, which is what declares them as rule sets: what the domain
    holds is their union, nothing combined across them (see
    :func:`odatix.lib.config_generator.parse_rule_sets`).
    """
    blocks = [block for block in blocks] or [_block_settings("", "")]
    settings = {
        CONFIGURATIONS_KEY: blocks[0] if len(blocks) == 1 else blocks,
        "variables": variables,
    }
    # Written as soon as the caller says anything about it, the empty block
    # included: settings are updated key by key, so a "match" block emptied in
    # the editor has to be written empty to disappear from the file (where it
    # is then left out, being empty).
    if match is not None:
        settings[selectors.MATCH_KEY] = dict(match)
    return settings


def rules_settings(name, template, variables, enabled=False, blacklist=(), constraints=(), match=None):
    """The settings of a domain described by a single set of rules."""
    return rule_sets_settings(
        [_block_settings(name, template, enabled=enabled, blacklist=blacklist, constraints=constraints)],
        variables, match=match,
    )


def configuration_defaults_enabled(settings):
    """Whether the saved rules explicitly choose both implicit templates."""
    configurations = (settings or {}).get(CONFIGURATIONS_KEY, {})
    return isinstance(configurations, dict) and bool(configurations.get("enabled"))


def declares_rule_sets(settings):
    """Whether saved rules declare several rule sets rather than one."""
    return bool(parse_rule_sets((settings or {}).get(CONFIGURATIONS_KEY)))


def saved_rule_sets(settings):
    """
    The rules blocks of a domain, each with the key its fields are named after.

    A domain always has at least one block -- an empty one when it says nothing
    yet -- so the form is the same list of cards whether one set of rules is
    declared or several. The key is the position the block was read at, and is
    what a card is matched back to its own saved block by: it survives another
    card being added before it or deleted after it.
    """
    configurations = (settings or {}).get(CONFIGURATIONS_KEY, {})
    blocks = parse_rule_sets(configurations)
    if blocks:
        return [(index, dict(block)) for index, block in enumerate(blocks)]
    return [(0, dict(configurations) if isinstance(configurations, dict) else {})]


def rule_set_extras(settings):
    """What each saved block says that the form does not edit, by key."""
    return dict(
        (key, dict((name, value) for name, value in block.items() if name not in BLOCK_FORM_KEYS))
        for key, block in saved_rule_sets(settings)
    )


def rule_set_fields(settings, implicit=True):
    """
    What the cards of a domain hold, as ``(key, name, template, constraints)``,
    and the variables they share.

    A single set of rules leaves unsaid what Odatix would fill in anyway: an
    implicit name or template is the placeholder of a field, not text to put in
    it. Several rule sets say both in each of them, and are shown as written.
    """
    space = config_set_rules(settings or {}, implicit=implicit)
    variables = ve.normalized_variables(dict(space.variables))
    blocks = saved_rule_sets(settings)
    if len(blocks) == 1:
        key, block = blocks[0]
        return [(
            key,
            "" if space.implicit_name else space.name,
            "" if space.implicit_template or space.template is None else space.template,
            rule_set_constraints(block),
        )], variables
    return [
        (key,
         str(block.get("name", "") or ""),
         str(block.get("template", "") or ""),
         rule_set_constraints(block))
        for key, block in blocks
    ], variables


def form_rules_settings(blocks, variables, domain_name, saved=None, match=None):
    """
    The rules the form currently means, including the main-domain defaults.

    ``blocks`` is what the cards hold, in the order they are written back. What
    the saved blocks said beyond the fields -- the names they hide, a "variables"
    restriction -- is carried over by key, so editing one card never drops what
    another one was written with.
    """
    extras = rule_set_extras(saved)
    blocks = [block for block in blocks] or [(0, "", "", [])]
    if len(blocks) == 1:
        key, name, template, constraints = blocks[0]
        # The main domain of a workspace describes its configurations by
        # declaring variables alone; saying so explicitly is what keeps it
        # describing them once anything else about it is written.
        enabled = configuration_defaults_enabled(saved) or (
            domain_name == hard_settings.main_parameter_domain
            and bool(variables)
            and not name
            and not template
        )
        written = [_block_settings(
            name, template, enabled=enabled, constraints=constraints, extra=extras.get(key),
        )]
    else:
        written = [
            _block_settings(name, template, constraints=constraints, extra=extras.get(key))
            for key, name, template, constraints in blocks
        ]
    return rule_sets_settings(written, variables, match=match)


def stored_rules_settings(settings, blocks, variables, domain_name=None):
    """
    What a panel was opened on, in the very form its fields hand back.

    This is what the dirty state is measured against, so it has to be written
    the way :func:`form_rules_settings` writes it -- storing anything else would
    make a panel nobody touched open as unsaved, and "Save all changes" then
    write whatever the fields happen to say over the file.
    """
    return form_rules_settings(
        blocks, variables, domain_name, settings, match=configuration_match(settings),
    )


def rules_space(settings, implicit=True):
    """
    The design space some rules describe, as Odatix reads them.

    Taken from the settings the form means rather than from two fields, so a
    domain of several rule sets is previewed as the union it is instead of as
    the cross product of everything it declares.
    """
    return config_set_rules(settings or {}, implicit=implicit)


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


def rule_sets_notice(count):
    """
    What a domain of several rule sets says above them: they are not combined.

    Shown only when there is something to say -- a single set of rules is just
    the rules of the domain, and needs no explaining.
    """
    return html.Div(
        children=[
            ui.badge("{0} rule sets".format(count), color="primary"),
            html.Span(
                "the configurations of this domain are the union of these sets of rules: "
                "nothing is combined across them, and each of them uses the variables it names",
                style={"opacity": "0.65", "fontSize": "13px"},
            ),
        ],
        className="odx-rule-sets-notice",
        style={"display": "flex", "alignItems": "center", "gap": "10px", "flexWrap": "wrap",
               "marginBottom": "12px"},
    )


def rule_set_card(domain_uuid, key, name, template, constraints, variables=None, index=0, total=1):
    """
    One set of rules: what its configurations are called, what they write, and
    what combinations of values are configurations at all.

    Its fields carry the key of the block they came from, so what the panel
    hands back can be matched to what the file already said about it -- the
    names it hides above all.
    """
    # A domain does not have to write either template down: the placeholder is
    # then what Odatix would actually use, not an example.
    # Either field left empty means the same thing in every domain, the main one
    # included: the values themselves. The placeholders say so.
    implicit_name = implicit_config_name(variables or {})
    implicit_content = implicit_template(variables or {})
    # Every set of rules is shown as one, the only set of a domain included:
    # what a domain says about its configurations reads the same whether it
    # says it once or several times.
    actions = [
        ui.icon_button(
            icon=icon("duplicate", className="icon"),
            color="default",
            id={"type": "cfg-duplicate-rule-set", "domain_uuid": domain_uuid, "rule_set": key},
            tooltip="Duplicate this set of rules",
            tooltip_options="bottom auto",
        ),
    ]
    # The last set of rules of a domain is not deletable: a domain describes
    # its configurations with one set of rules or several, never with none.
    if total > 1:
        actions.append(ui.icon_button(
            icon=icon("delete", className="icon"),
            color="default",
            id={"type": "cfg-delete-rule-set", "domain_uuid": domain_uuid, "rule_set": key},
            tooltip="Delete this set of rules",
            tooltip_options="bottom auto caution",
        ))
    header = [html.Div(
        children=[
            html.H4("Rule set {0}".format(index + 1), style={"margin": "0px"}),
            html.Div(actions, style={"display": "flex", "alignItems": "center", "gap": "6px"}),
        ],
        style={"display": "flex", "alignItems": "center", "justifyContent": "space-between",
               "gap": "10px", "marginBottom": "8px"},
    )]
    return html.Div(
        children=header + [
            html.Div([
                html.Label("Configuration name"),
                ui.tooltip_icon(
                    "How the configurations of this domain are named. Use a variable name prefixed by a dollar sign "
                    "and enclosed in curly braces (e.g. ${width}) where its value belongs. The '.txt' extension is not required. "
                    "Leaving this empty names the configurations after the values themselves, joined by an underscore when there are several variables."
                ),
                dcc.Input(
                    id={"type": "cfg-gen-name", "domain_uuid": domain_uuid, "rule_set": key},
                    value=name,
                    type="text",
                    placeholder=implicit_name or DEFAULT_NAME,
                    # The ${...} of both templates are highlighted, in the color
                    # of what they resolve to among the variables of this very
                    # domain (see assets/variable_highlight.js and the scope the
                    # panel declares).
                    className="odatix-command-field",
                    style={"width": "100%", "boxSizing": "border-box", "fontFamily": "monospace", "fontWeight": "500"},
                ),
            ], style={"marginBottom": "12px"}),
            html.Div([
                html.Label("Content template"),
                ui.tooltip_icon(
                    "What each configuration writes between the delimiters, with ${variable_name} replaced by its value. "
                    "Leaving this empty writes the values themselves, one per line."
                ),
                dcc.Textarea(
                    id={"type": "cfg-gen-template", "domain_uuid": domain_uuid, "rule_set": key},
                    value=template,
                    className="auto-resize-textarea odatix-command-field",
                    placeholder=implicit_content or DEFAULT_TEMPLATE,
                    style={"width": "100%", "boxSizing": "border-box", "resize": "none", "fontFamily": "monospace", "fontWeight": "500"},
                ),
            ], style={"marginBottom": "12px"}),
            html.Div([
                html.Label("Constraints"),
                ui.tooltip_icon(
                    "One boolean expression per line, over the variables of this domain (e.g. ${p_rf_sp} <= ${p_rf_read_buf}). "
                    "A combination of values that does not satisfy every one of them is not a configuration of this domain at all: "
                    "unlike a blacklisted configuration, it is never named and never shown. Lines starting with '#' are ignored."
                ),
                dcc.Textarea(
                    id={"type": "cfg-gen-constraints", "domain_uuid": domain_uuid, "rule_set": key},
                    value=constraints_text(constraints),
                    className="auto-resize-textarea odatix-command-field",
                    placeholder=DEFAULT_CONSTRAINTS,
                    style={"width": "100%", "boxSizing": "border-box", "resize": "none", "fontFamily": "monospace", "fontWeight": "500"},
                ),
            ], style={"marginBottom": "12px"}),
        ],
        className="odx-rule-set card configs",
        style={"padding": "12px", "marginBottom": "12px"},
    )


def add_rule_set_card(domain_uuid):
    """
    The last card of the list: one more set of rules, whose points are added to
    what the domain already describes rather than combined with them.
    """
    return html.Div(
        html.Div(
            children=[
                html.Div("+", style={"fontSize": "1.6em", "lineHeight": "1"}),
                html.Div("Add another set of rules", style={"fontWeight": "bold"}),
            ],
            id={"type": "cfg-new-rule-set", "domain_uuid": domain_uuid},
            n_clicks=0,
            style={"display": "flex", "alignItems": "center", "gap": "10px",
                   "textDecoration": "none", "width": "100%"},
        ),
        className="card configs add hover odx-rule-set-add",
        style={"padding": "10px 12px", "margin": "0px 0px 8px 0px", "display": "block",
               "width": "auto", "boxSizing": "border-box"},
    )


def rule_set_cards(domain_uuid, blocks, variables=None):
    """The cards a domain's rules are edited in, and the one that adds another."""
    total = len(blocks)
    cards = [
        rule_set_card(domain_uuid, key, name, template, constraints, variables, index, total)
        for index, (key, name, template, constraints) in enumerate(blocks)
    ]
    if total > 1:
        cards.insert(0, rule_sets_notice(total))
    cards.append(add_rule_set_card(domain_uuid))
    return cards


def rules_form(domain_uuid, blocks, variables=None):
    """
    How the configurations of a domain are named and what they contain: one
    card per set of rules, and one more to add another set.
    """
    return html.Div(
        children=rule_set_cards(domain_uuid, blocks, variables),
        id={"type": "cfg-rule-sets-row", "domain_uuid": domain_uuid},
    )


def advanced_section(domain_uuid, blocks, variables, open=False):
    """
    The rules of a domain, behind a fold: a domain says everything by declaring
    its variables, and only a domain that names or writes its configurations
    some other way has to open this.

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
                    rules_form(domain_uuid, blocks, variables),
                ],
                id={"type": "cfg-advanced-panel", "domain_uuid": domain_uuid},
                style={"marginTop": "12px"} if open else Style.hidden,
            ),
        ],
        style={"marginTop": "10px"},
    )


def domain_advanced_section(domain_uuid, settings, domain_name=None):
    """
    The rules of a domain, folded, as the configuration-parameters tile shows
    them: they say what is written into the target file set right above, which
    is the one place they belong.
    """
    blocks, variables = rule_set_fields(settings)
    return advanced_section(
        domain_uuid, blocks, variables,
        # Opened by itself only when it holds something: templates or
        # constraints already written, or the several sets of rules a domain of
        # a union is made of. Empty, it stays folded, main domain included.
        open=len(blocks) > 1 or any(part for block in blocks for part in block[1:]),
    )


def rules_section(domain_uuid, settings, open=False, domain_name=None, entry=None):
    """
    The variables of one parameter domain, and what they add up to.

    No fold of its own any more: a variable is a row saying its name, its type
    and the values it takes, so the whole list is readable at a glance and there
    is nothing to hide it behind. The two templates it feeds are edited next to
    the target file, under "Advanced" (see :func:`advanced_section`), which is
    where the rest of what the replacement does is set up.

    ``open`` is kept for callers that used to open this panel; nothing is folded
    here now.

    ``entry`` is what a section of the "?sim=&arch=" page substitutes, and is
    None everywhere else: only a simulation names the configurations it
    substitutes for by selector, so only such a section shows the "Matching"
    field (see :func:`match_form`).
    """
    space = config_set_rules(settings or {}, implicit=True)
    blocks, variables = rule_set_fields(settings)
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
                html.Div(
                    [match_form(domain_uuid, configuration_match(settings), visible=entry is not None)],
                    className="tile title",
                    style={"marginTop": "10px"} if entry is not None else Style.hidden,
                ),
                className="card-matrix config",
            ),
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
                data=stored_rules_settings(settings, blocks, variables, domain_name),
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


def matched_ids(type_name):
    """
    The ids Dash matched for one pattern, in the order its values came back,
    whether it was declared as an Input or as a State.
    """
    for group in list(ctx.inputs_list or []) + list(ctx.states_list or []):
        if isinstance(group, list) and group and isinstance(group[0], dict):
            if group[0].get("id", {}).get("type") == type_name:
                return [item.get("id", {}) for item in group]
    return []


def field_ids(pattern):
    """
    The ids Dash matched for one variable-field pattern, in the order the
    values came back. Every pattern of a variable card matches the same ids, so
    this is also the order of every other field list.
    """
    return matched_ids(VE_PREFIX + pattern)


def rule_set_positions(domain_uuids):
    """
    Where the fields of each domain's rule sets are in the flat field lists,
    in the order the blocks are written back.

    Sorted by the key of the block rather than left to the order Dash matched
    the ids in: what the file lists is what the panel shows, whichever way the
    keys of a domain happen to compare.
    """
    ids = matched_ids("cfg-gen-name")
    positions = dict((domain_uuid, []) for domain_uuid in domain_uuids)
    for index, identifier in enumerate(ids):
        domain_uuid = identifier.get("domain_uuid")
        if domain_uuid in positions:
            positions[domain_uuid].append((identifier.get("rule_set", 0), index))
    return dict(
        (domain_uuid, [index for _key, index in sorted(entries, key=lambda item: _sort_key(item[0]))])
        for domain_uuid, entries in positions.items()
    )


def _sort_key(key):
    """A rule-set key, ordered as a number when it is one."""
    try:
        return (0, int(key), "")
    except (TypeError, ValueError):
        return (1, 0, str(key))


def form_blocks(names, templates, constraint_texts, positions):
    """
    What the cards of one domain hold, as :func:`form_rules_settings` takes
    them: ``(key, name, template, constraints)``, in the order they are written.
    """
    ids = matched_ids("cfg-gen-name")
    blocks = []
    for index in positions:
        identifier = ids[index] if index < len(ids) else {}
        blocks.append((
            identifier.get("rule_set", 0),
            names[index] if index < len(names) else "",
            templates[index] if index < len(templates) else "",
            constraints_of_text(constraint_texts[index] if index < len(constraint_texts or ()) else ""),
        ))
    return blocks


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

# Showing the two templates of a domain only when they are asked for, and
# folding one variable card away, are both done in the browser, outside Dash:
# see the fold handler in assets/config_editor.js. Nothing but the page reads
# what they write, and a fold answered by Dash costs about a second on a page
# holding hundreds of cards, wherever the answer is computed.


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


@page_callback(PAGE_SCOPE,
    Output({"type": "cfg-rule-sets-row", "domain_uuid": dash.ALL}, "children"),
    Input({"type": "cfg-new-rule-set", "domain_uuid": dash.ALL}, "n_clicks"),
    Input({"type": "cfg-delete-rule-set", "domain_uuid": dash.ALL, "rule_set": dash.ALL}, "n_clicks"),
    Input({"type": "cfg-duplicate-rule-set", "domain_uuid": dash.ALL, "rule_set": dash.ALL}, "n_clicks"),
    State({"type": "cfg-gen-name", "domain_uuid": dash.ALL, "rule_set": dash.ALL}, "value"),
    State({"type": "cfg-gen-template", "domain_uuid": dash.ALL, "rule_set": dash.ALL}, "value"),
    State({"type": "cfg-gen-constraints", "domain_uuid": dash.ALL, "rule_set": dash.ALL}, "value"),
    State({"type": "domain-metadata", "domain_uuid": dash.ALL}, "data"),
    *variable_states(),
    prevent_initial_call=True,
)
def update_rule_set_cards(new_clicks, delete_clicks, duplicate_clicks, names, templates, constraint_texts,
                          domain_metadata, *field_values):
    """
    Add a set of rules to a domain, duplicate one, or delete one, leaving every other domain
    alone -- and leaving what the other cards of this one hold as it is: they
    are rebuilt from the form, not from the file, so an unsaved edit survives.

    The last set of rules of a domain is not deletable: a domain describes its
    configurations with one set of rules or several, never with none. Emptying
    the fields of the last one is how a domain stops describing any.
    """
    trigger = ctx.triggered_id
    if not isinstance(trigger, dict):
        return [dash.no_update] * len(domain_metadata)

    uuids = domain_uuids_of(domain_metadata)
    domain_uuid = trigger.get("domain_uuid", "")
    if domain_uuid not in uuids:
        return [dash.no_update] * len(uuids)
    row_index = uuids.index(domain_uuid)

    clicked = {
        "cfg-new-rule-set": new_clicks,
        "cfg-duplicate-rule-set": duplicate_clicks,
    }.get(trigger.get("type"), delete_clicks)
    if not any(clicked or ()):
        return [dash.no_update] * len(uuids)

    positions = rule_set_positions(uuids)
    blocks = form_blocks(names, templates, constraint_texts, positions.get(domain_uuid, []))

    target = trigger.get("rule_set")
    used = [_sort_key(key)[1] for key, _n, _t, _c in blocks]
    next_key = (max(used) + 1) if used else 1
    if trigger.get("type") == "cfg-new-rule-set":
        blocks.append((next_key, "", "", []))
    elif trigger.get("type") == "cfg-duplicate-rule-set":
        # The copy is what the duplicated set says now, right after it: read as
        # a variant of its neighbour rather than as a set of its own at the end.
        position = next((i for i, block in enumerate(blocks) if block[0] == target), None)
        if position is not None:
            _key, name, template, constraints = blocks[position]
            blocks.insert(position + 1, (next_key, name, template, list(constraints)))
    elif len(blocks) > 1:
        blocks = [block for block in blocks if block[0] != target]

    indices = domain_indices(field_ids("variable-title"), uuids)
    variables = variables_of(field_values, indices.get(domain_uuid, []))
    cards = rule_set_cards(domain_uuid, blocks, variables)
    return [cards if i == row_index else dash.no_update for i in range(len(uuids))]


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
    Output({"type": "cfg-gen-name", "domain_uuid": dash.ALL, "rule_set": dash.ALL}, "placeholder"),
    Output({"type": "cfg-gen-template", "domain_uuid": dash.ALL, "rule_set": dash.ALL}, "placeholder"),
    Input({"type": "cfg-gen-name", "domain_uuid": dash.ALL, "rule_set": dash.ALL}, "value"),
    Input({"type": "cfg-gen-template", "domain_uuid": dash.ALL, "rule_set": dash.ALL}, "value"),
    Input({"type": "cfg-gen-constraints", "domain_uuid": dash.ALL, "rule_set": dash.ALL}, "value"),
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
def update_rules_preview(names, templates, constraint_texts, stores, layout, *rest):
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
    rule_sets = rule_set_positions(uuids)
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
    # One per rule-set field of the page, in the order Dash matched them: every
    # set of rules of a domain says the same thing when it is left empty.
    name_placeholders = [dash.no_update] * len(names)
    template_placeholders = [dash.no_update] * len(templates)
    for i, domain_uuid in enumerate(uuids):
        positions = rule_sets.get(domain_uuid, [])
        blocks = form_blocks(names, templates, constraint_texts, positions)
        variables = variables_of(field_values, indices.get(domain_uuid, []))
        saved = stores[i] if i < len(stores) and stores[i] else rules_settings("", "", {}, match={})
        # Once the form says what the file says, the configuration cards below
        # are the real thing: previewing them again would only be noise.
        current = form_rules_settings(
            blocks, variables, domain_names.get(domain_uuid), saved,
            match=configuration_match(saved) if selectors.MATCH_KEY in (saved or {}) else None,
        )
        # Read from the settings the form means, so a domain of several rule
        # sets is previewed as the union it is rather than as everything its
        # variables could be combined into.
        space = rules_space(current)
        implicit_name = implicit_config_name(variables) or DEFAULT_NAME
        implicit_content = implicit_template(variables) or DEFAULT_TEMPLATE
        for position in positions:
            if position < len(name_placeholders):
                name_placeholders[position] = implicit_name
            if position < len(template_placeholders):
                template_placeholders[position] = implicit_content
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
    return row_values, summaries, config_previews, name_placeholders, template_placeholders


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


@page_callback(PAGE_SCOPE,
    Output({"type": "cfg-match-summary", "domain_uuid": dash.ALL}, "children"),
    Input({"type": "cfg-match", "domain_uuid": dash.ALL}, "value"),
    Input({"type": "config-metadata", "domain_uuid": dash.ALL, "config_uuid": dash.ALL}, "data"),
    State({"type": "domain-metadata", "domain_uuid": dash.ALL}, "data"),
)
def update_match_summary(match_texts, config_metadata, domain_metadata):
    """
    What the selectors of a directory add up to, said under the field: how many
    there are, and which of them point at a configuration this directory does
    not hold -- the mistake that would otherwise only show up on the one run
    that needed it.

    The configurations are read from the cards of the page rather than from
    disk, so a selector written for a configuration added a moment ago is not
    reported as pointing at nothing.
    """
    summaries = []
    for index, domain_uuid in enumerate(domain_uuids_of(domain_metadata)):
        match = match_of_text(match_texts[index] if index < len(match_texts) else "")
        if not match:
            summaries.append("")
            continue
        held = set(name for name, _origin, _content in held_configurations(config_metadata, domain_uuid))
        unknown = [target for target in match.values() if target and target not in held]
        missing = [selector for selector, target in match.items() if not target]

        parts = [html.Span("{0} selector{1}".format(len(match), "" if len(match) == 1 else "s"))]
        for text in (
            ('{0} naming no configuration: "{1}"'.format(len(missing), '", "'.join(missing)) if missing else ""),
            ('{0} pointing at nothing here: "{1}"'.format(len(unknown), '", "'.join(sorted(set(unknown))))
             if unknown else ""),
        ):
            if text:
                parts.append(html.Span(" · "))
                parts.append(html.Span(text, style={"color": "var(--theme-warning-color)"}))
        summaries.append(parts)
    return summaries


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
    # The selectors are saved with the rest of what the directory says about its
    # configurations, so its button lights up with the same unsaved state.
    Output({"type": "cfg-save-match", "domain_uuid": dash.ALL}, "className"),
    Output({"type": "cfg-save-match", "domain_uuid": dash.ALL}, "data-tooltip"),
    Input({"type": "cfg-gen-name", "domain_uuid": dash.ALL, "rule_set": dash.ALL}, "value"),
    Input({"type": "cfg-gen-template", "domain_uuid": dash.ALL, "rule_set": dash.ALL}, "value"),
    Input({"type": "cfg-gen-constraints", "domain_uuid": dash.ALL, "rule_set": dash.ALL}, "value"),
    Input({"type": "cfg-match", "domain_uuid": dash.ALL}, "value"),
    Input({"type": "cfg-rules-store", "domain_uuid": dash.ALL}, "data"),
    *variable_inputs(),
    State({"type": "domain-metadata", "domain_uuid": dash.ALL}, "data"),
)
def update_save_rules_button(names, templates, constraint_texts, match_texts, stores, *rest):
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
    rule_sets = rule_set_positions(uuids)

    classes = []
    tooltips = []
    match_tooltips = []
    for i, domain_uuid in enumerate(uuids):
        saved = stores[i] if i < len(stores) and stores[i] else rules_settings("", "", {}, match={})
        current = form_rules_settings(
            form_blocks(names, templates, constraint_texts, rule_sets.get(domain_uuid, [])),
            variables_of(field_values, indices.get(domain_uuid, [])),
            names_by_uuid.get(domain_uuid),
            saved,
            match=match_of_text(match_texts[i] if i < len(match_texts) else ""),
        )
        if current != saved:
            classes.append(enabled)
            tooltips.append("Save the rules of this parameter domain")
            match_tooltips.append("Save the selectors of this directory")
        else:
            classes.append(disabled)
            tooltips.append("Nothing to save")
            match_tooltips.append("Nothing to save")
    return classes, tooltips, classes, match_tooltips


@page_callback(PAGE_SCOPE,
    Output({"type": "cfg-rules-store", "domain_uuid": dash.ALL}, "data"),
    Output({"type": "cfg-rules-saved", "domain_uuid": dash.ALL}, "data"),
    Input({"type": "cfg-save-rules", "domain_uuid": dash.ALL}, "n_clicks"),
    Input({"type": "cfg-save-match", "domain_uuid": dash.ALL}, "n_clicks"),
    Input({"page": PAGE_PATH, "action": "save-all"}, "n_clicks"),
    State({"type": "cfg-gen-name", "domain_uuid": dash.ALL, "rule_set": dash.ALL}, "value"),
    State({"type": "cfg-gen-template", "domain_uuid": dash.ALL, "rule_set": dash.ALL}, "value"),
    State({"type": "cfg-gen-constraints", "domain_uuid": dash.ALL, "rule_set": dash.ALL}, "value"),
    State({"type": "cfg-match", "domain_uuid": dash.ALL}, "value"),
    *variable_states(),
    State({"type": "domain-metadata", "domain_uuid": dash.ALL}, "data"),
    State({"type": "cfg-rules-store", "domain_uuid": dash.ALL}, "data"),
    State({"type": "cfg-rules-saved", "domain_uuid": dash.ALL}, "data"),
    State("url", "search"),
    State("odatix-settings", "data"),
    prevent_initial_call=True,
)
def save_rules(n_clicks, match_clicks, save_all_clicks, names, templates, constraint_texts, match_texts, *rest):
    """
    Write the rules of a domain, in the form Odatix reads now -- a
    "configurations" block and the variables at the root of the settings file.

    Saves the domain whose own button was pressed -- the one of its rules or the
    one of its selectors, which are the same settings file -- or every domain
    whose rules differ from their file when the page-wide save button was, so
    that "Save all changes" means what it says.
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
        clicks = match_clicks if trigger.get("type") == "cfg-save-match" else n_clicks
        if not (clicks[index] if index < len(clicks) else 0):
            return nothing, nothing
        targets = [index]

    mode, instance_name, instances = get_instance_collection_context(search, odatix_settings)
    if not instance_name:
        return nothing, nothing

    indices = domain_indices(field_ids("variable-title"), uuids)
    rule_sets = rule_set_positions(uuids)
    names_by_uuid = domain_names_of(domain_metadata)

    new_stores = list(nothing)
    bumps = list(nothing)
    for index in targets:
        domain_uuid = uuids[index]
        saved = stores[index] if index < len(stores) and stores[index] else None
        settings = form_rules_settings(
            form_blocks(names, templates, constraint_texts, rule_sets.get(domain_uuid, [])),
            variables_of(field_values, indices.get(domain_uuid, [])),
            names_by_uuid.get(domain_uuid),
            saved,
            match=match_of_text(match_texts[index] if index < len(match_texts) else ""),
        )
        if settings == saved:
            continue
        domain_name = names_by_uuid.get(domain_uuid, hard_settings.main_parameter_domain)
        ParameterDomain(instances.entry(instance_name), domain_name).update(settings)
        counter = (saved_counters[index] or 0) if index < len(saved_counters) else 0
        new_stores[index] = settings
        bumps[index] = counter + 1
    return new_stores, bumps
