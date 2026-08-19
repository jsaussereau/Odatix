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
form, which is expensive to derive and no more exact than a few draws of the
thing itself. What is drawn is scored by how much it would add to the front
rather than by measuring the front again with it in (see
:func:`~odatix.dse.objectives.hypervolume_improvement`), and only a shortlist
of the pool is scored that way at all -- the arithmetic of choosing a design
has to stay well under the synthesis of one, and over four or five objectives
it does not do that on its own.

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
from odatix.dse.objectives import hypervolume_improvement, pareto_front
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
        shortlist (int): how many of the candidates the full expected
            hypervolume improvement is spent on. The rest are ranked by a
            cheap screening score first (see :meth:`_best_candidate`), so a
            large pool costs a large *search*, not a large amount of
            arithmetic.

    How many designs are proposed at random before a model is fit at all is
    not a setting: it is twice the number of axes plus one, which is what a
    GP needs to have anything to say about a space of that many dimensions,
    floored at a batch's worth -- how many designs a campaign runs at once,
    whether that is a batch's size in ``batch`` mode or the queue depth in
    ``async`` mode, both of which reach this strategy the same way, as
    ``batch`` -- so a first round run in ``async`` mode is not left
    half-random and half-modeled.
    """

    name = "bayesian"

    def __init__(self, space, rng, **options):
        super(BayesianSearch, self).__init__(space, rng, **options)
        self.dims = len(space.lengths)
        self.warmup = max(2 * self.dims + 1, int(options.get("batch") or 0) or 4)
        self.candidates = max(16, int(options.get("candidates") or 0) or 300)
        self.samples = max(4, int(options.get("samples") or 0) or 12)
        #: How many candidates of the pool are scored by the real acquisition
        #: rather than only screened (see :meth:`_best_candidate`).
        self.shortlist = max(4, int(options.get("shortlist") or 0) or 24)
        #: How many front points the expected-gain estimate is computed
        #: against at most. The volume it scores each candidate with is
        #: recomputed ``shortlist * samples`` times per proposal, so a front
        #: left to grow with the whole archive turns every single design a
        #: campaign submits into a slower and slower one to propose -- a
        #: search that widens its lead over time paying for that lead in
        #: exactly the throughput it bought the lead to spend (see the
        #: module's docstring on why ``async`` mode is proposed one design at
        #: a time). Thinned rather than truncated, so what is kept still
        #: spans the front instead of collapsing to one corner of it.
        #:
        #: What a front costs is about ``points ** objectives``, so the cap
        #: cannot be one number: forty points is nothing over two objectives
        #: and minutes per proposal over four. It is set from how many
        #: objectives there are unless the settings name one outright.
        #: Zero means "decide it" (see :meth:`_front_cap`).
        self.front_cap = max(0, int(options.get("front_cap") or 0))
        #: What has actually been measured, in observation order -- kept as
        #: the campaign's own :class:`~odatix.dse.objectives.Costs`, not a
        #: plain tuple, so a constrained search still ranks by how close a
        #: design got before it ranks by the objectives (see
        #: :func:`~odatix.dse.objectives.dominates`).
        self.genomes = []
        self.costs = []
        #: Designs that could not be measured at all -- nothing for a
        #: regression to fit, but still a place the search has already
        #: looked, so it is not proposed again and again until a campaign's
        #: attempt budget for a single slot runs out on repeats of it (see
        #: :meth:`~odatix.dse.campaign.Campaign.next_batch`).
        self.failed = set()
        #: Designs proposed and not yet observed, each carrying its own
        #: predicted cost -- the liar that keeps the next proposal from
        #: landing beside it (see the module's docstring).
        self.pending = {}
        #: One model per objective. Empty until there is enough to fit at all.
        self.models = []
        #: How many designs the models were last fit on -- what tells
        #: :meth:`_maybe_fit` how much has changed since, and what a refit
        #: would cost: a Gaussian process is refit in time cubic in how many
        #: points it holds, so in ``async`` mode, where a wave is one design
        #: at a time, refitting after every single one of them would make the
        #: model the slower half of the search well before a campaign is
        #: done -- doubly so with one model per objective. See
        #: :meth:`_maybe_fit`.
        self._fitted_at = 0

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
                # answer -- there is nothing here for a regression to fit, but
                # it is still a place already looked at (see ``self.failed``).
                self.failed.add(genome)
                continue
            self.genomes.append(genome)
            self.costs.append(evaluation.costs)
        self._maybe_fit()

    def _maybe_fit(self):
        """
        Refit the models, but only once refitting has become worth its cost.

        A Gaussian process is refit in time cubic in how many points it
        holds, and there is one per objective -- fine once a batch, but in
        ``async`` mode a wave is one design at a time, and refitting after
        every single one would turn the model into the slow half of the
        search well before a campaign is done, paying for a proposal with
        more thinking than the synthesis it is meant to keep ahead of costs.

        So a refit is skipped until enough has changed since the last one to
        be worth paying for again -- a tenth more points than were last fit
        on, which keeps the total time spent refitting across a whole
        campaign close to what one last, full-size refit alone would cost,
        rather than growing with how many refits were done along the way.
        The first fit is never skipped: nothing is modeled at all until then,
        and :meth:`propose` reads that absence to decide whether to still
        propose at random.
        """
        n = len(self.genomes)
        if n < 2:
            self.models = []
            self._fitted_at = 0
            return
        if self.models and n - self._fitted_at < max(1, self._fitted_at // 10):
            return
        self._fit()
        self._fitted_at = n

    def _fit(self):
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
            in_hand = len(self.genomes) + len(self.pending) + len(self.failed)
            if in_hand < self.warmup or not self._ready:
                genome = tuple(self.rng.randrange(length) for length in self.space.lengths)
            else:
                genome = self._best_candidate()
            proposed.append(genome)
            self.pending[genome] = self._predict(genome)
        return proposed

    def _best_candidate(self):
        """
        The candidate of the pool with the largest expected hypervolume gain.

        Scored in two passes rather than one. A pool wide enough to be worth
        drawing -- hundreds of candidates, most of them nowhere near the front
        -- cannot have the sampled estimate spent on all of it: that estimate
        costs a volume per draw per candidate, and it is the reason a
        proposal can take longer than the synthesis it is choosing. So every
        candidate is first screened by a single volume, computed at what the
        models optimistically believe of it, which ranks the pool for a
        fraction of the cost of ranking it properly; only the best few of
        that ranking are then scored by the full estimate. What this can miss
        is a candidate whose mean is unremarkable and whose spread is what
        makes it worth trying -- which the screen already leans towards by
        being optimistic rather than average.
        """
        front = self._current_front()
        reference = self._reference()

        pool = self._candidate_pool()
        if not pool:
            # A space too small, or too thoroughly explored, to fill a pool
            # of candidates from: a random genome is what a cold search would
            # have proposed anyway, and the campaign is what decides whether
            # it has already been seen.
            return tuple(self.rng.randrange(length) for length in self.space.lengths)
        if reference is None or not front:
            return pool[0]

        means, deviations = self._predict_many(pool)
        screened = sorted(
            range(len(pool)),
            key=lambda index: -hypervolume_improvement(
                [mean - deviation for mean, deviation in zip(means[index], deviations[index])],
                front, reference,
            ),
        )

        best_index, best_score = screened[0], -1.0
        for index in screened[:self.shortlist]:
            score = self._expected_gain(means[index], deviations[index], front, reference)
            if score > best_score:
                best_index, best_score = index, score
        return pool[best_index]

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
        seen = set(self.genomes) | set(self.pending) | self.failed
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
        costs = list(self.costs) + [cost for cost in self.pending.values() if cost is not None]
        if not costs:
            return []
        front = [costs[index] for index in pareto_front(costs)]
        return self._thin(front)

    def _thin(self, front):
        """
        A front kept to :attr:`front_cap` points at most, spread evenly along
        it rather than cut off at one end -- what the expected-gain estimate
        below is scored against, and the reason a design that would have kept
        the front's shape stays represented even once the front outgrows what
        is cheap to run a few thousand hypervolume computations against.
        """
        cap = self._front_cap(len(front[0]) if front else 0)
        if len(front) <= cap:
            return front
        order = sorted(range(len(front)), key=lambda index: front[index][-1])
        step = len(order) / float(cap)
        picked = sorted({order[int(position * step)] for position in range(cap)})
        return [front[index] for index in picked]

    def _front_cap(self, axes):
        """
        How many front points are worth scoring against, over that many
        objectives.

        A front of ``n`` points over ``d`` objectives costs on the order of
        ``n ** d`` to measure a volume against, so the same cap is generous
        over two objectives and unaffordable over five. What is picked here
        keeps that product roughly level instead: wide when the objectives
        are few, tight when they are many, and never below what it takes for
        a front to still have a shape.
        """
        if self.front_cap:
            return self.front_cap
        return {0: 40, 1: 40, 2: 40, 3: 24}.get(axes, 12)

    def _reference(self):
        """
        The corner the hypervolume is measured against: the worst of every
        objective seen or predicted so far, pushed out a little further so a
        single design still covers something (see
        :class:`~odatix.dse.objectives.Progress`, which does the same for a
        campaign's own reporting).
        """
        costs = list(self.costs) + [cost for cost in self.pending.values() if cost is not None]
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

        Nothing to predict from before the first design is even observed --
        there is not yet an axis count to hold a liar's place with, let alone
        a model to ask -- so a genome proposed that early carries no liar at
        all (see the ``None`` filtering everywhere ``self.pending`` is read).
        Once there is at least one measured design but the models are not
        fit or not all ready, the liar falls back to what has been observed
        on average per axis, which is enough to keep two proposals made
        moments apart from landing on top of each other without pretending
        to know more than that.
        """
        if not self.costs:
            return None
        if self._ready:
            means, _ = self._predict_many([genome])
            return tuple(means[0])
        axes = len(self.costs[0])
        return tuple(
            sum(cost[axis] for cost in self.costs) / len(self.costs) for axis in range(axes)
        )

    def _predict_many(self, genomes):
        """
        What every model believes about a whole pool at once.

        One call per model rather than one per model per genome: a pool is
        hundreds of candidates, a Gaussian process predicts a matrix as
        readily as a row, and the difference is entirely in how many times
        Python is asked rather than in how much arithmetic is done.

        Returns:
            tuple: ``(means, deviations)``, each a list of one cost vector per
            genome, in the order they came in.
        """
        points = np.array([self._normalize(genome) for genome in genomes])
        means, deviations = [], []
        for model in self.models:
            mean, variance = model.predict(points)
            means.append(np.asarray(mean, dtype=float).reshape(-1))
            deviations.append(np.sqrt(np.maximum(np.asarray(variance, dtype=float).reshape(-1), 0.0)))
        return (
            [[float(axis[index]) for axis in means] for index in range(len(genomes))],
            [[float(axis[index]) for axis in deviations] for index in range(len(genomes))],
        )

    def _expected_gain(self, means, deviations, front, reference):
        """
        How much a candidate is expected to grow the front's hypervolume,
        averaged over samples drawn from what each objective's model believes
        about it -- the Monte Carlo estimate of expected hypervolume
        improvement the module's docstring describes.

        What each draw is worth is asked of
        :func:`~odatix.dse.objectives.hypervolume_improvement` rather than by
        measuring the front twice: the difference between two volumes is the
        whole of what is wanted here, and it is far cheaper to compute than
        either of the volumes it is the difference of.
        """
        if reference is None:
            return 0.0
        gains = 0.0
        for _ in range(self.samples):
            sample = [
                self.rng.gauss(mean, deviation) if deviation > 0 else mean
                for mean, deviation in zip(means, deviations)
            ]
            gains += hypervolume_improvement(sample, front, reference)
        return gains / self.samples
