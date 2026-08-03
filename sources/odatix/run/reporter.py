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
Where what a run has to say goes.

A run talks: it says what it found cached, what it will overwrite, what it
cannot read. On a terminal that is printed as it happens, which is what the run
flows do. A script, or a graphical interface, would rather have it in hand, so
every run collects it as well.
"""

import contextlib

import odatix.lib.printc as printc

__all__ = ["Reporter", "TerminalReporter", "CollectingReporter"]


class Reporter(object):
    """
    Collects what a run reports, keeping it printed as it always was.

    Everything Odatix reports goes through :mod:`odatix.lib.printc`, so this
    listens there rather than asking the run flows to report differently.
    """

    def __init__(self):
        self.messages = []

    @contextlib.contextmanager
    def listening(self):
        """Collect everything reported inside the context."""
        with printc.collect(self._collect):
            yield self

    def _collect(self, level, message, script_name=""):
        self.messages.append((level, message))

    ######################################
    # Reading back
    ######################################

    def of_level(self, level):
        return [text for message_level, text in self.messages if message_level == level]

    @property
    def errors(self):
        return self.of_level("error")

    @property
    def warnings(self):
        return self.of_level("warning")

    def last_error(self):
        errors = self.errors
        return errors[-1] if errors else None

    def clear(self):
        self.messages = []
        return self

    def __len__(self):
        return len(self.messages)

    def __iter__(self):
        return iter(self.messages)

    def __repr__(self):
        return "<Reporter {0} messages>".format(len(self.messages))


class TerminalReporter(Reporter):
    """What the command line uses: printed as it happens, and kept."""


class CollectingReporter(Reporter):
    """
    Kept and not printed: what a script or a server wants, so that a run does
    not write to a standard output nobody is reading.
    """

    @contextlib.contextmanager
    def listening(self):
        import io

        buffer = io.StringIO()
        with printc.collect(self._collect):
            with contextlib.redirect_stdout(buffer):
                yield self
        self.output = buffer.getvalue()
