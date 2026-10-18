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
The "Exclusions" section of the architecture editor: the combinations of the
parameter domains of an architecture that are not part of its design space (see
:mod:`odatix.workspace.exclusions`).

One card per rule, in the order of the file. A rule is an expression, and an
expression that reads a name nothing defines is false rather than broken: a rule
with a typo in it does not fail, it just never leaves anything out. What the page
can tell instead is what each rule *does*. The rules on the page, saved or not,
are checked against the configurations the architecture has: how many
combinations each one leaves out, and one of them as an example.
"""

import difflib
import itertools
import random

import dash
from dash import html, dcc, Input, Output, State, ctx

import odatix.gui.ui_components as ui
from odatix.gui.utils import get_workspace
import odatix.lib.hard_settings as hard_settings
from odatix.lib.expressions import ExpressionError, Ref, identifier_of, names_in, syntax_error
from odatix.workspace.exclusions import DEFAULT_APPLIED, DOMINATED, DUPLICATE, ILLEGAL, KINDS, Exclusion
from odatix.workspace.selection import ExclusionFilter

KIND_OPTIONS = [
    {"label": "Illegal", "value": ILLEGAL, "title": "The design does not work"},
    {"label": "Duplicate", "value": DUPLICATE, "title": "The same hardware as another one"},
    {"label": "Dominated", "value": DOMINATED, "title": "Never worth it: not applied by default"},
]

#: The keys of a rule its card shows. "expr" and "expression" are other names
#: of "when", read as such and written back as "when".
CARD_KEYS = ("id", "when", "expr", "expression", "require", "kind", "message")

#: Where the rest of a card keeps a rule written as a bare expression -- what has
#: to hold, the way a domain writes its constraints -- so that it is written back
#: the way it was written as long as it is not edited.
HOLDS_KEY = "__holds__"

#: Where the rest of a card notes that the rule wrote its kind, so that a rule
#: left to the default kind is not written one by an unrelated edit.
KIND_WRITTEN_KEY = "__kind__"

#: The keys of a block written as a mapping that are not its rules.
BLOCK_KEYS = ("apply", "ignore")

#: Combinations checked at most: a larger space is checked on that many of
#: them, drawn at random over the whole space without listing it.
CHECK_LIMIT = 20000

#: Values shown per name in the list of what the rules can read.
SHOWN_VALUES = 4

WHEN_TOOLTIP = (
    "The combinations this rule is about: an expression that holds for them. "
    "$variable reads a variable of the main domain, $domain the name of the configuration a "
    "parameter domain contributes, $domain.variable one of its values, $config the configuration "
    "of the main domain and $architecture the architecture. A name nothing defines is unknown: "
    "it equals nothing, so a rule reading it never fires."
)

REQUIRE_TOOLTIP = (
    "What such a combination has to be instead, for a duplicate: the canonical value, e.g. "
    "\"$Fwd.p_fwd_pw == 1\". With it, a combination is only left out when it does not hold. "
    "Empty to leave out every combination the rule is about."
)


######################################
# Reading a block
######################################

def _text(value):
    return "" if value is None else str(value).strip()


def _kind(value):
    kind = _text(value).lower() or ILLEGAL
    return kind if kind in KINDS else ILLEGAL


def block_rules(declared):
    """
    The rules of an "exclusions" block, and what the block says besides them.

    Returns:
        tuple: (the entries, in order; the other keys of a block written as a
        mapping -- "apply", "ignore" -- or an empty dict).
    """
    if declared is None:
        return [], {}
    extra = {}
    rules = declared
    if isinstance(declared, dict) and any(key in declared for key in ("rules",) + BLOCK_KEYS):
        rules = declared.get("rules")
        extra = {key: value for key, value in declared.items() if key != "rules"}
    if rules is None:
        rules = []
    elif not isinstance(rules, (list, tuple)):
        rules = [rules]
    return [rule for rule in rules if isinstance(rule, dict) or _text(rule)], extra


def card_fields(entry):
    """What the card of one rule shows of it."""
    if isinstance(entry, dict):
        return {
            "id": _text(entry.get("id")),
            "kind": _kind(entry.get("kind")),
            "when": _text(entry.get("when", entry.get("expr", entry.get("expression")))),
            "require": _text(entry.get("require")),
            "message": _text(entry.get("message")),
            # What the file says that the card does not show, kept so that
            # editing the card does not drop it.
            "rest": dict(
                {key: value for key, value in entry.items() if key not in CARD_KEYS},
                **({KIND_WRITTEN_KEY: True} if "kind" in entry else {})
            ),
        }
    # A bare expression says what has to hold: the rule leaves out the points
    # where it does not, which is how it is read (see exclusions._rule_list).
    holds = _text(entry)
    return {
        "id": "", "kind": ILLEGAL, "when": "not ({0})".format(holds), "require": "", "message": "",
        "rest": {HOLDS_KEY: holds},
    }


def rule_of(fields):
    """The entry one card is written as, or None when it says nothing."""
    rest = dict(fields.get("rest") or {})
    holds = rest.pop(HOLDS_KEY, None)
    kind_written = rest.pop(KIND_WRITTEN_KEY, False)
    identifier, when, require, message = (
        _text(fields.get(key)) for key in ("id", "when", "require", "message")
    )
    kind = _kind(fields.get("kind"))

    # Without "when" nor "require", a rule leaves nothing out (Exclusion.valid):
    # it is not written.
    if not when and not require:
        return None

    if (
        holds is not None and when == "not ({0})".format(holds) and kind == ILLEGAL
        and not (identifier or require or message or rest)
    ):
        return holds

    entry = {}
    if identifier:
        entry["id"] = identifier
    if when:
        entry["when"] = when
    if require:
        entry["require"] = require
    # The default kind is only written when the rule wrote it: a new rule, or
    # one that did not, keeps the file as short as it was.
    if kind != ILLEGAL or kind_written:
        entry["kind"] = kind
    if message:
        entry["message"] = message
    entry.update(rest)
    return entry


def build_block(cards, extra=None):
    """
    The "exclusions" block to write, from what the cards hold.

    Args:
        cards (list): the fields of each card, in order (see card_fields).
        extra (dict): what the block said besides its rules ("apply",
            "ignore"), written back as it was.

    Returns:
        list or dict: the rules, or a mapping holding them when the block says
        something else too. Empty when there is nothing to write.
    """
    rules = [rule for rule in (rule_of(fields) for fields in cards or []) if rule is not None]
    if extra:
        block = dict(extra)
        if rules:
            block["rules"] = rules
        return block
    return rules


def normalize_block(declared):
    """
    The block as the cards can express it, so that the one read from the file
    and the one rebuilt from the page can be compared. It mirrors build_block.
    """
    rules, extra = block_rules(declared)
    return build_block([card_fields(rule) for rule in rules], extra)


def cards_from_values(ids, kinds, whens, requires, messages, rests):
    """The fields of every card, from the values of the page, in card order."""
    def at(values, index):
        return values[index] if values and index < len(values) else None

    return [
        {
            "id": at(ids, index),
            "kind": at(kinds, index),
            "when": at(whens, index),
            "require": at(requires, index),
            "message": at(messages, index),
            "rest": at(rests, index),
        }
        for index in range(len(whens or []))
    ]


######################################
# UI Components
######################################

KIND_TOOLTIP = (
    "Illegal: the design does not work. Duplicate: the same hardware as another one, which "
    "\"Require\" names. Both are left out of every sweep, search and selection. Dominated: the "
    "design works but is never worth it; only a DSE campaign that asks for it leaves it out."
)


def kind_field(index, value):
    """
    The kind of a rule: three choices, all in sight. A dropdown would hide two
    of them, open over the fields under it, and cost a card far more to draw.
    """
    return html.Div(
        children=[
            html.Div(
                children=[html.Label("Kind"), ui.tooltip_icon(KIND_TOOLTIP)],
                className="odx-field-label",
            ),
            dcc.RadioItems(
                id={"type": "arch-exclusion-kind", "index": index},
                options=[
                    {"label": html.Span(option["label"], title=option["title"]), "value": option["value"]}
                    for option in KIND_OPTIONS
                ],
                value=value,
                className="odx-chips small odx-exclusion-kind",
            ),
        ],
        className="odx-field",
    )


def readable_names(architecture):
    """
    A few names a rule of `architecture` can read, each with one of its values,
    as ``("$name", "'value'")`` pairs: the parameter domains with one of their
    configurations, or the configuration of the main domain. They make the
    placeholders of the cards speak of this architecture rather than of another
    one. Empty when nothing can be read.
    """
    if architecture is None:
        return []
    try:
        domains = architecture.parameter_domains()
    except Exception:
        return []
    names = []
    for domain, configurations in domains.items():
        if not configurations:
            continue
        name = "config" if domain == hard_settings.main_parameter_domain else domain
        names.append(("$" + name, repr(str(configurations[0]))))
    # The other domains first: telling them apart is what a rule is usually for.
    names.sort(key=lambda pair: pair[0] == "$config")
    return names


def placeholders(names):
    """The placeholders of the "When" and "Require" fields, from `readable_names`."""
    terms = ["{0} == {1}".format(name, value) for name, value in (names or [])]
    if not terms:
        return "$domain == 'configuration'", "Optional, e.g. $other_domain == 'configuration'"
    when = " and ".join(terms[:2])
    return when, "Optional, e.g. " + terms[-1]


def card_title(identifier, when):
    """
    What a card is called: its id, or else the start of what it is about, so
    that the cards of a long block can be told apart without reading them.
    """
    identifier, when = _text(identifier), " ".join(_text(when).split())
    if identifier:
        return "Leave out: " + identifier
    if when:
        return "Leave out: " + (when if len(when) <= 48 else when[:47] + "\u2026")
    return "Leave out"


def exclusion_card(index, fields, names=None):
    """
    One rule: which combinations it is about, what kind of exclusion it is, and
    what it has found once checked.

    Args:
        index (int): position of the card, which is what its components are
            keyed by: a rule needs no id, so the position is its identity here.
        fields (dict): what the card shows (see card_fields).
        names (list): what a rule can read here, as ``$name`` (see
            readable_names), for placeholders that speak of this architecture.
    """
    when_placeholder, require_placeholder = placeholders(names)
    head = html.Div(
        children=[
            html.Span(
                card_title(fields.get("id"), fields.get("when")),
                id={"type": "arch-exclusion-title", "index": index},
                className="odx-card-name odx-override-title",
            ),
            ui.delete_button(
                id={"type": "arch-delete-exclusion", "index": index},
                tooltip="Remove this exclusion",
            ),
        ],
        className="odx-card-head odx-override-head",
    )

    body = html.Div(
        children=[
            ui.form_field(
                label="When",
                id={"type": "arch-exclusion-when", "index": index},
                value=fields.get("when", ""),
                placeholder=when_placeholder,
                type="text",
                tooltip=WHEN_TOOLTIP,
                tooltip_options="secondary large",
                className="odx-expression-field",
            ),
            ui.form_field(
                label="Require",
                id={"type": "arch-exclusion-require", "index": index},
                value=fields.get("require", ""),
                placeholder=require_placeholder,
                type="text",
                tooltip=REQUIRE_TOOLTIP,
                tooltip_options="secondary large",
                className="odx-expression-field",
            ),
            html.Div(
                children=[
                    kind_field(index, fields.get("kind") or ILLEGAL),
                    ui.form_field(
                        label="Id",
                        id={"type": "arch-exclusion-id", "index": index},
                        value=fields.get("id", ""),
                        placeholder="Optional, e.g. overlap-single-port",
                        type="text",
                        tooltip="How a DSE campaign turns this one rule off (\"ignore\"), and how a "
                                "run names it when it says what it left out.",
                    ),
                ],
                className="odx-field-row",
            ),
            ui.form_field(
                label="Message",
                id={"type": "arch-exclusion-message", "index": index},
                value=fields.get("message", ""),
                placeholder="Why, shown when a combination is left out",
                type="text",
                tooltip="Why these combinations are left out, said by a run when it leaves one out.",
            ),
            html.Div(id={"type": "arch-exclusion-status", "index": index}, className="odx-exclusion-status"),
            dcc.Store(id={"type": "arch-exclusion-rest", "index": index}, data=fields.get("rest") or {}),
        ],
        className="odx-card-body",
    )

    return html.Div(
        children=[head, body],
        className="odx-card odx-override-card odx-exclusion-card",
        id={"type": "exclusion-card", "index": index},
    )


def exclusion_cards(cards, names=None):
    """The cards of an "exclusions" block, plus the add card."""
    children = [exclusion_card(index, fields, names) for index, fields in enumerate(cards or [])]
    if not children:
        children.append(html.Div(
            "Every combination of the parameter domains of this architecture is a design. Add an "
            "exclusion to leave out the ones that are not: illegal, or the same hardware as another one.",
            className="odx-panel-note odx-override-empty",
        ))
    children.append(ui.add_card(
        id="arch-add-exclusion-card",
        text="Add exclusion",
        className="horizontal odx-override-add",
    ))
    return children


def block_note(extra):
    """What a block written as a mapping says besides its rules, which the page keeps as it is."""
    if not extra:
        return None
    parts = []
    applied = extra.get("apply")
    if applied:
        applied = applied if isinstance(applied, (list, tuple)) else [applied]
        parts.append("applies " + ", ".join(str(kind) for kind in applied))
    ignored = extra.get("ignore")
    if ignored:
        ignored = ignored if isinstance(ignored, (list, tuple)) else [ignored]
        parts.append("ignores " + ", ".join(str(name) for name in ignored))
    if not parts:
        return None
    return html.Div(
        "The settings file also says what this block " + " and ".join(parts)
        + ": that is kept as written, and the check below follows it.",
        className="odx-panel-note",
    )


def exclusions_tile(declared, names=None):
    """
    The "Exclusions" tile of the architecture editor. `names` are what a rule
    can read here (see readable_names).
    """
    rules, extra = block_rules(declared)
    return html.Div([
        html.H3("Exclusions"),
        ui.caption(
            "Combinations left out",
            tooltip="The combinations of the parameter domains of this architecture that are not "
                    "designs. They are left out of every fmax or fixed-frequency sweep, simulation "
                    "sweep, DSE search and selection of the Run jobs page. Rules are written once, "
                    "here, rather than by not writing the sweep line that would produce them.",
        ),
        block_note(extra),
        html.Div(
            children=exclusion_cards([card_fields(rule) for rule in rules], names),
            id="arch-exclusion-cards-row",
            className="odx-override-cards",
        ),
        dcc.Store(id="arch-exclusions-block", data=extra),
        dcc.Store(id="arch-exclusion-names", data=[list(pair) for pair in names or []]),
        html.Div(
            children=[
                html.Button(
                    "Check against the configurations",
                    id="arch-exclusions-check",
                    n_clicks=0,
                    className="odx-mini-button",
                    title="Count what each rule leaves out of the configurations this architecture "
                          "has, as the rules are on the page, saved or not.",
                ),
                html.Div(id="arch-exclusions-summary", className="odx-exclusions-summary"),
            ],
            className="odx-exclusions-check",
        ),
    ], className="tile config")


######################################
# Checking the rules
######################################

class _Slot(object):
    """What one card has found."""

    __slots__ = ("rule", "applied", "count", "example", "error", "unknown")

    def __init__(self, rule, applied):
        self.rule = rule
        self.applied = applied
        self.count = 0
        self.example = None
        self.error = None
        #: The names it reads that nothing defines here, each with the closest
        #: one that is defined (or None), as (name, suggestion) pairs.
        self.unknown = []


def combination_axes(architecture):
    """
    The combinations of an architecture as axes rather than as a list: one
    list of selector tokens per parameter domain, plus one for its variables,
    whose product is what :meth:`Architecture.combinations` lists, in the same
    order. Returns ``(prefix, axes)``, `prefix` being the tokens every
    combination starts with.
    """
    domains = architecture.parameter_domains()
    prefix = []
    axes = []
    for domain, configurations in domains.items():
        shown = architecture.name if domain == hard_settings.main_parameter_domain else domain
        axes.append([["{0}/{1}".format(shown, configuration)] for configuration in configurations])
    if domains and list(domains)[0] != hard_settings.main_parameter_domain:
        prefix = [architecture.name]
    variables = architecture.variable_combinations()
    if variables:
        if not axes:
            prefix = [architecture.name]
        axes.append([list(tokens) for tokens in variables])
    return prefix, axes


def sample_combinations(architecture, limit):
    """
    The combinations of an architecture to check, without listing them all:
    every one of them when there are at most `limit`, else `limit` of them
    drawn at random over the whole space -- always the same ones, so that two
    checks of the same rules say the same.

    Returns:
        tuple: (how many combinations there are, the ones to check, each a
        list of selector tokens).
    """
    prefix, axes = combination_axes(architecture)
    if not axes:
        return 0, []
    total = 1
    for axis in axes:
        total *= len(axis)
    if total <= limit:
        return total, [prefix + sum(choice, []) for choice in itertools.product(*axes)]
    picked = sorted(random.Random(0).sample(range(total), limit))
    found = []
    for index in picked:
        # The last axis varies fastest, as in itertools.product.
        tokens = []
        for axis in reversed(axes):
            index, position = divmod(index, len(axis))
            tokens = axis[position] + tokens
        found.append(prefix + tokens)
    return total, found


def unknown_names(expressions, known):
    """
    The names `expressions` read that are not in `known`, each with the closest
    known one (or None), as (name, suggestion) pairs.
    """
    identifiers = {identifier_of(name): name for name in known}
    found = []
    for expression in expressions:
        for name in names_in(expression or ""):
            if name in known or identifier_of(name) in identifiers:
                continue
            if any(pair[0] == name for pair in found):
                continue
            close = difflib.get_close_matches(name, list(known), n=1, cutoff=0.6)
            found.append((name, close[0] if close else None))
    return found


def check_rules(architecture, cards, extra=None, limit=CHECK_LIMIT):
    """
    What each card leaves out of the combinations of an architecture.

    Every rule is checked on its own, so that a rule that never fires shows up
    even when another one leaves out the same combinations. The rules come from
    the page; the configurations, and what is read off them, from the disk.

    Returns:
        dict: "total" (combinations of the architecture), "checked" (how many
        were), "left_out" (how many of those the applied rules leave out),
        "slots" (a _Slot or None per card, None when the card says nothing),
        "names" (what an expression can read, with the values seen, see
        _NameSamples) and "error" (why nothing was checked, or None).
    """
    extra = extra or {}
    applied = extra.get("apply")
    if applied is not None:
        applied = applied if isinstance(applied, (list, tuple)) else [applied]
        applied = tuple(_kind(kind) for kind in applied if _text(kind))
    else:
        applied = DEFAULT_APPLIED
    ignored = extra.get("ignore") or []
    ignored = set(_text(name) for name in (ignored if isinstance(ignored, (list, tuple)) else [ignored]))

    slots = []
    for fields in cards or []:
        rule = Exclusion(
            when=_text(fields.get("when")), require=_text(fields.get("require")),
            kind=_kind(fields.get("kind")), message=_text(fields.get("message")), id=_text(fields.get("id")),
        )
        if not rule.valid:
            slots.append(None)
            continue
        slot = _Slot(rule, rule.kind in applied and rule.id not in ignored and rule.identifier not in ignored)
        for expression in (rule.when, rule.require):
            reason = syntax_error(expression)
            if reason and slot.error is None:
                slot.error = reason
        slots.append(slot)

    names = _NameSamples()
    result = {"total": 0, "checked": 0, "left_out": 0, "slots": slots, "names": names, "error": None}

    # Drawn axis by axis rather than listed: a space of millions is checked on a
    # sample spread over all of it, in the time a small one takes (AR-08).
    total, combinations = sample_combinations(architecture, limit)
    result["total"] = total
    result["checked"] = len(combinations)

    live = [slot for slot in slots if slot is not None and slot.error is None]

    excluder = ExclusionFilter.of(architecture)
    for tokens in combinations:
        entry = "+".join(tokens)
        values = excluder.context(entry)
        names.add(values)
        out = False
        for slot in live:
            if slot.error is not None:
                continue
            try:
                rejected = slot.rule.rejects(values)
            except ExpressionError as error:
                # A run reports it once and leaves nothing out: so does this.
                slot.error = error.reason
                continue
            if rejected:
                slot.count += 1
                if slot.example is None:
                    slot.example = entry
                out = out or slot.applied
        if out:
            result["left_out"] += 1

    # A name nothing defines equals nothing: the rule reading it quietly never
    # fires. Saying which name, and what it was likely meant to be, is what
    # turns a typo into something seen (AR-07).
    if combinations:
        known = set(names.samples) | set(_NameSamples.SKIPPED) | {"config", "architecture"}
        for slot in slots:
            if slot is not None and slot.error is None:
                slot.unknown = unknown_names((slot.rule.when, slot.rule.require), known)
    return result


class _NameSamples(object):
    """
    What the expressions of a rule can read, and a few of the values each name
    takes over the combinations checked.

    A configuration name is a string: "$width == 8" never holds when the
    configuration is called "8", "$width == '8'" does. Showing the values as an
    expression writes them is what makes that visible.
    """

    #: Other names of the same thing, not worth a line of their own.
    SKIPPED = ("main",)

    def __init__(self):
        self.samples = {}

    def _note(self, name, value):
        seen = self.samples.setdefault(name, [])
        if value not in seen and len(seen) <= SHOWN_VALUES:
            seen.append(value)

    def add(self, values):
        for name, value in values.items():
            if name in self.SKIPPED:
                continue
            if isinstance(value, Ref):
                # The main domain of an architecture without configurations is
                # no name at all: only what it holds is worth showing.
                if str(value) or name != "config":
                    self._note(name, str(value))
                for attribute, known in sorted(value.values.items()):
                    self._note("{0}.{1}".format(name, attribute), known)
            else:
                self._note(name, value)

    def lines(self):
        """One "$name: value, value, ..." per name, in alphabetical order."""
        lines = []
        for name in sorted(self.samples):
            values = self.samples[name]
            shown = ", ".join(repr(value) if isinstance(value, str) else str(value) for value in values[:SHOWN_VALUES])
            if len(values) > SHOWN_VALUES:
                shown += ", ..."
            lines.append(("$" + name, shown))
        return lines


def names_list(names):
    """What the rules can read, as a list under the summary."""
    lines = names.lines() if names is not None else []
    if not lines:
        return None
    return html.Div(
        children=[
            html.Div("What a rule can read here, and some of the values it takes:", className="odx-panel-caption"),
            html.Ul(
                [html.Li([html.Code(name), " ", html.Span(values)]) for name, values in lines],
                className="odx-exclusion-names",
            ),
        ],
    )


def _plural(count, word):
    return "{0:,} {1}{2}".format(count, word, "" if count == 1 else "s")


def slot_status(slot, checked):
    """What one card says once checked."""
    if slot is None:
        return html.Div("Says nothing yet: write when it applies.", className="odx-exclusion-count muted")
    if slot.error is not None:
        return ui.field_error("Cannot be evaluated, so it leaves nothing out: " + slot.error)
    if not checked:
        return None
    if slot.unknown:
        parts = []
        for name, close in slot.unknown:
            parts.append(html.Code("$" + name))
            if close:
                parts += [" (did you mean ", html.Code("$" + close), "?)"]
            parts.append(", ")
        parts[-1] = ""
        verb = "leaves out none of the {0} checked".format(_plural(checked, "combination")) if not slot.count \
            else "leaves out {0:,} of the {1}".format(slot.count, _plural(checked, "combination"))
        return html.Div(
            ["Reads "] + parts + [
                ", which nothing defines here: a name nothing defines equals nothing. It " + verb + "."
            ],
            className="odx-exclusion-count warning",
        )
    if not slot.count:
        return html.Div(
            "Leaves out none of the {0} checked. Check the names it reads against the list "
            "below: a name nothing defines equals nothing, and a configuration name is a string "
            "('8', not 8).".format(_plural(checked, "combination")),
            className="odx-exclusion-count warning",
        )
    if slot.rule.kind == DOMINATED and not slot.applied:
        verb = "Would leave out"
        tail = " A dominated combination is only left out by a DSE campaign that asks for it."
    elif not slot.applied:
        verb = "Would leave out"
        tail = " The block says not to apply it."
    else:
        verb = "Leaves out"
        tail = ""
    return html.Div(
        [
            "{0} {1:,} of the {2}, e.g. ".format(verb, slot.count, _plural(checked, "combination")),
            html.Code(slot.example),
            "." + tail,
        ],
        className="odx-exclusion-count",
    )


def check_summary(result):
    """The line under the cards, once checked."""
    if result["error"]:
        return ui.error(result["error"])
    total, checked = result["total"], result["checked"]
    if not total:
        return html.Div(
            "This architecture has no parameter domain to combine yet: there is nothing to leave out.",
            className="odx-panel-note",
        )
    spread = "" if checked == total else " out of {0:,}, drawn at random over the whole space".format(total)
    left = checked - result["left_out"]
    # The line is only as green as its worst rule: one that cannot be read,
    # or that leaves nothing out, is said here too, not only on its card.
    slots = [slot for slot in result.get("slots") or [] if slot is not None]
    unreadable = sum(1 for slot in slots if slot.error is not None)
    unknown = sum(1 for slot in slots if slot.error is None and slot.unknown)
    inert = sum(1 for slot in slots if slot.error is None and not slot.unknown and not slot.count)
    problems = []
    if unreadable:
        problems.append("{0} cannot be read".format(_plural(unreadable, "rule")))
    if unknown:
        problems.append("{0} {1} a name nothing defines".format(
            _plural(unknown, "rule"), "reads" if unknown == 1 else "read"))
    if inert:
        problems.append("{0} {1} nothing out".format(_plural(inert, "rule"), "leaves" if inert == 1 else "leave"))
    level = "error" if unreadable else "warning" if problems else "success"
    text = "{0} checked{1}: {2:,} left out, {3:,} left.".format(
        _plural(checked, "combination"), spread, result["left_out"], left,
    )
    if problems:
        text += " " + "; ".join(problems).capitalize() + ": see the cards above."
    text += " The rules are checked as they are on the page; the configurations, as they are saved."
    return [
        html.Div(text, className="odx-message " + level),
        names_list(result.get("names")),
    ]


######################################
# Callbacks
######################################

def _fields_states(prefix="arch-exclusion-"):
    return [
        State({"type": prefix + "id", "index": dash.ALL}, "value"),
        State({"type": prefix + "kind", "index": dash.ALL}, "value"),
        State({"type": prefix + "when", "index": dash.ALL}, "value"),
        State({"type": prefix + "require", "index": dash.ALL}, "value"),
        State({"type": prefix + "message", "index": dash.ALL}, "value"),
        State({"type": prefix + "rest", "index": dash.ALL}, "data"),
    ]


@dash.callback(
    Output("arch-exclusion-cards-row", "children"),
    Input("arch-add-exclusion-card", "n_clicks"),
    Input({"type": "arch-delete-exclusion", "index": dash.ALL}, "n_clicks"),
    *_fields_states(),
    State("arch-exclusion-names", "data"),
    prevent_initial_call=True,
)
def add_or_delete_exclusion(add_click, delete_clicks, ids, kinds, whens, requires, messages, rests, names):
    """
    Add an empty rule, or drop the one whose delete button was hit.

    The cards are keyed by position, so deleting one renumbers the ones after
    it: they are rebuilt from the values of the page rather than moved around,
    which keeps a card's contents with the rule they belong to. An empty card is
    kept, since it is being written.
    """
    cards = cards_from_values(ids, kinds, whens, requires, messages, rests)
    triggered_id = ctx.triggered_id

    if triggered_id == "arch-add-exclusion-card" and add_click:
        cards.append({"kind": ILLEGAL})
    elif isinstance(triggered_id, dict) and triggered_id.get("type") == "arch-delete-exclusion":
        # A card that has just been added brings its delete button along, which
        # fires this callback with no click of its own.
        triggered = ctx.triggered[0] if ctx.triggered else {}
        index = triggered_id.get("index")
        if triggered.get("value") and isinstance(index, int) and index < len(cards):
            del cards[index]
        else:
            raise dash.exceptions.PreventUpdate
    else:
        raise dash.exceptions.PreventUpdate

    return exclusion_cards(cards, names)


@dash.callback(
    Output({"type": "arch-exclusion-status", "index": dash.ALL}, "children"),
    Output("arch-exclusions-summary", "children"),
    Output({"type": "arch-exclusion-title", "index": dash.ALL}, "children"),
    Input("arch-exclusions-check", "n_clicks"),
    Input({"type": "arch-exclusion-when", "index": dash.ALL}, "value"),
    Input({"type": "arch-exclusion-require", "index": dash.ALL}, "value"),
    Input({"type": "arch-exclusion-kind", "index": dash.ALL}, "value"),
    Input({"type": "arch-exclusion-id", "index": dash.ALL}, "value"),
    State({"type": "arch-exclusion-message", "index": dash.ALL}, "value"),
    State({"type": "arch-exclusion-rest", "index": dash.ALL}, "data"),
    State("arch-exclusions-block", "data"),
    State("arch-current-name", "data"),
    State("odatix-settings", "data"),
)
def check_exclusions(n_clicks, whens, requires, kinds, ids, messages, rests, extra, arch_name, odatix_settings):
    """
    What each rule is worth: while it is written, whether its expressions can
    be read at all; on demand, what it leaves out of the combinations of the
    architecture.

    A check only holds for the rules it was made with, so editing a rule takes
    its result away rather than leaving one that no longer says the truth.
    """
    cards = cards_from_values(ids, kinds, whens, requires, messages, rests)
    titles = [card_title(fields.get("id"), fields.get("when")) for fields in cards]

    if ctx.triggered_id != "arch-exclusions-check":
        statuses = []
        for fields in cards:
            reason = card_syntax_error(fields)
            statuses.append(ui.field_error("Cannot be read: " + reason) if reason else None)
        return statuses, None, titles

    architecture = get_workspace(odatix_settings).architectures.get(arch_name) if arch_name else None
    if architecture is None:
        return [None] * len(cards), ui.error(
            "Save the architecture first: the rules are checked against the configurations it has."
        ), titles

    try:
        result = check_rules(architecture, cards, extra)
    except Exception as error:
        return [None] * len(cards), ui.error("Could not check the rules: {0}".format(error)), titles

    return [slot_status(slot, result["checked"]) for slot in result["slots"]], check_summary(result), titles


def card_syntax_error(fields):
    """Why the expressions of a card cannot be read, or None."""
    reasons = [syntax_error(_text(fields.get(key))) for key in ("when", "require")]
    return next((reason for reason in reasons if reason), None)


def save_notice(cards):
    """
    What saving the cards leaves to be said, or None: the rules written although
    they cannot be read, and the cards dropped because they say nothing.
    """
    unreadable = []
    dropped = []
    for index, fields in enumerate(cards or []):
        name = _text(fields.get("id")) or "#{0}".format(index + 1)
        if rule_of(fields) is None:
            if _text(fields.get("id")) or _text(fields.get("message")):
                dropped.append(name)
            continue
        if card_syntax_error(fields):
            unreadable.append(name)
    parts = []
    if unreadable:
        parts.append(
            "exclusion {0} cannot be read: a run reports it and leaves nothing out".format(", ".join(unreadable))
            if len(unreadable) == 1 else
            "exclusions {0} cannot be read: a run reports them and leaves nothing out".format(", ".join(unreadable))
        )
    if dropped:
        parts.append(
            "exclusion {0} has neither \"When\" nor \"Require\" and was not written".format(", ".join(dropped))
            if len(dropped) == 1 else
            "exclusions {0} have neither \"When\" nor \"Require\" and were not written".format(", ".join(dropped))
        )
    if not parts:
        return None
    return "Saved, but " + "; ".join(parts) + "."
