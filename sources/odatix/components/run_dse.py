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
"odatix dse": search a design space instead of sweeping it.

The command itself does very little -- read the settings, let the flags on the
command line override them, run the exploration and report what it found. The
search is in :mod:`odatix.dse`.
"""

import argparse
import os
import sys

import odatix.lib.printc as printc
from odatix.components.cli_options import ExtendAction, add_options, deprecated_option

EXIT_SUCCESS = 0

script_name = os.path.basename(__file__)


######################################
# Arguments
######################################

def add_arguments(parser):
    """The flags "odatix dse" takes, each overriding one setting of its file."""
    # Repeatable: naming one fixes it for every design, naming several makes it
    # something the search chooses between.
    parser.add_argument("-t", "--tool", action="append", dest="tools",
                        help="tool the evaluations run with (repeatable: the search chooses)")
    parser.add_argument("-f", "--flow", action="append", dest="flows",
                        help="flow of that tool (repeatable: the search chooses)")
    parser.add_argument("--target", action="append", dest="targets",
                        help="target the evaluations run on (repeatable: the search chooses)")
    deprecated_option(parser, "-T", "--target", dest="targets", action="append")
    parser.add_argument("-p", "--campaign", action="append", dest="campaigns",
                        help="campaign to run, i.e. a file of dse_campaigns/ saying what to search, "
                             "for which objectives and how (repeatable, overrides the settings file)")
    parser.add_argument("-a", "--architecture", "--arch", action=ExtendAction, nargs="+", dest="architectures",
                        help="architectures to explore (several values, repeatable; overrides the campaign file)")
    parser.add_argument("-r", "--run", help="what evaluating one design runs (fmax_synthesis, ...)")
    parser.add_argument("-s", "--strategy", help="how the designs to evaluate are chosen: "
                                                 "exhaustive (a space small enough to measure whole), "
                                                 "random (a baseline, or a first look at a large space), "
                                                 "genetic (a large space, designs cheap to evaluate), "
                                                 "bayesian (designs that take hours to evaluate)")
    parser.add_argument("-m", "--mode", choices=["batch", "async"],
                        help="batch: decide once a whole batch is back (designs that take about as long as each other); "
                             "async: start a design as soon as a slot frees (some designs take far longer than others)")
    parser.add_argument("-b", "--budget", type=int, help="how many design points to evaluate at most")
    parser.add_argument("-B", "--batch", type=int, help="how many design points to evaluate together")
    parser.add_argument("--seed", type=int, help="make the search reproducible")
    add_options(parser, "nb_jobs", nb_jobs={"help": "maximum number of parallel jobs"})
    parser.add_argument("--no-reuse", dest="no_reuse", action="store_true",
                        help="search from nothing but what this exploration runs itself, "
                             "instead of starting from the designs of the space that are "
                             "already measured")
    add_options(parser, "overwrite", "noask", "daemon_options", "exit_when_done", "log_size_limit",
                overwrite={"help": "evaluate again what is already done"},
                exit_when_done={"help": 'exit the monitor when the exploration is done (default: "exit_when_done" of the exploration settings file)'},
                log_size_limit={"help": 'size of the log history per job in the monitor, the exploration\'s own log included (default: "log_size_limit" of the exploration settings file)'},
                detach={"help": "let the exploration run without attaching the monitor to it"})
    # Not for users: what the daemon runs to be the search itself. Everything a
    # user says has already been resolved into the settings file it is given.
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    # Its own settings file is an input, like the run settings file of the
    # other commands; -c/--config is the workspace's, as everywhere.
    add_options(parser, "settings_file", "config", settings_file={
        "dest": "config_file", "help": "exploration settings file (default: \"dse_settings_file\" of odatix.yml)",
    })
    parser.add_argument("-C", "--check", action="store_true",
                        help="say what the exploration would do, without running anything")
    return parser


def apply_arguments(settings, args):
    """
    What the command line says about the run, on top of what
    "dse_settings.yml" says.

    What it says about the campaigns themselves is applied to each of them (see
    :func:`apply_campaign_arguments`): the two files answer two questions, and
    a flag belongs to the one it changes.
    """
    value = getattr(args, "nb_jobs", None)
    if value:
        settings.nb_jobs = value
    # A number that came from a command line is a string, and the settings file
    # the exploration hands to its own jobs must say it as a number.
    if isinstance(settings.nb_jobs, str) and settings.nb_jobs.strip().isdigit():
        settings.nb_jobs = int(settings.nb_jobs.strip())
    if getattr(args, "overwrite", False):
        settings.overwrite = True
    if getattr(args, "noask", False):
        settings.ask_continue = False
    if getattr(args, "exit_when_done", False):
        settings.exit_when_done = True
    value = getattr(args, "log_size_limit", None)
    if value not in (None, ""):
        try:
            settings.log_size_limit = int(value)
        except (TypeError, ValueError):
            printc.error('"--logsize" takes a number of lines, not "{0}"'.format(value), script_name)
            sys.exit(-1)
    if getattr(args, "campaigns", None):
        settings.campaigns = list(args.campaigns)
    return settings


def apply_campaign_arguments(campaign, args):
    """What the command line says about what is searched, on top of its file."""
    value = getattr(args, "run", None)
    if value:
        campaign.run = value
    # What runs a design is one name or several, and the command line says
    # either the same way: a single "-t vivado" stays a plain name in the
    # settings file the exploration writes for itself.
    for setting, name in (("tool", "tools"), ("flow", "flows"), ("target", "targets")):
        value = getattr(args, name, None)
        if value:
            campaign[setting] = value[0] if len(value) == 1 else list(value)
    if getattr(args, "architectures", None):
        campaign.architectures = list(args.architectures)
    if getattr(args, "no_reuse", False):
        campaign.reuse_results = False

    for name in ("strategy", "mode", "budget", "batch", "seed"):
        value = getattr(args, name, None)
        if value is not None:
            campaign.search[name] = value
    return campaign


######################################
# The command
######################################

def refuse_former_config(config):
    """
    "-c/--config" used to name the exploration settings file of "odatix dse",
    and names the workspace settings file now, as for every other command.
    An exploration settings file given there is refused rather than read as a
    workspace.
    """
    if not config or not os.path.isfile(config):
        return
    from odatix.workspace.yaml_io import read_yaml

    data = read_yaml(config, default={})
    if isinstance(data, dict) and "workspace" not in data and "campaigns" in data:
        printc.error('"{0}" is an exploration settings file, and -c/--config names the workspace settings file'.format(config), script_name)
        printc.tip("give the exploration settings file with -i/--input", script_name)
        sys.exit(-1)


def command_workspace(args):
    """The workspace the exploration runs in, read from -c/--config when it names another settings file."""
    import odatix.run.cli as run_cli

    return run_cli.command_workspace(getattr(args, "config", None), script_name)


def main(args, settings=None):
    """Run the exploration the workspace describes."""
    from odatix.dse.campaign import CampaignError, Exploration
    from odatix.dse.settings import DseSettings
    from odatix.workspace import Workspace
    from odatix.workspace.errors import WorkspaceError
    from odatix.workspace.settings import load_settings

    refuse_former_config(getattr(args, "config", None))
    try:
        workspace = command_workspace(args)
    except WorkspaceError as error:
        printc.error(str(error), script_name)
        sys.exit(-1)

    settings_file = getattr(args, "config_file", None) or workspace.paths.dse_settings_file
    if not os.path.isfile(settings_file):
        printc.error("No exploration settings in \"{0}\".".format(settings_file), script_name)
        printc.note(
            "An exploration needs to be told what makes a design good and how long to look for it. "
            "Write that file, or run \"odatix init\" again to get one to start from.",
            script_name,
        )
        sys.exit(-1)

    settings = settings if settings is not None else load_settings(DseSettings, settings_file)
    apply_arguments(settings, args)

    session = getattr(args, "session", None)

    if getattr(args, "worker", False):
        # The daemon is running the search: be it (see odatix.dse.driver).
        from odatix.dse.driver import run_worker

        try:
            run_worker(workspace, settings, session)
        except CampaignError as error:
            printc.error(str(error), script_name)
            sys.exit(-1)
        return EXIT_SUCCESS

    from odatix.dse.campaigns import CampaignNotFoundError, resolve_campaigns

    try:
        selected = resolve_campaigns(workspace, settings)
    except CampaignNotFoundError as error:
        printc.error(str(error), script_name)
        sys.exit(-1)
    for campaign in selected:
        apply_campaign_arguments(campaign, args)

    exploration = Exploration(workspace, settings, session=session, campaigns=selected)
    try:
        campaigns = exploration.check()
        if getattr(args, "check", False):
            for campaign in campaigns:
                printc.say(campaign.describe(), script_name)
            return EXIT_SUCCESS
        # What the exploration is about to spend is worth showing before it
        # spends it, and this is the last moment the terminal is free: from
        # here on, everything the search says is the log of its own job.
        exploration.confirm(campaigns)
    except CampaignError as error:
        printc.error(str(error), script_name)
        sys.exit(-1)

    from odatix.dse.driver import start_exploration

    start_exploration(
        workspace, settings,
        session=session,
        detach=getattr(args, "detach", False),
        architectures=list(dict.fromkeys(campaign.name for campaign in campaigns)),
        campaigns=selected,
    )
    return EXIT_SUCCESS
