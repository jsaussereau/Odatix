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
What a run raises when it cannot go on.

The run flows themselves report what is wrong and stop the process, which is
what a command line wants. A script does not: it gets these instead, carrying
what would have been printed.
"""

__all__ = ["RunError", "RunCancelled", "NOTHING_TO_RUN"]

#: Exit code of a run that has nothing left to do because every job it selected
#: is already done. Not a failure: the results are there, they were produced
#: earlier. A caller that can use them (the exploration does) tells this case
#: apart from a real refusal by :attr:`RunError.code`.
NOTHING_TO_RUN = 2


class RunError(Exception):
    """
    A run cannot go on: its settings are unusable, its eda tool is missing,
    there is nothing left to run...

    Attributes:
        messages (list): what the run reported before stopping, as
            ``(level, text)`` pairs, the last error being this exception's own
            message.
        code (int): the exit code the command line uses for this.
    """

    def __init__(self, message, messages=None, code=-1):
        super(RunError, self).__init__(message)
        self.messages = list(messages) if messages else []
        self.code = code

    def errors(self):
        """Only what was reported as an error."""
        return [text for level, text in self.messages if level == "error"]


class RunCancelled(Exception):
    """The run was asked to stop while it was checking or preparing its jobs."""
