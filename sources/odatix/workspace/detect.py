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
What Odatix can guess from the sources of a design: its top level module, its
clock and reset signals, and the parameters worth exploring -- the same
guesses as the "auto detect" buttons of the graphical interface.

Every guess is a list of candidates, best first, so that a script (or an AI
agent) can take the first one or choose among them:

.. code-block:: python

    from odatix.workspace import Workspace

    ws = Workspace.open()
    arch = ws.architectures.create("Counter")
    arch.settings.rtl_path = "examples/counter"
    arch.fill_from_sources()           # top level, clock and reset
    arch.save()

    for param in arch.detect_parameters():
        print(param.name, param.value, param.relevance)

    arch.domains.create_from_parameter("WIDTH", [8, 16, 32])

Nothing here runs a tool: the sources are only read.
"""

import os

import odatix.lib.hdl_detect as hdl_detect
from odatix.lib.hdl_detect import Candidate
from odatix.workspace.errors import NotFoundError, WorkspaceError

__all__ = [
    "Candidate",
    "DetectedParameter",
    "SourceDetection",
    "detect_sources",
    "detect_parameters",
    "parameter_domain_settings",
]


class SourceDetection(object):
    """
    What the HDL sources of a directory say about their design.

    ``tops``, ``clocks`` and ``resets`` are lists of :class:`Candidate`
    (``value``, ``score``, ``detail``, ``file``), best first; ``top``,
    ``clock`` and ``reset`` the best one of each, or None. The clock and reset
    candidates are those of the top level module chosen (the one asked for,
    or the best candidate).
    """

    def __init__(self, directory, units, tops, top, clocks, resets):
        self.directory = directory
        self.units = units
        self.tops = tops
        self.top = top
        self.clocks = clocks
        self.resets = resets

    @property
    def clock(self):
        return self.clocks[0] if self.clocks else None

    @property
    def reset(self):
        return self.resets[0] if self.resets else None

    def settings(self):
        """
        The settings of an architecture these guesses fill:
        ``top_level_file``, ``top_level_module``, ``clock_signal`` and
        ``reset_signal``, for those that were found.
        """
        found = {}
        if self.top is not None:
            found["top_level_module"] = self.top.value
            if self.top.file:
                found["top_level_file"] = self.top.file.replace(os.sep, "/")
        if self.clock is not None:
            found["clock_signal"] = self.clock.value
        if self.reset is not None:
            found["reset_signal"] = self.reset.value
        return found

    def to_dict(self):
        """Everything found, as plain data (for JSON)."""
        def candidates(items):
            return [{"value": c.value, "score": round(c.score, 2), "detail": c.detail, "file": c.file} for c in items]
        return {
            "directory": self.directory,
            "top_level_module": candidates(self.tops),
            "clock_signal": candidates(self.clocks),
            "reset_signal": candidates(self.resets),
        }

    def __repr__(self):
        return "SourceDetection(top={0!r}, clock={1!r}, reset={2!r})".format(
            self.top and self.top.value, self.clock and self.clock.value, self.reset and self.reset.value)


def detect_sources(directory, top_level_module="", top_level_file="", hints=()):
    """
    Guess the top level module, the clock and the reset of the HDL sources
    (Verilog, SystemVerilog, VHDL) under ``directory``.

    Args:
        directory (str): directory holding the sources.
        top_level_module (str): the top level module, when it is already known:
            the clock and reset are then those of this module.
        top_level_file (str): the file holding the top level, when it is
            known, relative to ``directory``.
        hints (list): names the top level is likely to bear (the architecture
            name...).

    Returns:
        SourceDetection

    Raises:
        NotFoundError: the directory does not exist, or holds no HDL unit.
    """
    if not os.path.isdir(directory):
        raise NotFoundError("Source directory not found: {0}".format(directory))
    units = hdl_detect.read_directory(directory)
    if not units:
        raise NotFoundError("No Verilog, SystemVerilog or VHDL module found in {0}".format(directory))
    hints = list(hints) + [os.path.basename(os.path.normpath(directory))]
    tops = hdl_detect.top_module_candidates(units, top_level_file or "", hints)
    unit = None
    top = None
    if top_level_module:
        unit = hdl_detect.find_unit(units, top_level_module, top_level_file or "")
        if unit is None:
            raise NotFoundError("Module '{0}' not found in {1}".format(top_level_module, directory))
        top = Candidate(unit.name, 10.0, "given", unit.file)
    elif tops:
        top = tops[0]
        unit = hdl_detect.find_unit(units, top.value, top.file)
    clocks = hdl_detect.clock_candidates(unit, units) if unit is not None else []
    resets = hdl_detect.reset_candidates(unit, units) if unit is not None else []
    return SourceDetection(directory, units, tops, top, clocks, resets)


class DetectedParameter(object):
    """
    A parameter found in a source file: ``name``, ``value`` (as written),
    ``kind`` ("parameter", "localparam", "generic", "constant", "define",
    "variable", "argument"), ``line``, and ``relevance``, from 0 to 10: how
    likely it is to be worth exploring (what the design expects to be set
    from outside, with a plain value, scores highest; what is derived from
    other parameters, lowest).
    """

    def __init__(self, path, param, text, parameters):
        self.path = path
        self.name = param.name
        self.value = param.value.strip()
        self.kind = param.kind
        self.overridable = param.overridable
        self.line = hdl_detect.line_of(text, param.start)
        self.relevance = hdl_detect.parameter_relevance(param, parameters)
        self.start = param.start
        self.end = param.end

    def to_dict(self):
        return {
            "name": self.name, "value": self.value, "kind": self.kind, "line": self.line,
            "relevance": round(self.relevance, 2), "overridable": self.overridable,
        }

    def __repr__(self):
        return "DetectedParameter({0!r}, {1!r}, {2!r}, relevance={3:.1f})".format(
            self.name, self.value, self.kind, self.relevance)


def _read(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except (OSError, IOError):
        raise NotFoundError("Source file not found: {0}".format(path))


def detect_parameters(path, sort=False):
    """
    The parameters declared in a source file: HDL (Verilog, SystemVerilog,
    VHDL), C/C++ (HLS), Scala (Chisel), Python, or a configuration file.

    Args:
        path (str): the file.
        sort (bool): the most relevant first, instead of in file order.

    Returns:
        list: DetectedParameter objects.
    """
    text = _read(path)
    params = hdl_detect.detect_parameters(text, path)
    found = [DetectedParameter(path, p, text, params) for p in params]
    if sort:
        found.sort(key=lambda p: -p.relevance)
    return found


def _number(value):
    """A value as a settings file holds it: a number when it is one."""
    for kind in (int, float):
        try:
            return kind(value)
        except (TypeError, ValueError):
            pass
    return value


def parameter_domain_settings(path, parameter, values=None, target_file=""):
    """
    The settings of a parameter domain sweeping one parameter of a source
    file: delimiters isolating its value in the file, and a single variable,
    named after the parameter, listing ``values``.

    Args:
        path (str): the file declaring the parameter.
        parameter (str or DetectedParameter): the parameter.
        values (list): the values to sweep (default: its current value).
        target_file (str): the file as the domain names it, relative to the
            design directory (default: the base name of ``path``).

    Returns:
        dict: settings for ``ParameterDomainCollection.create``.

    Raises:
        NotFoundError: no such parameter in the file.
        WorkspaceError: no delimiters isolate its value.
    """
    import odatix.components.replace_params as replace_params

    text = _read(path)
    name = parameter.name if isinstance(parameter, DetectedParameter) else str(parameter)
    params = hdl_detect.detect_parameters(text, path)
    found = [p for p in params if p.name == name]
    if not found:
        raise NotFoundError("No parameter '{0}' in {1}".format(name, path))
    param = found[0]
    delimiters = hdl_detect.auto_delimiters(text, param.start, param.end, name)
    if delimiters is None:
        raise WorkspaceError(
            "No delimiters isolate the value of '{0}' in {1}: set start_delimiter and stop_delimiter by hand".format(name, path))
    if values is None:
        values = [param.value.strip()]
    if not isinstance(values, (list, tuple)):
        values = [values]
    return {
        "use_parameters": True,
        "param_target_file": target_file or os.path.basename(path),
        "start_delimiter": replace_params.delimiter_to_write(replace_params.escape_delimiter(delimiters[0])),
        "stop_delimiter": replace_params.delimiter_to_write(replace_params.escape_delimiter(delimiters[1])),
        "variables": {name: {"type": "list", "settings": {"list": [_number(v) for v in values]}}},
    }


######################################
# For an architecture
######################################

def source_directory(arch):
    """
    The directory holding the HDL sources of an architecture: its RTL path, or
    the output of its generation (which must have run once).
    """
    settings = arch.settings
    root = arch.workspace.root
    if settings.generate_rtl:
        return os.path.join(root, settings.design_path or "", settings.generate_output or "")
    # The files found are named relative to it: searched from the workspace,
    # they would be named by a path the jobs cannot follow.
    if not settings.rtl_path or os.path.realpath(os.path.join(root, settings.rtl_path)) == os.path.realpath(root):
        raise WorkspaceError(
            "Architecture '{0}': set rtl_path to the directory of its sources (e.g. \"rtl/{0}\") "
            "before detecting anything in them".format(arch.name))
    return os.path.join(root, settings.rtl_path)


def design_directory(arch):
    """The directory the files named by its domains are relative to."""
    settings = arch.settings
    path = settings.design_path if settings.generate_rtl else settings.rtl_path
    if not path:
        raise WorkspaceError(
            "Architecture '{0}' has no {1}: set it (then save(), before another script or another "
            "ws.architectures[...] reads the architecture)".format(arch.name, "design_path" if settings.generate_rtl else "rtl_path"))
    return os.path.join(arch.workspace.root, path)


def parameter_file(arch, file=None):
    """Where a file of an architecture is (its parameter target file, or its top level file, by default)."""
    settings = arch.settings
    file = file or settings.param_target_file or settings.top_level_file
    if not file:
        raise WorkspaceError("Architecture '{0}' names no top level file: set top_level_file (fill_from_sources() does, "
            "then save() before another script reads it), or name the file".format(arch.name))
    return file if os.path.isabs(file) else os.path.join(design_directory(arch), file)

