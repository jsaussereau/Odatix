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
What is known about a configuration beyond its name.

A configuration produced by rules already carries its variables: the values it
was built from are what it *is*, and an exclusion can read them directly. A
configuration written by hand carries nothing -- it is a file with a name and a
content -- and yet what tells a pipeline topology from another is exactly the
kind of thing an exclusion needs to read ("does this one have an EX barrier?").

An ``attributes`` block bridges the two: it says how to read values off the name
or off the content of a configuration, so that a hand-written family becomes as
readable as a generated one::

    attributes:
      defaults:
        stage_EX: 0
        stage_RF: 0
      from_name: "(?:EX(?P<stage_EX>\\\\d+))?(?:RF(?P<stage_RF>\\\\d+))?"
      from_content: "p_stage_EX\\\\s*=\\\\s*(?P<stage_EX>\\\\d+)"
      values:
        "P-IF1MA1": {legacy: 1}

The regular expressions are read for their *named groups*, and nothing else: a
group that does not match leaves the attribute at its default. Values that look
like numbers are read as numbers, so ``$config.stage_EX >= 2`` compares numbers
and not strings.

The order is: defaults, then ``from_name``, then ``from_content``, then
``values``, then the variables of the rules -- the most direct knowledge wins.
"""

import re

__all__ = [
    "ATTRIBUTES_KEY",
    "Attributes",
    "parse_attributes",
    "read_value",
]

#: Where the block is declared, in the settings of an architecture or of a
#: parameter domain.
ATTRIBUTES_KEY = "attributes"


def read_value(value):
    """
    A value as an expression should compare it: a number when it reads as one,
    a boolean when it is written as one, the text otherwise.
    """
    if value is None:
        return None
    if isinstance(value, bool) or isinstance(value, int) or isinstance(value, float):
        return value
    text = str(value).strip()
    if not text:
        return text
    lowered = text.lower()
    if lowered in ("yes", "true"):
        return True
    if lowered in ("no", "false"):
        return False
    try:
        return int(text, 0) if text.lower().startswith("0x") else int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return text


def _pattern_list(declared):
    """One regular expression, or several, read as a list."""
    if declared is None:
        return []
    if isinstance(declared, (list, tuple)):
        return [str(item) for item in declared if str(item).strip()]
    text = str(declared).strip()
    return [text] if text else []


class Attributes(object):
    """
    How the configurations of one parameter domain are read.

    Attributes:
        defaults (dict): what every configuration of the domain has, before
            anything is read off it.
        from_name (list): regular expressions matched against the name.
        from_content (list): regular expressions matched against the content.
        values (list): ``[(selector, {attribute: value}), ...]``, written for the
            configurations a pattern cannot reach.
        errors (list): the patterns that do not compile, as text.
    """

    def __init__(self, defaults=None, from_name=(), from_content=(), values=(), source=""):
        self.source = source
        self.defaults = {str(key): read_value(value) for key, value in (defaults or {}).items()}
        self.from_name = list(from_name)
        self.from_content = list(from_content)
        self.values = list(values)
        self.errors = []
        self._compiled_name = self._compile(self.from_name)
        self._compiled_content = self._compile(self.from_content)
        # What each configuration is worth, read once. A design space asks the
        # same question about the same configuration once per point it crosses
        # it in, and reading a name and a whole file again every time is the
        # cost of the space rather than the cost of the answer.
        self._known = {}

    def _compile(self, patterns):
        compiled = []
        for pattern in patterns:
            try:
                compiled.append(re.compile(pattern))
            except re.error as error:
                self.errors.append('"{0}": {1}'.format(pattern, error))
        return compiled

    @property
    def declared(self):
        """Whether the block says anything at all."""
        return bool(self.defaults or self.from_name or self.from_content or self.values)

    def of(self, name, content=None, variables=None):
        """
        Everything known about one configuration.

        Args:
            name (str): the name of the configuration.
            content (str): what is written in its file, when it is at hand.
            variables (dict): the values its rules produced it from, when rules
                did.

        Returns:
            dict: ``{attribute: value}``, values already read as numbers.
        """
        key = (str(name), tuple(sorted((str(k), v) for k, v in (variables or {}).items())))
        try:
            remembered = self._known.get(key)
        except TypeError:
            # A value that cannot be part of a key: read it the long way.
            return self._read_all(name, content, variables)
        if remembered is not None:
            return dict(remembered)
        found = self._read_all(name, content, variables)
        self._known[key] = found
        return dict(found)

    def _read_all(self, name, content, variables):
        found = dict(self.defaults)
        found.update(self._read(self._compiled_name, name))
        if content is not None:
            found.update(self._read(self._compiled_content, content))

        # Imported here: a selector reports what it cannot read as a message,
        # and that module is read by the selection, which reads this one.
        from odatix.workspace import selectors

        for selector, values in self.values:
            if selectors.matches(selector, str(name)):
                found.update({str(key): read_value(value) for key, value in values.items()})

        # The variables the configuration was built from are not read off
        # anything: they are what it is made of, so they have the last word.
        for key, value in (variables or {}).items():
            found[str(key)] = read_value(value)
        return found

    @staticmethod
    def _read(compiled, text):
        found = {}
        for pattern in compiled:
            for match in pattern.finditer(str(text)):
                for key, value in (match.groupdict() or {}).items():
                    if value is None:
                        continue
                    found[str(key)] = read_value(value)
        return found

    def __repr__(self):
        return "<Attributes {0} defaults, {1} patterns>".format(
            len(self.defaults), len(self.from_name) + len(self.from_content)
        )


def parse_attributes(settings, source=""):
    """
    The ``attributes`` block of a settings file, read.

    Args:
        settings (dict): content of a "_settings.yml".
        source (str): path of that file, for error messages.

    Returns:
        Attributes: the block, empty when the file declares none.
    """
    declared = None
    if isinstance(settings, dict):
        declared = settings.get(ATTRIBUTES_KEY)
    if declared is None:
        return Attributes(source=source)
    if not isinstance(declared, dict):
        # A bare regular expression: the common case is reading the name.
        return Attributes(from_name=_pattern_list(declared), source=source)

    values = []
    declared_values = declared.get("values") or {}
    if isinstance(declared_values, dict):
        for selector, mapping in declared_values.items():
            if isinstance(mapping, dict):
                values.append((str(selector), mapping))

    return Attributes(
        defaults=declared.get("defaults") or {},
        from_name=_pattern_list(declared.get("from_name")),
        from_content=_pattern_list(declared.get("from_content")),
        values=values,
        source=source,
    )
