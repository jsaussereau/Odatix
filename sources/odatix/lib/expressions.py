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
The one expression language of Odatix, and how it is evaluated.

The same little language is written in several places -- the ``constraints`` of
a parameter domain, the ``exclusions`` of an architecture, a derived variable --
and it is always the same thing: a Python expression over values a run knows,
where a name is written ``$name`` or ``${name}``, and where ``^`` means what it
means in hardware, exponentiation::

    $p_rf_sp <= $p_rf_read_buf
    $Overlap == "On" and $p_fetch_buf == 1
    $config.stage_EX >= 2 and $ALU.p_alu_shift_bits < 32

A name may be *dotted*, which is how a value of another parameter domain is
reached: ``$Fwd.p_fwd_pw`` is the variable ``p_fwd_pw`` of the domain ``Fwd``,
and ``$Fwd`` alone is the name of the configuration that domain contributes.
Both work at once because a domain is handed to the expression as a
:class:`Ref`: a string -- the configuration name -- carrying the values behind
it as attributes.

Nothing here reads a file or prints anything: a caller that wants an expression
it cannot evaluate reported decides how to report it.
"""

import fnmatch
import functools
import math
import re

__all__ = [
    "ExpressionError",
    "Ref",
    "normalize",
    "names_in",
    "evaluate",
    "evaluate_bool",
    "identifier_of",
    "FUNCTIONS",
]


class ExpressionError(ValueError):
    """An expression could not be evaluated, and why."""

    def __init__(self, expression, reason):
        self.expression = expression
        self.reason = reason
        super(ExpressionError, self).__init__(
            'Failed to evaluate expression "{0}": {1}'.format(expression, reason)
        )


######################################
# Values that are a name and a record at once
######################################

class Ref(str):
    """
    What a parameter domain is worth inside an expression: the name of the
    configuration it contributes, and everything known about it.

    ``$Overlap == "On"`` compares the string. ``$Overlap.p_wb_buf`` reads one of
    the values behind it -- a variable of the rules that produced it, or an
    attribute read off its name or its content (see
    :mod:`odatix.workspace.attributes`).

    An attribute nothing defines is not an error waiting to happen: it is
    :data:`UNKNOWN`, a value that compares unequal to everything and is falsy,
    so an exclusion written for a domain that a given design does not have
    simply does not fire.
    """

    def __new__(cls, name, values=None):
        self = str.__new__(cls, "" if name is None else str(name))
        return self

    def __init__(self, name, values=None):
        str.__init__(self)
        # str is immutable, so the record rides along beside it.
        object.__setattr__(self, "values", dict(values or {}))

    def __getattr__(self, item):
        if item.startswith("__"):
            raise AttributeError(item)
        try:
            values = object.__getattribute__(self, "values")
        except AttributeError:
            raise AttributeError(item)
        if item in values:
            return values[item]
        return UNKNOWN

    def __getitem__(self, item):
        if isinstance(item, str):
            return self.values.get(item, UNKNOWN)
        return str.__getitem__(self, item)

    def __repr__(self):
        return "<Ref {0} {1}>".format(str.__repr__(self), self.values)


class _Unknown(object):
    """
    A value nothing defines.

    It is falsy, it is equal to nothing (not even to itself), and any ordering
    against it is false. An exclusion that mentions a domain the design does not
    have therefore never fires, instead of crashing the whole space.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(_Unknown, cls).__new__(cls)
        return cls._instance

    def __bool__(self):
        return False

    __nonzero__ = __bool__

    def __eq__(self, other):
        return False

    def __ne__(self, other):
        return True

    def __lt__(self, other):
        return False

    def __le__(self, other):
        return False

    def __gt__(self, other):
        return False

    def __ge__(self, other):
        return False

    def __hash__(self):
        return hash("__odatix_unknown__")

    def __getattr__(self, item):
        if item.startswith("__"):
            raise AttributeError(item)
        return self

    def __str__(self):
        return ""

    def __repr__(self):
        return "<unknown>"


#: The value of a name the context does not define.
UNKNOWN = _Unknown()


######################################
# Writing a name
######################################

#: A name as an expression writes it: "$x", "${x}", "$a.b", "${a.b}".
_REFERENCE = re.compile(r"\$\{\s*([A-Za-z_][\w.\-]*)\s*\}|\$([A-Za-z_][\w.\-]*)")


def identifier_of(name):
    """
    The identifier a name is reachable under, for a name Python cannot spell.

    A parameter domain is a directory, so it may be called "my-domain", which is
    not an identifier. It is then also bound under "my_domain", and that is what
    an expression mentioning it is rewritten to.
    """
    return _identifier_of(str(name))


@functools.lru_cache(maxsize=8192)
def _identifier_of(name):
    identifier = re.sub(r"\W", "_", name)
    if identifier and identifier[0].isdigit():
        identifier = "_" + identifier
    return identifier


def normalize(expression):
    """
    An expression as Python reads it.

    ``$name`` and ``${name}`` become the name, dots and all; ``^`` becomes
    ``**``, because a power is written ``2^n`` everywhere else in a settings
    file.

    Returns:
        str: the Python expression.
    """
    return _normalize(str(expression))


