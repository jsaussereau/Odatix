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
Running a job from a command.

A command and a script want opposite things from a failure: a script wants to
catch it, a command wants the process to stop with the right exit code. The run
API does the first; this is the one place that turns it back into the second, so
that both go through the same run.
"""

from odatix.run.errors import RunCancelled, RunError
from odatix.run.run import Run

__all__ = ["command_run", "execute"]


def command_run(mode, workspace=None, **overrides):
    """
    A run set up the way a command runs it: it asks before starting when its
    settings file says so, and it attaches the monitor unless asked to detach.
    """
    from odatix.workspace import Workspace

    defaults = {"noask": False, "detach": False}
    defaults.update(overrides)
    return Run(workspace if workspace is not None else Workspace.open(), mode, **defaults)


def execute(run):
    """
    Run it, and stop the command the way it has always stopped when it cannot.

    What went wrong has already been reported as it happened, so there is
    nothing to print here: only the exit code is left to give.
    """
    try:
        run.execute()
    except RunCancelled:
        raise SystemExit(0)
    except RunError as error:
        raise SystemExit(error.code)
    return run
