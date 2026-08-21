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

"""
The combinations of a design space that are not worth describing.

A parameter domain already says which of *its own* combinations mean something,
with the ``constraints`` of its rules. What it cannot say is anything about the
other domains: Odatix crosses them with ``+``, and until now the only way to
leave a combination of two domains out was not to write the sweep line that
would have produced it -- once per run settings file, and nowhere a search could
read it.

An ``exclusions`` block says it once, in the settings of the architecture::

    exclusions:
      - id: overlap-single-port
        when: "$Overlap == 'On' and $p_rf_sp == 1"
        kind: illegal
        message: "a single port register file cannot serve the merged write of i
                  and the read of i+1 in the same cycle"

      - id: forwarding-without-rf-barrier
        when: "$config.stage_RF == 0"
        require: "$Fwd.p_fwd_pw == 1"
        kind: duplicate

Three kinds of exclusion, because they do not mean the same thing:

``illegal``
    the design does not work -- the RTL asserts, the elaboration fails. The
    point does not exist, and asking for it explicitly is an error.

``duplicate``
    the design works, and is the very same hardware as another one: a parameter
    the rest of the configuration makes meaningless. What matters is not to drop
    it but to *pick one*, which is what ``require`` is for: it names the
    canonical value, and a search snaps to it instead of throwing the point away
    (see :meth:`Exclusion.pins`).

``dominated``
    the design works and is its own, but another one beats it on everything a
    campaign is looking for. That is knowledge about an objective, not about the
    design, so it is **not applied by default**: a campaign turns it on with
    ``exclusions: {apply: [illegal, duplicate, dominated]}``, and turns a single
    rule off by its ``id``.

An exclusion reads its values through :mod:`odatix.lib.expressions`: ``$domain``
is the name of the configuration a domain contributes, ``$domain.variable`` one
of the values behind it, ``$variable`` one of the main domain, ``$config`` the
configuration of the main domain and ``$architecture`` the architecture itself.
A name nothing defines is unknown, and an expression that reads one is false
rather than broken -- which is what lets the same block be written for a family
of architectures that do not all have the same domains.
"""

import re

from odatix.lib.expressions import ExpressionError, Ref, evaluate, evaluate_bool
from odatix.workspace.attributes import read_value

__all__ = [
    "expose",
    "EXCLUSIONS_KEY",
    "ILLEGAL",
    "DUPLICATE",
    "DOMINATED",
    "KINDS",
    "DEFAULT_APPLIED",
    "Exclusion",
    "ExclusionSet",
    "Excluded",
    "parse_exclusions",
    "context",
]

#: Where the block is declared.
EXCLUSIONS_KEY = "exclusions"

#: The design does not work.
ILLEGAL = "illegal"
#: The design is the same hardware as another one.
DUPLICATE = "duplicate"
#: The design works, but another one beats it on every objective.
DOMINATED = "dominated"

KINDS = (ILLEGAL, DUPLICATE, DOMINATED)

#: What is left out unless a campaign says otherwise. A dominated design is
#: dominated *for a question*, so it takes a question to rule it out.
DEFAULT_APPLIED = (ILLEGAL, DUPLICATE)

#: A "$name == value" of a "require", which is what a projection can snap to.
_EQUALITY = re.compile(r"^\s*\$\{?\s*([A-Za-z_][\w.\-]*)\s*\}?\s*==\s*(.+?)\s*$")


class Excluded(object):
    """
    Why one point of the space is not part of it.

    Attributes:
        rule (Exclusion): the rule that rejected it.
        pins (dict): what the rule would have the point be instead, when it
            names it -- ``{name: value}``, empty when it only rejects.
    """

    __slots__ = ("rule", "pins")

    def __init__(self, rule, pins=None):
        self.rule = rule
        self.pins = dict(pins or {})

    @property
    def kind(self):
        return self.rule.kind

    def __str__(self):
        return self.rule.describe()

    def __repr__(self):
        return "<Excluded {0}>".format(self.rule.identifier)


