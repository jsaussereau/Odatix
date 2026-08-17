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
How a campaign decides what to run next.

Everything a strategy sees is a genome -- one number per axis of the space (see
:mod:`odatix.dse.space`) -- and what comes back from an evaluation is a cost
vector, all objectives turned into things to minimize. A strategy never reads a
metric, a configuration name or a settings file; it proposes places to look and
is told how they turned out.

Three of them, and the first is the one Odatix already did:

- ``exhaustive`` walks the whole space in sweep order. It is here so that a
  full sweep and a search are the same command with a different word in the
  settings, and so that a campaign can be capped by a budget whatever it does.
- ``random`` samples the space uniformly. It is the baseline any search has to
  beat, and on a space too large to sweep it is already useful on its own.
- ``genetic`` keeps the designs that turned out well and looks around them. It
  is the one that makes an exploration worth its name.

Each strategy is handed a random source it does not own, so a campaign given a
seed runs the same way twice -- which matters when an evaluation costs an hour
of synthesis and the question is whether a change in the rules changed the
answer.
"""

import itertools

from odatix.dse.objectives import crowding_distances, non_dominated_sort

__all__ = ["Strategy", "ExhaustiveSearch", "RandomSearch", "GeneticSearch", "STRATEGIES", "strategy_for"]


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


######################################
# Sweeping
######################################

class ExhaustiveSearch(Strategy):
    """
    Every design of the space, in the order a sweep runs them.

    Which is to say: what Odatix has always done, said as a search. A campaign
    running this one with a budget larger than the space does exactly the same
    work as "odatix fmax" over the whole architecture, and stops early when the
    budget is smaller.
    """

    name = "exhaustive"

    def __init__(self, space, rng, **options):
        super(ExhaustiveSearch, self).__init__(space, rng, **options)
        self._remaining = space.genomes()
        self._done = False

    def propose(self, count):
        batch = [tuple(genome) for genome in itertools.islice(self._remaining, max(0, int(count)))]
        if not batch:
            self._done = True
        return batch

    @property
    def exhausted(self):
        return self._done


######################################
# Sampling
######################################

class RandomSearch(Strategy):
    """
    Designs drawn uniformly from the space.

    It learns nothing, which is the point: it is what a real search is compared
    against, and on a space of a million designs it still says more in fifty
    evaluations than a sweep that will never finish.
    """

    name = "random"

    def propose(self, count):
        return [
            tuple(self.rng.randrange(length) for length in self.space.lengths)
            for _ in range(max(0, int(count)))
        ]


######################################
# Searching
######################################

class GeneticSearch(Strategy):
    """
    A search that keeps what worked and looks around it.

    The population is ranked the way NSGA-II ranks it: first by the front a
    design belongs to -- how many other designs dominate it -- and, within a
    front, by how much room it has around it, so that the search spreads along
    the trade-off curve instead of piling into one end of it (see
    :func:`~odatix.dse.objectives.crowding_distances`).

    Only the best designs are kept, and that is where the search gets its pull:
    a parent is drawn out of a bounded population, so the odds of looking around
    a good design stay the same however long the search runs. Keeping everything
    ever evaluated instead would dilute those odds batch after batch, and an
    exploration would drift back towards sampling at random. What is dropped is
    not lost -- it is in the archive, and the campaign never runs it again -- it
    just stops being something the search looks around.

    A child comes from two parents drawn by tournament: each gene is taken from
    one of them, then changed with a small probability to another value of its
    axis. Nothing here is specific to hardware -- what makes it work on a
    parameter space is that a gene is a choice along one variable, so a child
    of a wide-and-fast design and a narrow-and-small one is a design that is
    wide and small, which is exactly the question an architect is asking.

    The first batch is drawn at random: with nothing evaluated there is nothing
    to look around.

    Options:
        mutation (float): how often a gene is redrawn, per gene. Defaults to
            one gene per design on average, which is the usual rule of thumb.
        tournament (int): how many designs a parent is picked out of. Larger
            means a greedier search.
        population (int): how many designs the search keeps to look around.
            Defaults to four batches' worth: enough that a batch cannot take
            the whole population over on its own, small enough that a design on
            the front stays likely to be picked.
        elite (int): how many of the best designs are proposed again unchanged
            when they have not been evaluated yet. Kept at zero: Odatix never
            evaluates the same design twice, so the elite survives by being in
            the population, not by being run again.
    """

    name = "genetic"

    def __init__(self, space, rng, **options):
        super(GeneticSearch, self).__init__(space, rng, **options)
        self.population = []
        self.costs = []
        self.mutation = float(options.get("mutation") or 0.0)
        if self.mutation <= 0:
            self.mutation = 1.0 / max(1, len(space.lengths))
        self.tournament = max(2, int(options.get("tournament") or 2))
        self.size = max(2, int(options.get("population") or 0) or 4 * max(2, int(options.get("batch") or 8)))

    ######################################
    # What it knows
    ######################################

    def observe(self, evaluations):
        for evaluation in evaluations:
            if evaluation.costs is None:
                # A design that could not be measured tells the search nothing
                # about the shape of the space, only that it is not an answer.
                continue
            self.population.append(tuple(evaluation.genome))
            self.costs.append(evaluation.costs)
        self.select()

    def select(self):
        """
        Keep the best of the population, and nothing else.

        The batch that was just observed and what was already there are ranked
        together and cut down to size -- which is what NSGA-II calls the
        environmental selection, and what keeps the search from losing its grip
        as the archive grows.
        """
        if len(self.population) <= self.size:
            return
        kept = self.ranked()[:self.size]
        self.population = [self.population[index] for index in kept]
        self.costs = [self.costs[index] for index in kept]

    def ranked(self):
        """The population from the most promising design to the least."""
        order = []
        for front in non_dominated_sort(self.costs):
            distances = crowding_distances([self.costs[index] for index in front])
            spread = sorted(zip(front, distances), key=lambda pair: pair[1], reverse=True)
            order.extend(index for index, _distance in spread)
        return order

    ######################################
    # What it proposes
    ######################################

    def propose(self, count):
        count = max(0, int(count))
        if not self.population:
            return [
                tuple(self.rng.randrange(length) for length in self.space.lengths)
                for _ in range(count)
            ]

        order = self.ranked()
        rank = dict((index, position) for position, index in enumerate(order))
        return [self.child(rank) for _ in range(count)]

    def child(self, rank):
        """One design, from two parents and a little chance."""
        first = self.parent(rank)
        second = self.parent(rank)
        genome = [
            first[gene] if self.rng.random() < 0.5 else second[gene]
            for gene in range(len(self.space.lengths))
        ]
        return tuple(self.mutate(genome))

    def parent(self, rank):
        """
        The better of a few designs drawn at random -- better meaning further up
        the ranking, i.e. on a front nothing dominates and with room around it.
        """
        drawn = [self.rng.randrange(len(self.population)) for _ in range(self.tournament)]
        best = min(drawn, key=lambda index: rank.get(index, len(self.population)))
        return self.population[best]

    def mutate(self, genome):
        """Each gene, now and then, moved to another value of its axis."""
        for gene, length in enumerate(self.space.lengths):
            if length > 1 and self.rng.random() < self.mutation:
                # Redraw among the *other* values: a mutation that changes
                # nothing is a wasted one.
                moved = self.rng.randrange(length - 1)
                genome[gene] = moved if moved < genome[gene] else moved + 1
        return genome


######################################
# Choosing one
######################################

#: Every search strategy, by the word a settings file uses for it.
STRATEGIES = dict(
    (strategy.name, strategy) for strategy in (ExhaustiveSearch, RandomSearch, GeneticSearch)
)

#: Other words for the same strategies, so that a settings file may say what it
#: means rather than what Odatix calls it.
STRATEGY_ALIASES = {
    "sweep": "exhaustive",
    "full": "exhaustive",
    "all": "exhaustive",
    "uniform": "random",
    "ga": "genetic",
    "nsga2": "genetic",
    "evolutionary": "genetic",
}


def strategy_for(name):
    """
    The strategy class of a name, whichever of its names is used.

    Raises:
        ValueError: no strategy goes by that name.
    """
    key = str(name or "").strip().lower()
    key = STRATEGY_ALIASES.get(key, key)
    if key not in STRATEGIES:
        raise ValueError(
            "Unknown search strategy \"{0}\". Odatix searches with: {1}.".format(
                name, ", ".join(sorted(STRATEGIES))
            )
        )
    return STRATEGIES[key]
