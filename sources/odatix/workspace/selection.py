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
What a run targets, and how it is written.

Every run selects what it runs the same way, whether it selects architectures,
workflows or the designs a simulation runs on::

    counter/08bits                     one configuration
    counter                            the architecture, without a configuration
    counter/*                          every configuration of the architecture
    counter/08bits+corner/tt           with one configuration of another domain
    counter/*+corner/*                 every combination of both

:func:`parse` reads one such entry, :func:`expand` turns a whole selection into
the concrete entries it stands for, looking up on disk what the wildcards match.

Nothing here prints: what a user should be told about a selection comes back as
:class:`Message` objects, so the command line, the graphical interface and a
script each report it their own way.
"""

import itertools
import os
import re

from natsort import natsorted

import odatix.lib.hard_settings as hard_settings
from odatix.lib.expressions import Ref
from odatix.workspace.attributes import parse_attributes, read_value
from odatix.workspace.configs import CONFIG_EXTENSION, configuration_names
from odatix.workspace.exclusions import expose as expose_exclusion_context, parse_exclusions
from odatix.workspace.space import config_set_at, load_domain_settings, resolved_names

__all__ = [
    "JobRequest",
    "Message",
    "parse",
    "expand",
    "domain_names",
    "ExclusionFilter",
    "NATURAL_ORDER_LIMIT",
    "filter_excluded",
]


######################################
# Messages
######################################

class Message(object):
    """
    Something a user should be told about a selection.

    `level` is one of "error", "warning", "note" or "tip", which is how Odatix
    already names what it prints. `hints` are the lines that follow it.
    """

    def __init__(self, level, text, hints=None):
        self.level = level
        self.text = text
        self.hints = list(hints) if hints else []

    def __repr__(self):
        return "<Message {0} {1!r}>".format(self.level, self.text)


######################################
# One entry of a selection
######################################

class JobRequest(object):
    """
    One entry of a run selection, read.

    Attributes:
        text (str): the entry as written, without its spaces.
        entry (str): what holds the configurations, i.e. the architecture or the
            workflow ("counter").
        configuration (str): the configuration selected ("08bits"). An entry
            that selects none names the entry itself, which is what running "the
            design with its parameters left alone" has always been written as.
        path (str): "<entry>/<configuration>", the configuration file without
            its extension.
        domains (list): the other parameter domains selected, each written
            "<domain>/<configuration>".
        has_configuration (bool): whether a configuration was actually selected.
        notes (list): what reading this entry has to tell the user.
    """

    def __init__(self, text, entry, configuration, domains, has_configuration=True, notes=None):
        self.text = text
        self.entry = entry
        self.configuration = configuration
        self.domains = list(domains)
        self.has_configuration = has_configuration
        self.notes = list(notes) if notes else []

    ######################################
    # How it is written
    ######################################

    @property
    def path(self):
        """The configuration file of the main domain, without its extension."""
        return "{0}/{1}".format(self.entry, self.configuration)

    def display_name(self, target="", only_one_target=True):
        """
        How this entry is named in what a run prints: the other domains between
        brackets, and the target too when a run has several of them.
        """
        if self.domains:
            name = "{0} [{1}]".format(self.path, ", ".join(self.domains).replace("/", ":"))
        else:
            name = self.text
        if not only_one_target:
            name = "{0} ({1})".format(name, target)
        return name

    @property
    def work_dirname(self):
        """
        The directory this entry runs in, under the one named after its entry.
        The other domains are part of it: two runs of the same configuration
        with different domains are two different results.
        """
        if not self.domains:
            return self.configuration
        return self.configuration + "+" + "+".join(self.domains).replace("/", "_")

    def with_domains(self, domains):
        """The same entry, targeting these parameter domains instead."""
        return JobRequest(
            text=self.text,
            entry=self.entry,
            configuration=self.configuration,
            domains=domains,
            has_configuration=self.has_configuration,
        )

    def __str__(self):
        if not self.domains:
            return self.path if self.has_configuration else self.entry
        return "+".join([self.path if self.has_configuration else self.entry] + self.domains)

    def __repr__(self):
        return "<JobRequest {0!r}>".format(str(self))


def parse(text, keep_extension_note=True):
    """
    Read one entry of a selection.

    Args:
        text (str): the entry, e.g. "counter/08bits+corner/tt".
        keep_extension_note (bool): report a configuration written with its
            ".txt" extension, which works but is not how it is meant to be
            written.
    """
    full = str(text).replace(" ", "")
    parts = [part.strip() for part in full.split("+")]

    path = parts[0]
    domains = parts[1:]
    notes = []

    if path.endswith(CONFIG_EXTENSION):
        path = path[:-len(CONFIG_EXTENSION)]
        if keep_extension_note:
            notes.append(
                Message("note", "'{0}' after the configuration name is not needed. Just use \"{1}\"".format(
                    CONFIG_EXTENSION, path
                ))
            )
    if path.endswith("/"):
        path = path[:-1]

    entry = re.sub("/.*", "", path)
    configuration = re.sub(".*/", "", path)

    return JobRequest(
        text=full,
        entry=entry,
        configuration=configuration,
        domains=domains,
        # "counter" alone selects no configuration: the name after the slash is
        # then the entry itself.
        has_configuration=configuration != entry or "/" in path,
        notes=notes,
    )


