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

import os

import odatix.lib.printc as printc
from odatix.run.errors import RunCancelled, RunError
from odatix.run.options import RunOptions
from odatix.run.run import Run

__all__ = ["command_workspace", "command_run", "execute"]


def command_workspace(config_file=None, script_name=None):
    """
    The workspace a command runs in: the one of the current directory, read
    from "-c/--config" when it names another settings file.

    A command needs one, unlike a script that may open a directory about to be
    initialized: it stops the command when there is none.
    """
    from odatix.workspace import Workspace
    from odatix.workspace.errors import WorkspaceError
    from odatix.lib.settings import OdatixSettings

    try:
        if not config_file or os.path.normpath(config_file) == Workspace.SETTINGS_FILENAME:
            return Workspace.open(required=True)
        if not os.path.isfile(config_file):
            printc.error('Settings file "' + config_file + '" does not exist', script_name)
            raise SystemExit(-1)
        # The paths of a settings file named on the command line are relative
        # to where the command runs, as they have always been.
        settings = OdatixSettings.get_settings_file_dict(config_file, silent=True)
        return Workspace.from_dict(settings if isinstance(settings, dict) else {})
    except WorkspaceError as error:
        printc.error(str(error), script_name)
        raise SystemExit(-1)


def command_run(mode, workspace=None, options=None, **overrides):
    """
    A run set up the way a command runs it: it asks before starting when its
    settings file says so, and it attaches the monitor unless asked to detach.

    Args:
        options (RunOptions): what the command line says, usually from
            :meth:`RunOptions.from_namespace`, which already holds those
            defaults.
    """
    from odatix.workspace import Workspace

    if options is None:
        options = RunOptions(**RunOptions.COMMAND_DEFAULTS)
    return Run(workspace if workspace is not None else Workspace.open(), mode, options=options, **overrides)


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
