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
Exporting results again, and applying the derived metrics, from a script: what
``odatix results <type>`` does on the command line.
"""

import contextlib
import io
import os
import re

import odatix.lib.printc as printc

__all__ = ["export_results", "ExportReport", "RESULT_TYPES"]

#: What :func:`export_results` exports: "all" does every other one in turn,
#: "derived" only applies the derived metrics to the results files on disk.
RESULT_TYPES = ("all", "synth", "sim", "workflow", "analysis", "derived")

# Color codes, and the "[odatix results]" prefix of every printed line.
_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_PREFIX = re.compile(r"^\[[^\]]*\]\s*")
_DIAGNOSTICS = ("error:", "internal error:", "warning:", "note:", "tip:", "error details:")


class ExportReport(object):
    """
    How an export went.

    True when it went through without a single error, so that
    ``if export_results(ws):`` reads as expected.

    Attributes:
        result_type (str): what was exported (see :data:`RESULT_TYPES`).
        ok (bool): whether it went through without reporting any error.
        messages (list): what it reported, as ``(level, text)`` pairs (level
            being "error", "warning", "note" or "tip").
        output (list): every line it printed, without color codes.
    """

    def __init__(self, result_type, ok, messages=None, output=None):
        self.result_type = result_type
        self.ok = bool(ok)
        self.messages = list(messages) if messages else []
        self.output = list(output) if output else []

    def errors(self):
        """Only what was reported as an error."""
        return [text for level, text in self.messages if level == "error"]

    def warnings(self):
        """Only what was reported as a warning."""
        return [text for level, text in self.messages if level == "warning"]

    def summary(self):
        """
        The last line the export printed that is not a diagnostic ("Derived
        metrics updated in 1 results file"), or "" when it printed none.
        """
        for line in reversed(self.output):
            text = _PREFIX.sub("", line).strip()
            if text and not text.startswith(_DIAGNOSTICS):
                return text
        return ""

    def __bool__(self):
        return self.ok

    __nonzero__ = __bool__

    def __repr__(self):
        return "<ExportReport {0} {1}>".format(self.result_type, "ok" if self.ok else "failed")


def _options(workspace, result_type, tool):
    """The options of ``odatix results <result_type>``, for this workspace."""
    from odatix.components import results_command

    args = results_command.default_arguments(result_type)
    paths = workspace.paths
    absolute = lambda path: os.path.realpath(path) if path else path

    if os.path.isfile(workspace.settings_file):
        args.config = absolute(workspace.settings_file)
    if hasattr(args, "result_path"):
        args.result_path = absolute(paths.result_path)
    if hasattr(args, "work_path"):
        if result_type == "sim":
            args.work_path = absolute(paths.under_work_path("simulation_work_path"))
        elif result_type == "workflow":
            args.work_path = absolute(paths.under_work_path("workflow_work_path"))
        else:
            args.work_path = absolute(paths.work_path)
    if result_type == "derived":
        if os.path.isfile(paths.derived_metrics_file):
            args.derived = absolute(paths.derived_metrics_file)
    else:
        args.derived_metrics_file = absolute(paths.derived_metrics_file)
    if result_type in ("all", "synth"):
        args.tool = tool
    elif result_type == "analysis" and tool not in (None, "all"):
        args.tool = list(tool) if isinstance(tool, (list, tuple)) else [tool]
    return args


def export_results(workspace, result_type="all", tool="all", quiet=False):
    """
    Export the results of the work directory again, as ``odatix results
    <result_type>`` does, or only apply the derived metrics (``"derived"``).

    Exporting is what turns the reports a job left in its work directory into
    the results files Odatix Explorer reads. Runs do it themselves; exporting
    again is for after a metric definition changed. Every export but
    ``"analysis"`` and ``"derived"`` writes a results file from scratch, and
    applies the derived metrics again right after.

    Args:
        workspace (Workspace): the workspace whose results to export.
        result_type (str): one of :data:`RESULT_TYPES`.
        tool (str): for "all" and "synth", the eda tool whose results to
            export ("all" for every one of them); for "analysis", the tool whose
            analyses to report.
        quiet (bool): print nothing; what the export said is still in the
            report.

    Returns:
        ExportReport: how it went. It is false when an error was reported, even
        if the export went on with the rest: a metric that cannot be read is a
        definition to fix.

    Raises:
        ValueError: for an unknown result type.
    """
    # Imported here: the exporters are heavy, and only an export needs them.
    from odatix.components import results_command
    from odatix.run.run import _plain_unless_terminal, _working_directory

    if result_type not in RESULT_TYPES:
        raise ValueError(
            'Unknown result type "' + str(result_type) + '": expected one of ' + ", ".join(RESULT_TYPES)
        )

    args = _options(workspace, result_type, tool)
    messages = []
    buffer = io.StringIO()

    def collect(level, message, _script_name):
        messages.append((level, message))

    printing = contextlib.redirect_stdout(buffer) if quiet else _Tee(buffer)
    with _working_directory(workspace.root), _plain_unless_terminal(), printc.collect(collect), printing:
        ok, _errors = results_command.export(result_type, args, on_exception=_report_exception)

    output = [_ANSI.sub("", line) for line in buffer.getvalue().splitlines()]
    return ExportReport(result_type, ok, messages, output)


def _report_exception(error):
    """An unexpected failure of an exporter, reported like any other error."""
    printc.internal_error(type(error).__name__ + ": " + str(error), "odatix results")


class _Tee(object):
    """Print as usual, and keep a copy of what is printed."""

    def __init__(self, buffer):
        self.buffer = buffer
        self.stream = None
        self.redirect = None

    def __enter__(self):
        import sys

        self.stream = sys.stdout
        self.redirect = contextlib.redirect_stdout(self)
        self.redirect.__enter__()
        return self

    def __exit__(self, *exc_info):
        return self.redirect.__exit__(*exc_info)

    def write(self, text):
        self.buffer.write(text)
        return self.stream.write(text)

    def flush(self):
        self.stream.flush()

    def isatty(self):
        return False