######################################
# Wildcards
######################################

def domain_names(root, entry):
    """The parameter domains an entry holds, i.e. its sub-directories."""
    path = os.path.join(root, entry)
    if not os.path.isdir(path):
        return []
    return natsorted([
        name for name in os.listdir(path)
        if os.path.isdir(os.path.join(path, name))
        and not name.startswith("_") and not name.startswith(".")
    ])


#: Past this many entries, a selection is a design space rather than a list,
#: and is left in the order its wildcards produced it.
NATURAL_ORDER_LIMIT = 100


class _LeftOut(object):
    """
    What the exclusions of one architecture took out of one entry of a
    selection, gathered so that it is said once per rule instead of once per
    combination.
    """

    def __init__(self, architecture):
        self.architecture = architecture
        # Rules in the order they first rejected something, each with how many
        # points it took and the first of them, which is what an example is.
        self.rules = {}
        self.order = []

    def add(self, entry, excluded):
        key = excluded.rule.identifier
        if key not in self.rules:
            self.rules[key] = [excluded.rule, 0, entry]
            self.order.append(key)
        self.rules[key][1] += 1

    def report(self, messages, strict=False):
        """
        Say what was left out, and how loudly. Asking for a combination that
        does not exist is an error; sweeping over one is a note.
        """
        if messages is None:
            return
        level = "error" if strict else "note"
        for key in self.order:
            rule, count, example = self.rules[key]
            if count == 1:
                messages.append(Message(level, '"{0}" is not part of the design space of "{1}": {2}'.format(
                    example, self.architecture, rule.describe()
                )))
                continue
            messages.append(Message(
                level,
                '{0} combinations are not part of the design space of "{1}": {2}'.format(
                    count, self.architecture, rule.describe()
                ),
                hints=['For example "{0}"'.format(example)],
            ))


def expand(requests, root, messages=None):
    """
    Turn a selection into the entries it stands for, resolving its wildcards
    against what `root` holds.

    Args:
        requests (list): the selection, as written in a run settings file.
        root (str): the directory holding the entries (the architectures of the
            workspace, or its workflows).
        messages (list): appended with the :class:`Message` objects the
            expansion produces. Errors do not stop it: what can be run is run,
            and what cannot is reported.

    Returns:
        list: one string per entry, deduplicated. In natural order, unless the
            selection stands for more entries than :data:`NATURAL_ORDER_LIMIT`,
            which are left in the order the wildcards produced them.
    """
    if messages is None:
        messages = []

    filters = {}
    expanded = []
    for text in requests or []:
        request = parse(text)
        messages.extend(request.notes)

        matched = _match_configurations(request, root, messages)
        domain_values = _match_domains(request, root, messages)

        if domain_values is None:
            continue

        before = len(expanded)
        # What this architecture says its design space does not hold. A
        # combination an exclusion rules out is not part of the sweep, whether
        # it was reached by a wildcard or written out: the difference is only in
        # how loudly it is said.
        excluder = filters.get(request.entry)
        if excluder is None:
            excluder = ExclusionFilter(root, request.entry)
            filters[request.entry] = excluder
        strict = not _has_wildcard(request)

        # A wildcard over several domains stands for the product of everything
        # it names, and a rule may take tens of thousands of those out at once.
        # Saying so once per point would bury what the run is about under its
        # own explanation, so what is left out is counted per rule and said at
        # the end of the entry -- an explicitly named point still gets its own
        # message, there being exactly one of it.
        left_out = _LeftOut(request.entry)

        if domain_values:
            domains = list(domain_values.keys())
            for path in matched:
                for combination in itertools.product(*[domain_values[domain] for domain in domains]):
                    selectors = "+".join(
                        "{0}/{1}".format(domain, value) for domain, value in zip(domains, combination)
                    )
                    entry = "{0}+{1}".format(path, selectors)
                    excluded = excluder.check(entry)
                    if excluded is None:
                        expanded.append(entry)
                    else:
                        left_out.add(entry, excluded)
        else:
            for entry in matched:
                excluded = excluder.check(entry)
                if excluded is None:
                    expanded.append(entry)
                else:
                    left_out.add(entry, excluded)

        left_out.report(messages, strict=strict)

        for message in excluder.take_errors():
            messages.append(Message("error", message))

        if _has_wildcard(request) and len(expanded) == before:
            messages.append(
                Message("warning", 'Wildcard "{0}" did not match any configuration'.format(request.text))
            )

    unique = list(dict.fromkeys(expanded))
    # Natural order is what puts "8bits" before "16bits", and it is worth what
    # it costs on the handful of entries a run usually names. On a design space
    # it is not: the entries already come out in that order -- every wildcard is
    # resolved in natural order and the product preserves it -- and sorting a
    # quarter of a million strings by natural order costs more than working out
    # which of them exist in the first place.
    if len(unique) > NATURAL_ORDER_LIMIT:
        return unique
    return natsorted(unique)