class Exclusion(object):
    """
    One rule of an ``exclusions`` block.

    A point is rejected when ``when`` holds and, if a ``require`` is written,
    that ``require`` does not.
    """

    __slots__ = ("id", "when", "require", "kind", "message", "source", "_pins")

    def __init__(self, when="", require="", kind=ILLEGAL, message="", id="", source=""):
        self.id = str(id or "").strip()
        self.when = str(when or "").strip()
        self.require = str(require or "").strip()
        self.kind = str(kind or ILLEGAL).strip().lower()
        if self.kind not in KINDS:
            self.kind = ILLEGAL
        self.message = str(message or "").strip()
        self.source = source
        self._pins = None

    @property
    def identifier(self):
        """How the rule is named when a campaign turns it off, or a run reports it."""
        return self.id or self.when or self.require

    @property
    def valid(self):
        """A rule that says nothing rejects nothing."""
        return bool(self.when or self.require)

    ######################################
    # What it does to a point
    ######################################

    def rejects(self, values):
        """
        Whether this rule takes one point out of the space.

        Raises:
            ExpressionError: one of its expressions could not be evaluated.
        """
        if not self.valid:
            return False
        if not evaluate_bool(self.when, values):
            return False
        if not self.require:
            return True
        return not evaluate_bool(self.require, values)

    def pins(self):
        """
        What the ``require`` of this rule fixes, when it is a plain equality --
        ``{name: value}``, empty when it is anything else.

        This is what makes a ``duplicate`` cheap to a search: rather than
        throwing away every point whose ignored parameter is not the canonical
        one, the point is moved to the canonical one, and the space keeps its
        density.
        """
        if self._pins is not None:
            return self._pins

        pins = {}
        if self.require:
            for part in re.split(r"\band\b", self.require):
                match = _EQUALITY.match(part)
                if not match:
                    pins = {}
                    break
                name, literal = match.group(1), match.group(2)
                if "$" in literal:
                    # Pinning to another name is not something a genome can be
                    # snapped to: leave it to plain rejection.
                    pins = {}
                    break
                try:
                    pins[name] = evaluate(literal, {})
                except ExpressionError:
                    pins = {}
                    break
        self._pins = pins
        return pins

    ######################################
    # How it is said
    ######################################

    def describe(self):
        """One line saying what this rule rules out, and why."""
        text = self.when or "always"
        if self.require:
            text += ' requires "{0}"'.format(self.require)
        label = "{0} ({1})".format(self.id, self.kind) if self.id else self.kind
        if self.message:
            return "{0}: {1} -- {2}".format(label, text, self.message)
        return "{0}: {1}".format(label, text)

    def to_dict(self):
        declared = {}
        if self.id:
            declared["id"] = self.id
        if self.when:
            declared["when"] = self.when
        if self.require:
            declared["require"] = self.require
        declared["kind"] = self.kind
        if self.message:
            declared["message"] = self.message
        return declared

    def __repr__(self):
        return "<Exclusion {0}>".format(self.describe())


