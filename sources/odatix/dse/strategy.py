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
What every search strategy is, before any of them says how it searches.

Kept apart from :mod:`odatix.dse.strategies` so that a strategy whose own
module is more than a page long -- :mod:`odatix.dse.bayesian`, which leans on
:mod:`odatix.dse.gp` -- can depend on :class:`Strategy` without depending on
every other strategy along with it, and without :mod:`odatix.dse.strategies`
having to depend on it back to register it.
"""

__all__ = ["Strategy"]


class Strategy(object):
    """
    A way of choosing what to evaluate next.

    A campaign asks for a batch, evaluates it, hands the results back, and asks
    again. A strategy that has nothing left to propose says so, which is how an
    exhaustive search ends before its budget does.

    Args:
        space (ArchitectureSpace): what there is to choose from.
        rng (random.Random): the campaign's random source.
        **options: what the settings file says about this strategy.
    """

    #: The word a settings file uses for it.
    name = ""

    def __init__(self, space, rng, **options):
        self.space = space
        self.rng = rng
        self.options = options

    def propose(self, count):
        """
        Up to ``count`` genomes to evaluate next.

        Fewer is allowed -- a campaign fills the gap by asking again after the
        next batch -- and none means there is nothing left to look at.
        """
        raise NotImplementedError

    def observe(self, evaluations):
        """
        How the last batch turned out.

        Args:
            evaluations (list): the :class:`~odatix.dse.evaluation.Evaluation`
                of the batch, failures included: a design that could not be
                built is something a search should learn to stay away from.
        """

    @property
    def exhausted(self):
        """Whether the strategy has run out of places to look."""
        return False

    def __repr__(self):
        return "<{0} strategy>".format(self.name)
