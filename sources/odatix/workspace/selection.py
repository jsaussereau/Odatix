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

from odatix.workspace.configs import CONFIG_EXTENSION, configuration_names

__all__ = [
    "JobRequest",
    "Message",
    "parse",
    "expand",
    "domain_names",
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
    return natsorted([name for name in os.listdir(path) if os.path.isdir(os.path.join(path, name))])


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
        list: one string per entry, deduplicated and in natural order.
    """
    if messages is None:
        messages = []

    expanded = []
    for text in requests or []:
        request = parse(text)
        messages.extend(request.notes)

        matched = _match_configurations(request, root, messages)
        domain_values = _match_domains(request, root, messages)

        if domain_values is None:
            continue

        before = len(expanded)
        if domain_values:
            domains = list(domain_values.keys())
            for path in matched:
                for combination in itertools.product(*[domain_values[domain] for domain in domains]):
                    selectors = "+".join(
                        "{0}/{1}".format(domain, value) for domain, value in zip(domains, combination)
                    )
                    expanded.append("{0}+{1}".format(path, selectors))
        else:
            expanded.extend(matched)

        if _has_wildcard(request) and len(expanded) == before:
            messages.append(
                Message("warning", 'Wildcard "{0}" did not match any configuration'.format(request.text))
            )

    return natsorted(list(dict.fromkeys(expanded)))


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

    names = configuration_names(entry_path)
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

        names = configuration_names(domain_path)
        values[domain] = names
        if not names:
            messages.append(
                Message("warning", 'Wildcard "{0}" did not match any configuration in "{1}"'.format(
                    selector, domain_path
                ))
            )

    return values if values else None
