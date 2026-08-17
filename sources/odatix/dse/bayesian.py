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
A search that models each objective instead of only ranking what it has run,
and chooses what to try next by how much it is expected to grow the front --
not by looking around the best designs the way a genetic search does, but by
asking a surrogate where the front is most likely to still be missing
something.

This is the strategy for a campaign where a genetic search's batches are the
problem rather than the answer. Two designs a parameter apart can close timing
five times slower than each other, which is ordinary in EDA synthesis and
nothing a search is meant to fix -- but a genetic search proposes a whole
batch at once and waits for all of it, so one slow design in an otherwise fast
batch leaves every other slot idle until it returns. Paired with a campaign's
``async`` mode (see :mod:`odatix.dse.campaign`), a Bayesian search asks one
question at a time instead: a design finishing anywhere frees a slot that is
filled immediately, by a proposal informed by everything measured so far and
by what is still in flight, so a straggler ties up one slot and not the whole
search.

What is modeled is one Gaussian process per objective (see :mod:`odatix.dse.gp`),
each predicting a mean and an uncertainty at any point of the space. What is
proposed is, out of a large pool of candidates drawn at random and around what
is already known to be good, the one whose predicted improvement to the
front's hypervolume is largest in expectation -- estimated the way a hand
would: draw a few cost vectors from what the model believes about a candidate,
add each to the current front, and see how much further out the front reaches
on average. This is the Bayesian-optimization idea generally known as expected
hypervolume improvement, computed here by sampling rather than by the closed
form, since a front of a handful of objectives is cheap to recompute a few
thousand times and expensive to derive a formula for.

A design still in flight is not ignored while its outcome is unknown -- it is
fed back into the model at its own predicted mean (the "Kriging believer"
heuristic), which is enough to keep two proposals made moments apart from
landing on top of each other without pretending to know how the pending one
will actually turn out.