class ExclusionSet(object):
    """
    The exclusions that apply to one architecture, and which kinds of them a run
    is applying.

    Attributes:
        rules (list): the rules, in declaration order.
        applied (tuple): the kinds that are being applied.
        ignored (set): the ids that are turned off.
        errors (list): the rules that could not be evaluated, reported once.
    """

    def __init__(self, rules=(), applied=None, ignored=(), source=""):
        self.rules = [rule for rule in rules if rule.valid]
        #: What the block itself said to apply, None when it said nothing --
        #: which is what lets a campaign leave the choice to the architecture.
        self.declared_applied = tuple(applied) if applied is not None else None
        self.applied = self.declared_applied if self.declared_applied is not None else DEFAULT_APPLIED
        self.ignored = set(str(name) for name in (ignored or []))
        self.source = source
        self.errors = []
        self._broken = set()

    ######################################
    # What is being applied
    ######################################

    def active(self):
        """The rules a run is actually applying."""
        return [
            rule for rule in self.rules
            if rule.kind in self.applied and rule.identifier not in self.ignored and rule.id not in self.ignored
        ]

    @property
    def empty(self):
        return not self.active()

    def merge(self, other):
        """
        This set, plus what a campaign says on top of it.

        The rules add up -- a campaign may write an exclusion of its own -- and
        what the campaign says about which kinds to apply and which ids to
        ignore replaces what the architecture said, because that is the decision
        a campaign is entitled to make.
        """
        if other is None:
            return self
        merged = ExclusionSet(
            list(self.rules) + list(other.rules),
            applied=other.declared_applied if other.declared_applied is not None else self.declared_applied,
            ignored=set(self.ignored) | set(other.ignored),
            source=self.source,
        )
        return merged

    def with_kinds(self, applied):
        """The same rules, applying the given kinds."""
        return ExclusionSet(self.rules, applied=applied, ignored=self.ignored, source=self.source)

    ######################################
    # Checking a point
    ######################################

    def check(self, values):
        """
        Whether one point belongs to the space.

        Args:
            values (dict): what the names of the expressions are worth, as
                :func:`context` builds it.

        Returns:
            Excluded: why the point is out, or None when it is in. A rule whose
            expression cannot be evaluated is reported once, and rejects
            nothing: a typo must not empty a space silently, and an exclusion is
            never the thing a run is about.
        """
        for rule in self.active():
            try:
                rejected = rule.rejects(values)
            except ExpressionError as error:
                if rule.identifier not in self._broken:
                    self._broken.add(rule.identifier)
                    self.errors.append(
                        'Exclusion "{0}"{1} could not be evaluated and is ignored: {2}'.format(
                            rule.identifier,
                            ' in "{0}"'.format(rule.source or self.source) if (rule.source or self.source) else "",
                            error.reason,
                        )
                    )
                continue
            if rejected:
                return Excluded(rule, rule.pins())
        return None

    def take_errors(self):
        """The evaluation errors gathered so far, cleared on the way out."""
        errors, self.errors = list(self.errors), []
        return errors

    def __len__(self):
        return len(self.active())

    def __iter__(self):
        return iter(self.active())

    def __repr__(self):
        return "<ExclusionSet {0} rules, applying {1}>".format(
            len(self.rules), ", ".join(self.applied)
        )


######################################
# Reading a block
######################################

def _rule_list(declared, source=""):
    rules = []
    if declared is None:
        return rules
    if isinstance(declared, dict):
        declared = [declared]
    if not isinstance(declared, (list, tuple)):
        declared = [declared]
    for entry in declared:
        if isinstance(entry, dict):
            rules.append(Exclusion(
                when=entry.get("when", entry.get("expr", entry.get("expression", ""))),
                require=entry.get("require", ""),
                kind=entry.get("kind", ILLEGAL),
                message=entry.get("message", ""),
                id=entry.get("id", ""),
                source=source,
            ))
        elif entry is not None and str(entry).strip():
            # A bare expression: what has to be true, the way a domain writes
            # its constraints. "when" is its negation, so it reads as a rule.
            rules.append(Exclusion(when="not ({0})".format(entry), kind=ILLEGAL, source=source))
    return rules


