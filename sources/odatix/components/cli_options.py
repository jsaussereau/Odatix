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
The options several commands take, declared once.

An option shared by two commands must read the same and mean the same in both:
same flags, same destination, same help. Each one is declared here, and a
command picks the ones it takes by name or by group.

The destination of a run option is the name of the :class:`odatix.run.RunOptions`
setting it overrides ("--jobs" lands in ``nb_jobs``, "--input" in
``settings_file``), so that a command line becomes run options without a line
of copying (see :meth:`RunOptions.from_namespace`).
"""

import argparse

from odatix.lib.settings import OdatixSettings

__all__ = ["OPTIONS", "GROUPS", "add_options", "deprecated_option"]

#: Where the default of an option comes from, when not from Odatix itself.
FROM_WORKSPACE = "of odatix.yml"
FROM_RUN_SETTINGS = "of the run settings file"


#: Every shared option, as {name: (flags, add_argument keywords)}. The name is
#: its destination, unless the keywords say otherwise.
OPTIONS = {
  ######################################
  # Every command
  ######################################
  "nobanner": (("-Q", "--nobanner"), dict(action="store_true", help="suppress printing of banner")),
  "config": (("-c", "--config"), dict(
    default=OdatixSettings.DEFAULT_SETTINGS_FILE,
    help="workspace settings file (default: " + OdatixSettings.DEFAULT_SETTINGS_FILE + ")",
  )),

  ######################################
  # Talking to the daemon
  ######################################
  "detach": (("-d", "--detach"), dict(action="store_true", help="enqueue jobs to daemon and return without attaching monitor")),
  "session": (("-S", "--session"), dict(default=None, help="daemon session name or selector")),
  "host": (("--host",), dict(default=None, help="daemon API host (default: current workspace daemon host)")),
  "port": (("--port",), dict(type=int, default=None, help="daemon API port (default: current workspace daemon port)")),
  "token": (("--token",), dict(default=None, help="session token, when an explicit --host/--port is used (default: $ODATIX_DAEMON_TOKEN)")),
  "remote": (("-R", "--remote"), dict(default=None, help="reach a session on another machine over ssh, e.g. user@host or user@host:/path/to/workspace")),
  "zombies": (("-z", "--zombies"), dict(action="store_true", help="also handle zombie sessions (unresponsive daemons and leftover state files)")),

  ######################################
  # What a run does
  ######################################
  "tool": (("-t", "--tool"), dict(default=None, help='eda tool to run (default: "default_tool" ' + FROM_WORKSPACE + ', or the only tool with a target file)')),
  # No short form: -T is --trust.
  "targets": (("--target",), dict(action="append", dest="targets", default=None, metavar="TARGET", help="target to run on, out of those the target file of the tool enables (repeatable; default: all of them)")),
  "flow": (("-f", "--flow"), dict(default=None, help="flow of the eda tool to run (default: the tool's default flow)")),
  "until": (("-u", "--until"), dict(default=None, help="last step of the flow to run, inclusive (default: the flow's default step, or all its steps)")),
  "rerun_from": (("--rerun-from",), dict(dest="rerun_from", default=None, help="re-run this step and the following ones, even if already done")),
  "overwrite": (("-o", "--overwrite"), dict(action="store_true", help='overwrite existing results (default: "overwrite" ' + FROM_RUN_SETTINGS + ')')),
  "noask": (("-y", "--noask"), dict(action="store_true", help='do not ask to continue (default: "ask_continue" ' + FROM_RUN_SETTINGS + ')')),
  "exit_when_done": (("-E", "--exit"), dict(dest="exit_when_done", action="store_true", help='exit the monitor when all jobs are done (default: "exit_when_done" ' + FROM_RUN_SETTINGS + ')')),
  "nb_jobs": (("-j", "--jobs"), dict(dest="nb_jobs", help='maximum number of parallel jobs, "auto" for the number of CPUs minus one (default: "nb_jobs" ' + FROM_RUN_SETTINGS + ')')),
  "log_size_limit": (("--logsize",), dict(dest="log_size_limit", help='size of the log history per job in the monitor (default: "log_size_limit" ' + FROM_RUN_SETTINGS + ')')),
  "check_eda_tool": (("-T", "--trust"), dict(dest="check_eda_tool", action="store_false", help="do not check the eda tool before running jobs (saves time)")),
  "debug": (("-D", "--debug"), dict(action="store_true", help="enable debug mode to help troubleshoot settings files")),
  "keep": (("-k", "--keep"), dict(action="store_true", help="store the batch with a timestamp in the configuration name")),
  "resume": (("-r", "--resume"), dict(action="store_true", help="resume from existing work directories (do not delete/recreate them)")),

  ######################################
  # Where things are
  ######################################
  "settings_file": (("-i", "--input"), dict(dest="settings_file", default=None, help="run settings file (default: the one " + FROM_WORKSPACE + " names for this command)")),
  "arch_path": (("-a", "--archpath"), dict(dest="arch_path", help='architecture directory (default: "arch_path" ' + FROM_WORKSPACE + ')')),
  "sim_path": (("-s", "--simpath"), dict(dest="sim_path", help='simulation directory (default: "sim_path" ' + FROM_WORKSPACE + ')')),
  "workflow_path": (("-p", "--workflowpath"), dict(dest="workflow_path", help='workflow directory (default: "workflow_path" ' + FROM_WORKSPACE + ')')),
  "work_path": (("-w", "--work"), dict(dest="work_path", help='work directory (default: "work_path" ' + FROM_WORKSPACE + ')')),
  "result_path": (("-r", "--respath"), dict(dest="result_path", help='result directory (default: "result_path" ' + FROM_WORKSPACE + ')')),

  ######################################
  # Exporting the results
  ######################################
  "noexport": (("-e", "--noexport"), dict(action="store_true", help="do not export results after the run")),
  "metrics": (("-m", "--metrics"), dict(help="metrics definition file (default: the metrics.yml of each tool)")),
}

#: The options that always go together.
GROUPS = {
  # How a run hands its jobs over to the daemon.
  "daemon_options": ("detach", "session"),
  # Which daemon a session command talks to.
  "endpoint_options": ("host", "port", "token", "remote"),
  # What every run command accepts about how it runs.
  "run_options": ("overwrite", "noask", "exit_when_done", "nb_jobs", "log_size_limit", "debug"),
  # Where a run reads its settings and does its work.
  "path_options": ("settings_file", "work_path"),
  # What a run does with its results.
  "export_options": ("noexport",),
}


def add_options(parser, *names, **overrides):
  """
  Add shared options to a parser (or to a group of one).

  Args:
      parser: what to add them to: a parser, an argument group or a mutually
          exclusive group.
      *names: option names (see :data:`OPTIONS`) or group names (see
          :data:`GROUPS`), in the order they are added.
      **overrides: per option, the keywords that change for this command, e.g.
          ``work_path={"help": "simulation work directory"}``.
  """
  for name in names:
    if name in GROUPS:
      add_options(parser, *GROUPS[name], **overrides)
      continue
    flags, keywords = OPTIONS[name]
    keywords = dict(keywords)
    keywords.update(overrides.get(name, {}))
    parser.add_argument(*flags, **keywords)


def deprecated_option(parser, flag, replacement, action="store", **keywords):
  """
  Keep accepting a former spelling of an option for one more version.

  It does what `replacement` does, says that it is deprecated each time it is
  used, and is left out of the help, so that nobody starts using it.

  Args:
      flag (str): the former spelling ("-f").
      replacement (str): the spelling to use instead ("-y/--yes").
      action (str): "store", "store_true", "store_const" or "append", as the
          replacement takes it.
      **keywords: the add_argument keywords of the replacement (dest, nargs,
          const, ...).
  """
  base = {
    "store": argparse._StoreAction,
    "store_true": argparse._StoreTrueAction,
    "store_const": argparse._StoreConstAction,
    "append": argparse._AppendAction,
  }[action]

  class Deprecated(base):
    def __call__(self, parser, namespace, values, option_string=None):
      import odatix.lib.printc as printc

      printc.warning('"{0}" is deprecated and will be removed in a future version: use "{1}"'.format(option_string, replacement), "odatix")
      super(Deprecated, self).__call__(parser, namespace, values, option_string)

  keywords.setdefault("default", argparse.SUPPRESS)
  parser.add_argument(flag, action=Deprecated, help=argparse.SUPPRESS, **keywords)
