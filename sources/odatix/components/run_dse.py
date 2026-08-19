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
                        help="eda tool the evaluations run with (repeatable: the search chooses)")
    parser.add_argument("-f", "--flow", action="append", dest="flows",
                        help="flow of that tool (repeatable: the search chooses)")
    parser.add_argument("-T", "--target", action="append", dest="targets",
                        help="target the evaluations run on (repeatable: the search chooses)")
    parser.add_argument("-p", "--campaign", action="append", dest="campaigns",
                        help="campaign to run (repeatable, overrides the settings file)")
    parser.add_argument("-a", "--architecture", action="append", dest="architectures",
                        help="architecture to explore (repeatable, overrides the campaign file)")
    parser.add_argument("-r", "--run", help="what evaluating one design runs (fmax_synthesis, ...)")
    parser.add_argument("-s", "--strategy", help="how the designs to evaluate are chosen "
                                                 "(genetic, random, exhaustive, bayesian)")
    parser.add_argument("-m", "--mode", choices=["batch", "async"],
                        help="wait for a whole batch between two decisions, or fill "
                             "slots as they free up (batch, async)")
    parser.add_argument("-b", "--budget", type=int, help="how many designs to evaluate at most")
    parser.add_argument("-B", "--batch", type=int, help="how many designs to evaluate together")
    parser.add_argument("--seed", type=int, help="make the search reproducible")
    parser.add_argument("-j", "--jobs", dest="nb_jobs", help="maximum number of parallel jobs")
    parser.add_argument("-o", "--overwrite", action="store_true", help="evaluate again what is already done")
    parser.add_argument("-y", "--noask", action="store_true", help="do not ask to continue")
    parser.add_argument("-d", "--detach", action="store_true",
                        help="let the exploration run without attaching the monitor to it")
    parser.add_argument("-S", "--session", help="daemon session name or selector")
    # Not for users: what the daemon runs to be the search itself. Everything a
    # user says has already been resolved into the settings file it is given.
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("-c", "--config", dest="config_file", help="exploration settings file")
    parser.add_argument("-w", "--work", dest="work_path", help="work directory")
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

    for name in ("strategy", "mode", "budget", "batch", "seed"):
        value = getattr(args, name, None)
        if value is not None:
            campaign.search[name] = value
    return campaign


######################################
# The command
######################################

def main(args, settings=None):
    """Run the exploration the workspace describes."""
    from odatix.dse.campaign import CampaignError, Exploration
    from odatix.dse.settings import DseSettings
    from odatix.workspace import Workspace
    from odatix.workspace.errors import WorkspaceError
    from odatix.workspace.settings import load_settings

    try:
        workspace = Workspace.open()
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
