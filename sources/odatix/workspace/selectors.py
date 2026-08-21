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
Selectors: naming several configurations at once.

A directory of configurations holds one file per configuration of the domain it
substitutes, looked up by name. That is exact, and exact is not always what is
meant: a testbench often has one set of parameters for a whole family of
configurations, and writing that family out one file per member is copying the
same thing many times.

A selector says which configurations a substitution is meant for, without naming
them one by one. They are declared in the "_settings.yml" of the directory
holding the configurations, under "match", as *selector: configuration*::

    match:
      "P*":              small_params    # every configuration whose name starts with "P"
      "$value > 7":      wide_params     # every configuration whose value is above 7
      "/^M[0-9]{4}$/":   riscv_params    # every configuration whose name matches the regex
      "*":               default_params  # everything else

Four kinds of selectors, told apart by how they are written:

- **exact** -- a plain name, matching that configuration and no other;
- **glob** -- a name holding "*", "?" or "[...]", matched with :mod:`fnmatch`;
- **regex** -- written between slashes, matched with :mod:`re` (unanchored, so
  "/^P/" and "/P/" differ);
- **expression** -- a boolean expression over "$name" and "$value" (see
  :func:`evaluate`).

Two values are available to an expression:

- ``$name``  -- the name of the configuration being run ("P8", "M0000");
- ``$value`` -- what that configuration substitutes, when it is a single number.
  A configuration substituting several parameters, or something that is not a
  number, has no ``$value``, and an expression reading it matches nothing rather
  than failing.

Both compare as numbers when both sides are numbers, and as text otherwise, so
"$name > 62" and "$name == 'P8'" both say what they look like they say.

When several selectors match the same configuration, the most specific one wins,
and declaration order settles a tie (see :func:`specificity`). A configuration
the directory holds a file (or a rule) for is not a matter of selectors at all:
that file always wins, selectors only answer for the configurations left.