@functools.lru_cache(maxsize=4096)
def _normalize(text):

    def replace(match):
        name = match.group(1) or match.group(2)
        return ".".join(identifier_of(part) for part in name.split("."))

    text = _REFERENCE.sub(replace, text)
    # "^" is exponentiation in the rest of the settings, never a xor.
    text = text.replace("^", "**")
    return text


def names_in(expression):
    """
    The names an expression reads, dotted ones written as they are written.

    Used to say what an exclusion is about without evaluating it, and to find
    the axis a ``require`` pins.
    """
    return list(_names_in(str(expression)))


@functools.lru_cache(maxsize=4096)
def _names_in(expression):
    found = []
    for match in _REFERENCE.finditer(expression):
        name = match.group(1) or match.group(2)
        if name not in found:
            found.append(name)
    return tuple(found)


######################################
# Evaluating
######################################

def _match(text, pattern):
    """Whether a name matches a shell pattern ("P-*RF1*")."""
    if text is UNKNOWN or pattern is UNKNOWN:
        return False
    return fnmatch.fnmatchcase(str(text), str(pattern))


def _matches(text, pattern):
    """Whether a name matches a regular expression, unanchored."""
    if text is UNKNOWN or pattern is UNKNOWN:
        return False
    return re.search(str(pattern), str(text)) is not None


def _contains(haystack, needle):
    if haystack is UNKNOWN or needle is UNKNOWN:
        return False
    return str(needle) in str(haystack)


def _defined(value):
    """Whether a name the context was asked for is defined at all."""
    return value is not UNKNOWN


def _number(value, default=0):
    """A value read as a number, `default` when it is not one."""
    try:
        return int(str(value))
    except (TypeError, ValueError):
        pass
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return default


#: What an expression may call. Everything else is out of reach: the evaluation
#: runs without builtins.
FUNCTIONS = {
    "match": _match,
    "matches": _matches,
    "contains": _contains,
    "defined": _defined,
    "number": _number,
    "abs": abs,
    "min": min,
    "max": max,
    "len": len,
    "int": int,
    "float": float,
    "str": str,
    "round": round,
    "sum": sum,
    "any": any,
    "all": all,
    "sorted": sorted,
    "bool": bool,
    "math": math,
    "True": True,
    "False": False,
    "None": None,
}


class _Names(object):
    """
    The names of one point, read without being copied into an environment.

    An expression is evaluated once per point of a design space, so the values
    are handed to :func:`eval` as its local names rather than merged into a
    dictionary built for the occasion. A name written ``$domain`` that the point
    does not define reads as :data:`UNKNOWN`; a bare name -- a function, or a
    ``$`` forgotten -- is left to the environment, so that a typo is still
    reported instead of quietly never firing.
    """

    __slots__ = ("values", "roots")

    def __init__(self, values, roots):
        self.values = values
        self.roots = roots

    def __getitem__(self, name):
        values = self.values
        try:
            return values[name]
        except KeyError:
            pass
        # A name Python cannot spell is written as it is on disk ("my-domain"),
        # and reached under the identifier it was rewritten to.
        for written, value in values.items():
            if identifier_of(written) == name:
                return value
        if name in self.roots:
            return UNKNOWN
        raise KeyError(name)


#: Expressions already turned into code, by expression as it is written. The
#: same handful of rules is evaluated once per point of a design space -- tens
#: of thousands of times for a large one -- and normalizing and compiling them
#: again every time is the whole cost of walking that space.
_PREPARED = {}


def _prepared(expression):
    """
    One expression, compiled once: its code object and the root names it reads.

    Raises:
        ExpressionError: it cannot be compiled at all. Nothing is remembered
            then, so the error is raised again rather than cached as a value.
    """
    key = str(expression)
    prepared = _PREPARED.get(key)
    if prepared is None:
        try:
            code = compile(normalize(key), "<odatix expression>", "eval")
        except Exception as error:
            raise ExpressionError(key, "{0}: {1}".format(type(error).__name__, error))
        roots = tuple(dict.fromkeys(
            identifier_of(str(name).split(".")[0]) for name in names_in(key)
        ))
        prepared = (code, roots)
        _PREPARED[key] = prepared
    return prepared


def evaluate(expression, values, functions=None):
    """
    Evaluate one expression against the values of the names it reads.

    Args:
        expression (str): the expression, written with ``$name``.
        values (dict): what each name is worth. A value may be a :class:`Ref`,
            which is how a dotted name is reached.
        functions (dict): extra callables the expression may use, on top of
            :data:`FUNCTIONS`.

    Returns:
        The value of the expression.

    Raises:
        ExpressionError: it could not be evaluated -- a syntax error, an
            operation between values that do not compare, a call to something
            that is not a function.
    """
    code, roots = _prepared(expression)
    environment = dict(FUNCTIONS)
    if functions:
        environment.update(functions)
    environment["__builtins__"] = {}

    try:
        return eval(code, environment, _Names(values or {}, roots))
    except ExpressionError:
        raise
    except Exception as error:
        raise ExpressionError(expression, "{0}: {1}".format(type(error).__name__, error))


def evaluate_bool(expression, values, functions=None):
    """
    Evaluate an expression and read its result as a yes or a no.

    An empty expression is True: a rule that says nothing rules nothing out.
    """
    if expression is None or not str(expression).strip():
        return True
    return bool(evaluate(expression, values, functions=functions))