def parse_exclusions(settings, source="", applied=None):
    """
    The ``exclusions`` block of a settings file, read.

    Written as a list, it is the rules themselves. Written as a mapping, it also
    says what to apply::

        exclusions:
          apply: [illegal, duplicate, dominated]
          ignore: [alu-share-adder-vs-bp]
          rules:
            - when: "..."

    Args:
        settings (dict): content of a settings file, or the block itself.
        source (str): path of that file, for error messages.
        applied (list): what to apply when the block does not say.

    Returns:
        ExclusionSet: the block, empty when the file declares none.
    """
    declared = settings
    if isinstance(settings, dict) and EXCLUSIONS_KEY in settings:
        declared = settings.get(EXCLUSIONS_KEY)

    if declared is None:
        return ExclusionSet((), applied=applied, source=source)

    if isinstance(declared, dict) and (
        "rules" in declared or "apply" in declared or "ignore" in declared
    ):
        kinds = declared.get("apply")
        if kinds is not None:
            if not isinstance(kinds, (list, tuple)):
                kinds = [kinds]
            kinds = tuple(str(kind).strip().lower() for kind in kinds if str(kind).strip())
            kinds = tuple(kind for kind in kinds if kind in KINDS)
        else:
            kinds = applied
        ignored = declared.get("ignore") or []
        if not isinstance(ignored, (list, tuple)):
            ignored = [ignored]
        return ExclusionSet(
            _rule_list(declared.get("rules"), source=source),
            applied=kinds,
            ignored=[str(name).strip() for name in ignored if str(name).strip()],
            source=source,
        )

    return ExclusionSet(_rule_list(declared, source=source), applied=applied, source=source)


######################################
# What a point is worth
######################################

MAIN = "__main__"


def context(architecture, configurations, values=None, attributes=None, contents=None,
            main_domain=MAIN, extra=None):
    """
    The names an exclusion reads, for one point of the space.

    Args:
        architecture (str): name of the architecture.
        configurations (dict): ``{domain: configuration}``, the main domain
            named `main_domain`.
        values (dict): ``{variable: value}`` for the main domain,
            ``{"<domain>.<variable>": value}`` for the others -- exactly what a
            :class:`~odatix.dse.space.Design` carries.
        attributes (dict): ``{domain: Attributes}``, how the configurations of
            each domain are read (see :mod:`odatix.workspace.attributes`).
        contents (dict): ``{domain: content}``, when the configuration files are
            at hand and the attributes read them.
        main_domain (str): the key the main domain is under.
        extra (dict): anything else to expose, by name.

    Returns:
        dict: what to hand :meth:`ExclusionSet.check`.
    """
    values = dict(values or {})
    attributes = dict(attributes or {})
    contents = dict(contents or {})

    per_domain = {}
    for name, value in values.items():
        domain, _, variable = str(name).partition(".")
        if variable:
            per_domain.setdefault(domain, {})[variable] = read_value(value)
        else:
            per_domain.setdefault(main_domain, {})[domain] = read_value(value)

    built = {}
    for domain, configuration in (configurations or {}).items():
        reader = attributes.get(domain)
        known = dict(per_domain.get(domain, {}))
        if reader is not None and reader.declared:
            known = reader.of(configuration, contents.get(domain), known)
        built[domain] = Ref(configuration, known)

    # A domain that has no configuration at all -- the virtual variables of an
    # architecture, which are values and nothing else -- is still readable.
    for domain, known in per_domain.items():
        if domain not in built:
            built[domain] = Ref("", known)

    return expose(architecture, built, main_domain=main_domain, extra=extra)


def expose(architecture, references, main_domain=MAIN, extra=None):
    """
    The same names, from configurations that are already read.

    A design space crosses the same configuration of the same domain in every
    point that uses it, so a caller that walks one reads each of them once and
    assembles the context from the :class:`~odatix.lib.expressions.Ref` objects
    it already has, instead of reading names and files again per point.

    Args:
        architecture (str): name of the architecture.
        references (dict): ``{domain: Ref}``, the main domain named
            `main_domain`.
        main_domain (str): the key the main domain is under.
        extra (dict): anything else to expose, by name.

    Returns:
        dict: what to hand :meth:`ExclusionSet.check`.
    """
    built = references
    exposed = {}
    for domain, reference in built.items():
        if domain == main_domain:
            continue
        exposed[domain] = reference

    main = built.get(main_domain, Ref("", {}))
    exposed["config"] = main
    exposed["main"] = main
    exposed["architecture"] = Ref(architecture, {})
    # The variables of the main domain are read without saying which domain they
    # belong to, the way a domain writes its own constraints.
    for variable, value in main.values.items():
        exposed.setdefault(variable, value)

    if extra:
        exposed.update(extra)
    return exposed