Nothing here prints: what a user should be told comes back as
:class:`odatix.workspace.selection.Message` objects, the way the rest of the
workspace reports.
"""

import fnmatch
import math
import re

from odatix.workspace.selection import Message

__all__ = [
    "MATCH_KEY",
    "KIND_EXACT",
    "KIND_GLOB",
    "KIND_REGEX",
    "KIND_EXPRESSION",
    "parse",
    "kind",
    "specificity",
    "matches",
    "evaluate",
    "select",
]

#: Key the selectors are declared under, in the "_settings.yml" of a directory
#: of configurations.
MATCH_KEY = "match"

KIND_EXACT = "exact"
KIND_GLOB = "glob"
KIND_REGEX = "regex"
KIND_EXPRESSION = "expression"

#: Characters that make a selector a glob rather than a name.
GLOB_CHARACTERS = "*?["

#: What an expression may use besides "$name" and "$value". Everything else --
#: the builtins included -- is out of reach, an expression being read from a
#: settings file.
EXPRESSION_ENVIRONMENT = {"math": math}

#: What a selector is worth against the others, the higher the more specific:
#: a name is meant for one configuration, a pattern or a predicate for the ones
#: it describes, and a "*" for whatever is left.
SPECIFICITY_EXACT = 3
SPECIFICITY_SPECIFIC = 2
SPECIFICITY_CATCH_ALL = 1


######################################
# Values an expression compares
######################################

class Value(str):
    """
    A configuration name, or what it substitutes, comparing as a number when
    the comparison is between numbers.

    A domain whose configurations are named after their value ("8", "16") is
    compared with "<" and ">" as anyone would expect, and a domain whose
    configurations have names ("small", "wide") still compares with "==" and
    with the ordering of text. A comparison between a number and something that
    is not one is false rather than an error: it is a configuration the
    selector does not match, not a settings file to fix.
    """

    @property
    def number(self):
        """The value as a number, or None when it is not one."""
        try:
            return float(str(self))
        except (TypeError, ValueError):
            return None

    def _compare(self, other, numbers, texts):
        mine = self.number
        if isinstance(other, bool):
            return NotImplemented
        if isinstance(other, (int, float)):
            return numbers(mine, other) if mine is not None else False
        theirs = Value(other).number if isinstance(other, str) else None
        if mine is not None and theirs is not None:
            return numbers(mine, theirs)
        return texts(str(self), str(other))

    def __eq__(self, other):
        return self._compare(other, lambda a, b: a == b, lambda a, b: a == b)

    def __ne__(self, other):
        result = self.__eq__(other)
        return result if result is NotImplemented else not result

    def __lt__(self, other):
        return self._compare(other, lambda a, b: a < b, lambda a, b: a < b)

    def __le__(self, other):
        return self._compare(other, lambda a, b: a <= b, lambda a, b: a <= b)

    def __gt__(self, other):
        return self._compare(other, lambda a, b: a > b, lambda a, b: a > b)

    def __ge__(self, other):
        return self._compare(other, lambda a, b: a >= b, lambda a, b: a >= b)

    def __hash__(self):
        return str.__hash__(self)


def number_of(content):
    """
    What a configuration substitutes, as "$value" reads it: the single number
    its parameter file holds, or None when it holds anything else.

    A parameter file is read as it is written -- "8", or "8\\n", or a line
    holding a comment and a number is not one number and has no value.
    """
    text = str(content or "").strip()
    if not text or "\n" in text:
        return None
    return Value(text).number


######################################
# Reading a selector
######################################

def kind(selector):
    """
    Which of :data:`KIND_EXACT`, :data:`KIND_GLOB`, :data:`KIND_REGEX` and
    :data:`KIND_EXPRESSION` a selector is, told from how it is written.

    A name holding nothing special is exact, which is what makes "match" usable
    without knowing any of this: the obvious thing works, and the rest is opt-in
    through a character no configuration name holds.
    """
    text = str(selector or "").strip()
    if len(text) > 1 and text.startswith("/") and text.endswith("/"):
        return KIND_REGEX
    if "$" in text:
        return KIND_EXPRESSION
    if any(character in text for character in GLOB_CHARACTERS):
        return KIND_GLOB
    return KIND_EXACT


def specificity(selector):
    """
    How specific a selector is, the higher the more:
    :data:`SPECIFICITY_EXACT` for a name, :data:`SPECIFICITY_CATCH_ALL` for a
    glob made of nothing but wildcards, and :data:`SPECIFICITY_SPECIFIC` for
    everything in between.

    Only three ranks, because there is no honest way to tell whether "P1*" is
    meant to win over "$value > 7": between two selectors that both describe a
    family, the one written first wins (see :func:`select`), so the narrow ones
    are written above the broad ones and it reads the way it behaves.
    """
    text = str(selector or "").strip()
    selector_kind = kind(text)
    if selector_kind == KIND_EXACT:
        return SPECIFICITY_EXACT
    if selector_kind == KIND_GLOB and not text.strip("*?"):
        return SPECIFICITY_CATCH_ALL
    return SPECIFICITY_SPECIFIC


######################################
# Matching
######################################

def evaluate(expression, name, value=None, messages=None, where=""):
    """
    Whether one configuration satisfies a boolean expression over "$name" and
    "$value".

    Args:
        expression (str): the expression, "$" and "${}" alike ("$value > 7",
            "${name} == 'P8'").
        name (str): name of the configuration.
        value: what it substitutes, when that is a single number (see
            :func:`number_of`). None when it is not one, which makes an
            expression reading "$value" match nothing.
        messages (list): filled with what the user should be told about an
            expression that cannot be evaluated at all.
        where (str): how to name the selector in those messages.

    Returns:
        bool: whether the configuration satisfies it. False when it cannot be
        evaluated, so a broken selector rules configurations out instead of
        stopping the run.
    """
    text = str(expression or "")
    # Written the way every other expression of a settings file is: "$name",
    # "${name}", and "^" meaning what it means in the rest of Odatix.
    text = text.replace("^", "**").replace("${", "").replace("}", "").replace("$", "")

    environment = dict(EXPRESSION_ENVIRONMENT)
    environment["name"] = Value(name)
    if value is not None:
        environment["value"] = Value(value) if not isinstance(value, Value) else value

    try:
        # An empty mapping rather than None, so that reading a name that is not
        # there is the NameError it looks like, and not a lookup in nothing.
        return bool(eval(text, {"__builtins__": {}}, environment))
    except NameError:
        # Reading "$value" of a configuration that has none: the selector does
        # not match it, which is what it means for the value not to be there.
        return False
    except Exception as error:
        if messages is not None:
            messages.append(Message(
                "warning",
                'Selector "' + str(expression) + '"' + (" of " + where if where else "")
                + " could not be evaluated: " + str(error),
                ['A selector compares "$name" and "$value", as in "$value > 7"'],
            ))
        return False


def matches(selector, name, value=None, messages=None, where=""):
    """
    Whether one selector answers for the configuration ``name``, substituting
    ``value``.

    Args:
        selector (str): the selector, of any of the four kinds.
        name (str): name of the configuration being run.
        value: the number it substitutes, or None (see :func:`number_of`).
        messages (list): filled with what the user should be told.
        where (str): how to name the selector in those messages.
    """
    text = str(selector or "").strip()
    name = str(name)
    selector_kind = kind(text)

    if selector_kind == KIND_EXACT:
        return text == name
    if selector_kind == KIND_GLOB:
        return fnmatch.fnmatchcase(name, text)
    if selector_kind == KIND_REGEX:
        try:
            return re.search(text[1:-1], name) is not None
        except re.error as error:
            if messages is not None:
                messages.append(Message(
                    "warning",
                    'Selector ' + text + (" of " + where if where else "")
                    + " is not a valid regular expression: " + str(error),
                ))
            return False
    return evaluate(text, name, value, messages=messages, where=where)


######################################
# A "match" block
######################################

def parse(settings, messages=None, where=""):
    """
    The selectors a settings file declares, in the order they are written:
    ``[(selector, configuration), ...]``.

    Args:
        settings (dict): content of a "_settings.yml".
        messages (list): filled with what the user should be told about a block
            that says nothing usable.
        where (str): how to name the file in those messages.

    Returns:
        list: the selectors, empty when none is declared.
    """
    if not isinstance(settings, dict):
        return []
    declared = settings.get(MATCH_KEY)
    if declared is None:
        return []
    if not isinstance(declared, dict):
        if messages is not None:
            messages.append(Message(
                "error",
                '"' + MATCH_KEY + '"' + (" in " + where if where else "") + " must be a mapping",
                ['One entry per selector: "P*": the_configuration'],
            ))
        return []

    selectors = []
    for selector, target in declared.items():
        selector = str(selector or "").strip()
        target = str(target if target is not None else "").strip()
        if not selector:
            continue
        if not target:
            if messages is not None:
                messages.append(Message(
                    "error",
                    'Selector "' + selector + '"' + (" in " + where if where else "")
                    + " names no configuration to substitute",
                ))
            continue
        selectors.append((selector, target))
    return selectors


def select(selectors, name, value=None, messages=None, where=""):
    """
    The configuration a "match" block substitutes for ``name``:
    ``(selector, configuration)``, or ``(None, None)`` when none of the
    selectors answers for it.

    A name wins over a pattern and a pattern over a "*", and between two
    selectors of the same rank the first one written wins -- so a "*" placed
    anywhere stays the fallback, and the narrow selectors are written above the
    broad ones.
    """
    answered = [
        (index, selector, target)
        for index, (selector, target) in enumerate(selectors or [])
        if matches(selector, name, value, messages=messages, where=where)
    ]
    if not answered:
        return None, None
    index, selector, target = min(answered, key=lambda item: (-specificity(item[1]), item[0]))
    return selector, target
