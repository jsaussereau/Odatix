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

"""
Design space exploration: searching a space instead of sweeping it.

Odatix has always run every configuration an architecture describes. That is
the right thing to do when there are forty of them and the wrong thing when
there are forty thousand, which is what happens as soon as an architecture has
four or five parameters -- and it is exactly then that the question is worth
asking.

Nothing about the architectures changes. The parameters, the rules that produce
the configurations, the runs that synthesize them and the results they export
are the ones that were already there; a search reads the same
:class:`~odatix.workspace.space.ParameterSpace` a sweep enumerates, and runs the
same commands on the designs it picks. What is added is one settings file
saying what makes a design good and how long to look for it::

    from odatix.dse import explore

    archives = explore()          # reads odatix_userconfig/dse_settings.yml

Read from the inside out, it is four pieces:

- :mod:`odatix.dse.space` -- what there is to choose, and how a choice becomes
  something to run;
- :mod:`odatix.dse.objectives` -- what makes one design better than another,
  without ever having to say how many LUTs a megahertz is worth;
- :mod:`odatix.dse.constraints` -- what a design has to be for it to count at
  all, which is not the same question;
- :mod:`odatix.dse.strategies` -- how the next designs are chosen. A sweep is
  one of them;
- :mod:`odatix.dse.campaign` -- the loop, and when it stops.
"""

from odatix.dse.archive import Archive
from odatix.dse.bayesian import BayesianSearch
from odatix.dse.campaign import Campaign, CampaignError, Exploration
from odatix.dse.campaigns import (
    CampaignNotFoundError,
    RunSettings,
    available_campaigns,
    load_campaign,
    resolve_campaigns,
)
from odatix.dse.constraints import Constraint, Constraints
from odatix.dse.evaluation import Evaluation, EvaluationError, Evaluator
from odatix.dse.gp import GaussianProcess
from odatix.dse.objectives import (
    Costs,
    Objective,
    Objectives,
    Progress,
    dominates,
    hypervolume,
    pareto_front,
)
from odatix.dse.settings import CampaignSettings, DseSettings, SearchSettings
from odatix.dse.space import (
    ArchitectureSpace,
    Design,
    DomainSelection,
    EmptySpaceError,
)
from odatix.dse.strategies import STRATEGIES, Strategy, strategy_for

__all__ = [
    "Archive",
    "ArchitectureSpace",
    "BayesianSearch",
    "Campaign",
    "CampaignError",
    "CampaignNotFoundError",
    "CampaignSettings",
    "Constraint",
    "Constraints",
    "Costs",
    "Design",
    "DomainSelection",
    "DseSettings",
    "EmptySpaceError",
    "Evaluation",
    "EvaluationError",
    "Evaluator",
    "Exploration",
    "GaussianProcess",
    "Objective",
    "Objectives",
    "Progress",
    "RunSettings",
    "SearchSettings",
    "STRATEGIES",
    "Strategy",
    "available_campaigns",
    "dominates",
    "hypervolume",
    "explore",
    "load_campaign",
    "pareto_front",
    "resolve_campaigns",
    "strategy_for",
]


def explore(workspace=None, session=None, **overrides):
    """
    Run the exploration a workspace describes, from beginning to end, and
    return what it found.

    The search runs in the calling process: what it says is printed there, and
    the call returns once every campaign is over. The batches it decides on
    run in a daemon session like every other run -- the one named, or a new
    one started for the exploration and stopped once it is over. Follow them
    with ``odatix monitor -S <session>`` while it runs.

    Nothing is asked: a script does not answer questions on its standard input
    (pass ``ask_continue=True`` to be asked all the same).

    Args:
        workspace (Workspace): the workspace to explore. The one of the current
            directory when not given.
        session (str): the daemon session the batches run in. When it is not
            running, it is started, and stopped once the exploration is over.
            A new session is started when not given.
        **overrides: settings, each applied where it belongs:

            - a setting of the run (``dse_settings.yml``): ``campaigns``,
              ``nb_jobs``, ``overwrite``, ``log_size_limit``, ``ask_continue``;
            - a setting of the search, applied to every campaign selected
              (``search:`` of a campaign file): ``strategy``, ``mode``,
              ``budget``, ``batch``, ``seed``, ``patience``, ...;
            - any other setting of a campaign file, applied to every campaign
              selected: ``tool``, ``flow``, ``target``, ``architectures``,
              ``objectives``, ``reuse_results``, ...

    Returns:
        list: what each campaign found, one :class:`Archive` per architecture.

    Raises:
        TypeError: an override that is none of the settings above.
        CampaignError: the exploration cannot run (an unknown campaign, an
            objective naming a metric nothing measures, ...).
    """
    import odatix.lib.printc as printc
    from odatix.dse.driver import close_session, open_session
    from odatix.workspace import Workspace

    workspace = workspace if workspace is not None else Workspace.open()
    settings = Exploration.load(workspace)
    settings.ask_continue = False

    run_overrides, search_overrides, campaign_overrides = _split_overrides(overrides)
    settings.update(run_overrides)
    try:
        campaigns = resolve_campaigns(workspace, settings)
    except CampaignNotFoundError as error:
        raise CampaignError(str(error))
    for campaign in campaigns:
        for key, value in campaign_overrides.items():
            campaign[key] = value
        for key, value in search_overrides.items():
            campaign.search[key] = value

    previous_command = printc._command
    printc.set_command("odatix dse")
    try:
        # Checked before a session is started for it: an exploration that
        # cannot run should not leave a daemon behind.
        checked = Exploration(workspace, settings, campaigns=campaigns).check()
        if not any(campaign.remaining for campaign in checked):
            # Every budget is spent: nothing will be enqueued, so no session
            # is started for it. The archives are still read and returned, and
            # each campaign says it had nothing left to run.
            return Exploration(workspace, settings, session=session, campaigns=campaigns).run(confirm=False)
        session, started = open_session(workspace, settings, session)
        try:
            printc.note(
                "The batches run in session \"{0}\": follow them with "
                "\"odatix monitor -S {0}\".".format(session),
                "odatix dse",
            )
            exploration = Exploration(workspace, settings, session=session, campaigns=campaigns)
            return exploration.run(confirm=bool(settings.ask_continue))
        finally:
            close_session(workspace, session, started)
    finally:
        printc.set_command(previous_command)


def _split_overrides(overrides):
    """
    The overrides :func:`explore` was given, sorted by where they belong: the
    run, the search of each campaign, or the rest of each campaign.

    Raises:
        TypeError: one of them belongs nowhere.
    """
    run, search, campaign = {}, {}, {}
    unknown = []
    for key, value in overrides.items():
        if DseSettings.spec(key) is not None:
            run[key] = value
        elif SearchSettings.spec(key) is not None:
            search[key] = value
        elif CampaignSettings.spec(key) is not None and key != "search":
            campaign[key] = value
        else:
            unknown.append(key)
    if unknown:
        accepted = sorted(
            set(spec.key for spec in DseSettings.specs())
            | set(spec.key for spec in SearchSettings.specs())
            | set(spec.key for spec in CampaignSettings.specs() if spec.key != "search")
        )
        raise TypeError(
            "explore() got setting(s) it does not know: {0}. It accepts: {1}.".format(
                ", ".join(sorted(unknown)), ", ".join(accepted)
            )
        )
    return run, search, campaign
