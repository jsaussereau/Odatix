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
Running what a workspace holds.

:mod:`odatix.workspace` says what a workspace is configured to do; this is where
it gets done. A run goes through three steps, and stopping after any of them is
a normal thing to do::

    from odatix.workspace import Workspace
    from odatix.run import Run

    run = Run(Workspace.open(), "fmax_synthesis", tool="vivado")

    plan = run.check()          # what would be run, and what is already done
    print(plan.names())

    run.prepare()               # every work directory written, nothing started
    run.start()                 # handed over to the daemon

Nothing here exits the interpreter: what a run cannot do raises
:class:`~odatix.run.errors.RunError`, and what a user should be told about comes
back as messages. The command line turns both into what it prints and into its
exit code.
"""

from odatix.run.errors import RunCancelled, RunError
from odatix.run.options import RunOptions
from odatix.run.planner import JobPlanner
from odatix.run.reporter import CollectingReporter, Reporter, TerminalReporter
from odatix.run.run import Run, run_job

__all__ = [
    "Run",
    "run_job",
    "RunOptions",
    "RunError",
    "RunCancelled",
    "JobPlanner",
    "Reporter",
    "TerminalReporter",
    "CollectingReporter",
]
