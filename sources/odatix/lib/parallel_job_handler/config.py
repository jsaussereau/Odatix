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
The settings of the job handler: where its sessions keep their state, where
they listen by default, which plugins they load.

They are plain values, set once by whatever embeds the handler before it starts
a session (see :func:`configure`): Odatix does it in odatix.jobs_plugin. A
daemon is another process, so the plugins it loads are handed to it on its
command line, and a plugin configures the daemon the same way it configured
the process that started it.
"""

__all__ = ["DaemonConfig", "CONFIG", "configure"]


class DaemonConfig(object):
    """The settings in effect; read them from :data:`CONFIG`, change them with :func:`configure`."""

    def __init__(self):
        #: Where a session listens when nothing else is asked for.
        self.default_host = "127.0.0.1"
        self.default_port = 8000

        #: The directory, under the workspace, holding the state of its sessions.
        self.state_dirname = ".job_sessions"
        #: The state and log files of the default session...
        self.state_file = "state.json"
        self.log_file = "daemon.log"
        #: ...and how those of a named session are built ("state.<name>.json").
        self.state_prefix = "state."
        self.state_suffix = ".json"
        self.log_prefix = "daemon."
        self.log_suffix = ".log"
        #: Whether a daemon writes its stdout to its log file unless told otherwise.
        self.log_enabled_default = False

        #: The modules a session imports when it starts, to register its handlers
        #: (see plugins). A daemon receives them on its command line.
        self.plugins = []

        #: What the programs of the package call themselves in their help.
        self.app_name = "parallel job handler"

    def as_dict(self):
        return dict(self.__dict__)


#: The settings in effect, for the whole process.
CONFIG = DaemonConfig()


def configure(**settings):
    """
    Change some settings, e.g. ``configure(state_dirname=".my_sessions")``.

    An unknown name is an error rather than a silently ignored setting.
    Plugins are added to those already set, never replaced.
    """
    for name, value in settings.items():
        if not hasattr(CONFIG, name):
            raise AttributeError("unknown job handler setting '" + str(name) + "'")
        if name == "plugins":
            for module in value or []:
                if module not in CONFIG.plugins:
                    CONFIG.plugins.append(str(module))
            continue
        setattr(CONFIG, name, value)
    return CONFIG