######################################
# What a sweep leaves out
######################################

MAIN_DOMAIN = hard_settings.main_parameter_domain


class ExclusionFilter(object):
    """
    The exclusions of one architecture, applied to the entries of a sweep.

    A sweep crosses the parameter domains of an architecture, and some of those
    combinations are not designs: the RTL does not build, or the very same
    hardware is described twice. Until now the only way to leave them out was
    not to write the line that produces them, once per run settings file. Here
    they are read from the architecture itself, so that a sweep and a search
    leave out exactly the same points -- and so that the reason is written down
    next to the design instead of in three settings files.

    Everything is read lazily and once: an architecture that declares no
    exclusion costs a single settings file read, which is what most of them are.
    """

    def __init__(self, root, entry, applied=None):
        self.root = root
        self.entry = entry
        self.path = os.path.join(root, entry)
        self._applied = applied
        self._exclusions = None
        self._attributes = {}
        self._configs = {}
        self._references = {}

    @staticmethod
    def of(instance):
        """
        The filter of an architecture that is already at hand, rather than of a
        directory -- what the graphical interface has.
        """
        if instance is None:
            return ExclusionFilter("", "")
        return ExclusionFilter(os.path.dirname(instance.path), instance.name)

    @property
    def exclusions(self):
        if self._exclusions is None:
            settings = load_domain_settings(self.path) if os.path.isdir(self.path) else {}
            self._exclusions = parse_exclusions(
                settings,
                source=os.path.join(self.path, "_settings.yml"),
                applied=self._applied,
            )
            self._attributes[MAIN_DOMAIN] = parse_attributes(settings)
        return self._exclusions

    @property
    def empty(self):
        """Whether this architecture leaves anything out at all."""
        return not len(self.exclusions)

    ######################################
    # What one configuration is worth
    ######################################

    def _domain_path(self, domain):
        return self.path if domain == MAIN_DOMAIN else os.path.join(self.path, domain)

    def _attributes_of(self, domain):
        if domain not in self._attributes:
            self._attributes[domain] = parse_attributes(load_domain_settings(self._domain_path(domain)))
        return self._attributes[domain]

    def _configs_of(self, domain):
        """``{name: ResolvedConfig}`` of one domain, resolved once."""
        if domain not in self._configs:
            path = self._domain_path(domain)
            found = {}
            if os.path.isdir(path):
                try:
                    for config in config_set_at(path).resolve():
                        found[config.name] = config
                except Exception:
                    found = {}
            self._configs[domain] = found
        return self._configs[domain]

    def _reference(self, domain, name):
        """
        What one configuration of one domain is worth inside an expression.

        A sweep crosses each configuration once per combination of all the other
        domains -- thousands of times over -- and what it is worth never depends
        on them. It is therefore read once and kept.
        """
        key = (domain, name)
        reference = self._references.get(key)
        if reference is None:
            known = {}
            config = self._configs_of(domain).get(name)
            content = None
            if config is not None:
                content = config.content
                known = dict(config.values or {})
            reader = self._attributes_of(domain)
            if reader.declared:
                known = reader.of(name, content, known)
            else:
                known = {variable: read_value(value) for variable, value in known.items()}
            reference = Ref(name, known)
            self._references[key] = reference
        return reference

    def context(self, entry):
        """What the expressions of an exclusion read, for one entry of a sweep."""
        request = parse(entry, keep_extension_note=False)
        references = {}
        if request.has_configuration:
            references[MAIN_DOMAIN] = self._reference(MAIN_DOMAIN, request.configuration)
        for selector in request.domains:
            domain, _, configuration = selector.partition("/")
            if domain and configuration:
                references[domain] = self._reference(domain, configuration)

        return expose_exclusion_context(self.entry, references, main_domain=MAIN_DOMAIN)

    ######################################
    # Applying them
    ######################################

    def check(self, entry):
        """Why one entry is not part of the space, or None when it is."""
        if self.empty:
            return None
        return self.exclusions.check(self.context(entry))

    def keeps(self, entry, messages=None, strict=False):
        """
        Whether one entry of a sweep is run, saying why when it is not.

        Args:
            entry (str): the entry, as a selection writes it.
            messages (list): appended with what to tell the user.
            strict (bool): the entry was written out rather than reached by a
                wildcard. Asking for a combination that does not exist is worth
                an error; sweeping over one is worth a note.
        """
        excluded = self.check(entry)
        if excluded is None:
            return True
        if messages is not None:
            text = '"{0}" is not part of the design space of "{1}": {2}'.format(
                entry, self.entry, excluded.rule.describe()
            )
            messages.append(Message("error" if strict else "note", text))
        return False

    def take_errors(self):
        """The exclusions that could not be evaluated, reported once each."""
        if self._exclusions is None:
            return []
        return self._exclusions.take_errors()

    def __repr__(self):
        return "<ExclusionFilter {0} ({1} rules)>".format(self.entry, len(self.exclusions))


