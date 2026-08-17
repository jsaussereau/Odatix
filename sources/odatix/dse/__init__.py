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
from odatix.dse.settings import DseSettings, SearchSettings
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
    "SearchSettings",
    "STRATEGIES",
    "Strategy",
    "dominates",
    "hypervolume",
    "explore",
    "pareto_front",
    "strategy_for",
]


def explore(workspace=None, **overrides):
    """
    Run the exploration a workspace describes, from beginning to end.

    Args:
        workspace (Workspace): the workspace to explore. The one of the current
            directory when not given.
        **overrides: any exploration setting, e.g. ``tool="vivado"``.

    Returns:
        list: what each campaign found, one :class:`Archive` per architecture.
    """
    from odatix.workspace import Workspace

    workspace = workspace if workspace is not None else Workspace.open()
    settings = Exploration.load(workspace)
    if overrides:
        settings.update(overrides)
    return Exploration(workspace, settings).run()