Cold and blind at the start -- there is nothing yet to fit a surface to -- so
the first handful of designs are drawn at random, exactly the way a genetic
search opens.
"""

import numpy as np

from odatix.dse.gp import GaussianProcess
from odatix.dse.objectives import hypervolume, pareto_front
from odatix.dse.strategy import Strategy

__all__ = ["BayesianSearch"]


class BayesianSearch(Strategy):
    """
    Options:
        candidates (int): how many candidates the acquisition compares before
            proposing one. Half drawn uniformly over the space, half around
            the best designs found so far -- a surface fit on a handful of
            expensive evaluations is not one to trust to point a gradient at
            directly, so what it is asked instead is to rank a pool.
        samples (int): how many Monte Carlo draws a candidate's expected
            hypervolume improvement is averaged over.

    How many designs are proposed at random before a model is fit at all is
    not a setting: it is twice the number of axes plus one, which is what a
    GP needs to have anything to say about a space of that many dimensions,
    floored at a batch's worth so a first round run in ``async`` mode is not
    left half-random and half-modeled.
    """

    name = "bayesian"

    def __init__(self, space, rng, **options):
        super(BayesianSearch, self).__init__(space, rng, **options)
        self.dims = len(space.lengths)
        self.warmup = max(2 * self.dims + 1, int(options.get("batch") or 0) or 4)
        self.candidates = max(16, int(options.get("candidates") or 0) or 300)
        self.samples = max(4, int(options.get("samples") or 0) or 12)
        #: What has actually been measured, in observation order -- kept as
        #: the campaign's own :class:`~odatix.dse.objectives.Costs`, not a
        #: plain tuple, so a constrained search still ranks by how close a
        #: design got before it ranks by the objectives (see
        #: :func:`~odatix.dse.objectives.dominates`).
        self.genomes = []
        self.costs = []
        #: Designs proposed and not yet observed, each carrying its own
        #: predicted cost -- the liar that keeps the next proposal from
        #: landing beside it (see the module's docstring).
        self.pending = {}
        #: One model per objective, refit after every batch observed. Empty
        #: until there is enough to fit at all.
        self.models = []

    ######################################
    # What it knows
    ######################################

    def observe(self, evaluations):
        for evaluation in evaluations:
            genome = tuple(evaluation.genome)
            self.pending.pop(genome, None)
            if evaluation.costs is None:
                # A design that could not be measured tells the search nothing
                # about the shape of the objectives, only that it is not an
                # answer -- there is nothing here for a regression to fit.
                continue
            self.genomes.append(genome)
            self.costs.append(evaluation.costs)
        self._fit()

    def _fit(self):
        if len(self.genomes) < 2:
            self.models = []
            return
        X = np.array([self._normalize(genome) for genome in self.genomes])
        models = []
        for axis in range(len(self.costs[0])):
            y = np.array([cost[axis] for cost in self.costs])
            if np.allclose(y, y[0]):
                # Every design measured the same on this objective so far: a
                # GP fit to a flat surface is a division by zero waiting to
                # happen, and there is nothing yet for it to have learned.
                models.append(None)
                continue
            seed = self.rng.randrange(1 << 30)
            models.append(GaussianProcess(seed=seed).fit(X, y))
        self.models = models

    def _normalize(self, genome):
        """A genome as the model reads it: one axis, scaled to ``[0, 1]``."""
        return [gene / max(1, length - 1) for gene, length in zip(genome, self.space.lengths)]

    @property
    def _ready(self):
        return bool(self.models) and not any(model is None for model in self.models)

    ######################################
    # What it proposes
    ######################################

    def propose(self, count):
        count = max(0, int(count))
        proposed = []
        for _ in range(count):
            in_hand = len(self.genomes) + len(self.pending)
            if in_hand < self.warmup or not self._ready:
                genome = tuple(self.rng.randrange(length) for length in self.space.lengths)
            else:
                genome = self._best_candidate()
            proposed.append(genome)
            self.pending[genome] = self._predict(genome)
        return proposed

    def _best_candidate(self):
        """The candidate of the pool with the largest expected hypervolume gain."""
        front = self._current_front()
        reference = self._reference()
        base_volume = hypervolume(front, reference) if front and reference else 0.0

        pool = self._candidate_pool()
        if not pool:
            # A space too small, or too thoroughly explored, to fill a pool
            # of candidates from: a random genome is what a cold search would
            # have proposed anyway, and the campaign is what decides whether
            # it has already been seen.
            return tuple(self.rng.randrange(length) for length in self.space.lengths)

        best_genome, best_score = pool[0], -1.0
        for genome in pool:
            score = self._expected_gain(genome, front, reference, base_volume)
            if score > best_score:
                best_genome, best_score = genome, score
        return best_genome

    def _candidate_pool(self):
        """
        What the acquisition chooses among: half of the pool spread over the
        whole space, so a region nothing has looked at yet is still in the
        running, half built by mutating the designs on the front measured so
        far, so a promising corner of the space gets looked at closely.

        A genome already measured or still pending is never a candidate: its
        expected gain would be zero or near it either way -- there is nothing
        left to learn from a point already known, and a point already in
        flight is being learned from as soon as it comes back -- and proposing
        it again would only have the campaign discard it as already seen,
        leaving this search no wiser for the attempt.
        """
        pool = []
        seen = set(self.genomes) | set(self.pending)
        attempts = 0
        while len(pool) < self.candidates // 2 and attempts < self.candidates * 4:
            attempts += 1
            genome = tuple(self.rng.randrange(length) for length in self.space.lengths)
            if genome not in seen:
                seen.add(genome)
                pool.append(genome)

        anchors = self._front_genomes() or self.genomes
        attempts = 0
        while anchors and len(pool) < self.candidates and attempts < self.candidates * 4:
            attempts += 1
            genome = self._mutate(anchors[self.rng.randrange(len(anchors))])
            if genome not in seen:
                seen.add(genome)
                pool.append(genome)
        return pool

    def _mutate(self, genome):
        genome = list(genome)
        gene = self.rng.randrange(len(genome))
        length = self.space.lengths[gene]
        if length > 1:
            # Redrawn among the *other* values of the axis: a mutation that
            # changes nothing is a candidate wasted on a genome already in
            # the pool some other way.
            moved = self.rng.randrange(length - 1)
            genome[gene] = moved if moved < genome[gene] else moved + 1
        return tuple(genome)

    def _front_genomes(self):
        if not self.costs:
            return []
        return [self.genomes[index] for index in pareto_front(self.costs)]

    def _current_front(self):
        """The front as it is known now, pending designs' liars included."""
        costs = list(self.costs) + list(self.pending.values())
        if not costs:
            return []
        return [costs[index] for index in pareto_front(costs)]

    def _reference(self):
        """
        The corner the hypervolume is measured against: the worst of every
        objective seen or predicted so far, pushed out a little further so a
        single design still covers something (see
        :class:`~odatix.dse.objectives.Progress`, which does the same for a
        campaign's own reporting).
        """
        costs = list(self.costs) + list(self.pending.values())
        if not costs:
            return None
        axes = len(costs[0])
        worst = [max(cost[axis] for cost in costs) for axis in range(axes)]
        best = [min(cost[axis] for cost in costs) for axis in range(axes)]
        return tuple(w + (0.1 * (w - b) or 0.1 * abs(w) or 1.0) for w, b in zip(worst, best))

    def _predict(self, genome):
        """
        A genome's cost as the models believe it to be right now -- used both
        as the liar a pending design is held at, and as one leg of the
        expected-improvement estimate below.
        """
        point = np.array([self._normalize(genome)])
        return tuple(float(model.predict(point)[0][0]) for model in self.models)

    def _expected_gain(self, genome, front, reference, base_volume):
        """
        How much a candidate is expected to grow the front's hypervolume,
        averaged over samples drawn from what each objective's model believes
        about it -- the Monte Carlo estimate of expected hypervolume
        improvement the module's docstring describes.
        """
        if reference is None:
            return 0.0
        point = np.array([self._normalize(genome)])
        means, deviations = [], []
        for model in self.models:
            mean, variance = model.predict(point)
            means.append(float(mean[0]))
            deviations.append(float(np.sqrt(max(variance[0], 0.0))))

        gains = []
        for _ in range(self.samples):
            sample = tuple(
                self.rng.gauss(mean, deviation) if deviation > 0 else mean
                for mean, deviation in zip(means, deviations)
            )
            gains.append(max(0.0, hypervolume(front + [sample], reference) - base_volume))
        return sum(gains) / len(gains)