def filter_excluded(entries, root, messages=None, applied=None):
    """
    The entries of a selection an architecture actually holds.

    Args:
        entries (list): entries, already expanded.
        root (str): the directory holding the architectures.
        messages (list): appended with what to tell the user.
        applied (list): which kinds of exclusion to apply (see
            :mod:`odatix.workspace.exclusions`).

    Returns:
        list: the entries that are part of the design space.
    """
    filters = {}
    left_out = {}
    kept = []
    for entry in entries or []:
        name = parse(entry, keep_extension_note=False).entry
        if name not in filters:
            filters[name] = ExclusionFilter(root, name, applied=applied)
            left_out[name] = _LeftOut(name)
        excluded = filters[name].check(entry)
        if excluded is None:
            kept.append(entry)
        else:
            left_out[name].add(entry, excluded)
    for report in left_out.values():
        report.report(messages)
    for excluder in filters.values():
        for message in excluder.take_errors():
            if messages is not None:
                messages.append(Message("error", message))
    return kept


def _has_wildcard(request):
    return _selects_every_configuration(request) or any(domain.endswith("/*") for domain in request.domains)


def _selects_every_configuration(request):
    """Whether the entry is written "<entry>/*"."""
    return request.has_configuration and request.configuration == "*"


def _match_configurations(request, root, messages):
    """The configurations of the main domain an entry selects."""
    if not _selects_every_configuration(request):
        return [request.path if request.has_configuration else request.entry]

    entry_path = os.path.join(root, request.entry)
    if not os.path.isdir(entry_path):
        messages.append(Message("error", 'The architecture directory "{0}" does not exist'.format(entry_path)))
        return []

    names = resolved_names(entry_path)
    if not names:
        messages.append(
            Message("warning", 'Wildcard "{0}" did not match any configuration in "{1}"'.format(
                request.text, entry_path
            ))
        )
    return [os.path.join(request.entry, name) for name in names]


def _match_domains(request, root, messages):
    """
    The values of each other parameter domain an entry selects, as a
    ``{domain: [configuration, ...]}`` mapping.

    An empty mapping means the entry selects no other domain; ``None`` means it
    selects domains but none of them could be resolved, which leaves nothing to
    run for this entry.
    """
    if not request.domains:
        return {}

    entry_path = os.path.join(root, request.entry)
    values = {}
    for selector in request.domains:
        if not selector.endswith("/*"):
            domain = re.sub("/.*", "", selector)
            values[domain] = [re.sub(".*/", "", selector)]
            continue

        domain = selector[:-2]
        if not os.path.isdir(entry_path):
            messages.append(Message("error", 'The architecture directory "{0}" does not exist'.format(entry_path)))
            continue

        domain_path = os.path.join(entry_path, domain)
        if not os.path.isdir(domain_path):
            existing = domain_names(root, request.entry)
            if existing:
                hint = 'Available parameter domains found in "{0}": {1}'.format(entry_path, ", ".join(existing))
            else:
                hint = 'No parameter domains found in "{0}"'.format(entry_path)
            messages.append(
                Message(
                    "error",
                    'The parameter domain directory "{0}" does not exist'.format(domain_path),
                    hints=[hint],
                )
            )
            continue

        names = resolved_names(domain_path)
        values[domain] = names
        if not names:
            messages.append(
                Message("warning", 'Wildcard "{0}" did not match any configuration in "{1}"'.format(
                    selector, domain_path
                ))
            )

    return values if values else None
