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
Searches that stay correct over a whole campaign: what a strategy is told about
the proposals that are never run, a campaign picked up again, a campaign
cancelled with designs still running, and a design measured by what its own
run produced.
"""

import os
import random
import threading

import numpy as np
import pytest

import odatix.dse.evaluation as evaluation_module
from odatix.dse.archive import Archive
from odatix.dse.bayesian import BayesianSearch, ConstantModel
from odatix.dse.campaign import Campaign
from odatix.dse.evaluation import DAEMON_GRACE, Evaluation, Evaluator, Pending, _finished_jobs
from odatix.dse.objectives import Objectives
from odatix.dse.space import ArchitectureSpace
from odatix.dse.strategies import ExhaustiveSearch
from odatix.dse.strategy import Strategy

from test_dse import (  # noqa: F401 -- architecture is a fixture
    FakeAsyncEvaluator,
    FakeEvaluator,
    FakeSpace,
    architecture,
    campaign_settings,
    evaluation,
)


######################################
# Helpers
######################################

class _Design(object):
    def __init__(self, genome):
        self.genome = tuple(genome)
        self.entry = self.label = str(self.genome)
        self.architecture = "Design"
        self.values = {}
        self.frequency = None
        self.toolchain = None
        self.chose_toolchain = False


class GridSpace(FakeSpace):
    """
    A space of plain numbers that a campaign can ask about: some genomes name
    nothing runnable, and some are moved onto another design by an exclusion.
    """

    def __init__(self, lengths, holes=(), projections=None):
        FakeSpace.__init__(self, lengths)
        self.holes = set(tuple(genome) for genome in holes)
        self.projections = dict(projections or {})

    def clamp(self, genome):
        return tuple(int(gene) % length for gene, length in zip(genome, self.lengths))

    def design(self, genome, project=True):
        genome = self.clamp(genome)
        if genome in self.holes:
            return None
        if project and genome in self.projections:
            return _Design(self.projections[genome])
        return _Design(genome)


class ScriptedStrategy(Strategy):
    """Proposes what it is told to, and remembers what it was told to forget."""

    name = "scripted"

    def __init__(self, space, proposals):
        Strategy.__init__(self, space, random.Random(0))
        self.proposals = [list(batch) for batch in proposals]
        self.discarded = []

    def propose(self, count):
        return self.proposals.pop(0) if self.proposals else []

    def discard(self, genomes):
        self.discarded.extend(tuple(genome) for genome in genomes)


def bare_campaign(space, strategy, seen=(), running=()):
    """A campaign reduced to what :meth:`Campaign.next_batch` reads."""
    campaign = Campaign.__new__(Campaign)
    campaign.space = space
    campaign.strategy = strategy
    campaign.seen = set(tuple(genome) for genome in seen)
    campaign._pending = [Pending(_Design(genome), (), ()) for genome in running]
    return campaign


def cost(design):
    width = design.values["width"]
    depth = design.values["depth"]
    return {"speed": width * 10, "area": width * depth}


######################################
# Exhaustive
######################################

class TestExhaustive:
    def test_a_sweep_skips_what_it_was_told_is_evaluated(self):
        strategy = ExhaustiveSearch(FakeSpace([2, 3]), random.Random(1))
        strategy.observe([evaluation(genome, (1.0,)) for genome in ((0, 0), (0, 1), (0, 2), (1, 0))])
        assert strategy.propose(2) == [(1, 1), (1, 2)]
        assert strategy.propose(1) == []
        assert strategy.exhausted

    def test_a_sweep_gets_past_a_long_prefix_already_seen(self):
        # Two hundred designs, the first hundred already run: twenty proposals
        # of two would never reach the rest, and the campaign would conclude
        # that the space is spent.
        space = GridSpace([200])
        seen = [(index,) for index in range(100)]
        campaign = bare_campaign(space, ExhaustiveSearch(space, random.Random(1)), seen=seen)
        designs = campaign.next_batch(2)
        assert [design.genome for design in designs] == [(100,), (101,)]

    def test_a_resumed_sweep_numbers_its_batches_on(self, architecture, tmp_path):
        from odatix.workspace import Workspace

        search = {"strategy": "exhaustive", "budget": 3, "batch": 1, "seed": 1}
        settings = campaign_settings(search=search)
        Campaign(
            Workspace(str(tmp_path)), architecture, settings,
            evaluator=FakeEvaluator(settings.objective_list(), cost),
        ).run()

        settings = campaign_settings(search=dict(search, budget=6))
        evaluator = FakeEvaluator(settings.objective_list(), cost)
        second = Campaign(Workspace(str(tmp_path)), architecture, settings, evaluator=evaluator)
        archive = second.run()
        assert len(evaluator.evaluated) == 3
        assert sorted(evaluation.batch for evaluation in archive.evaluations) == [1, 2, 3, 4, 5, 6]


######################################
# What the campaign hands back
######################################

class TestDiscard:
    def test_every_proposal_that_is_not_run_is_handed_back(self):
        space = GridSpace([10], holes=[(3,)], projections={(5,): (6,)})
        strategy = ScriptedStrategy(space, [[(3,), (4,), (5,), (1,)]])
        campaign = bare_campaign(space, strategy, seen=[(1,)])
        designs = campaign.next_batch(4)
        assert [design.genome for design in designs] == [(4,), (6,)]
        # The hole, the projected proposal, the design already run.
        assert sorted(strategy.discarded) == [(1,), (3,), (5,)]

    def test_the_origin_of_a_projection_is_marked_as_seen(self):
        # Or a strategy drawing at random keeps proposing it, and each time the
        # campaign finds the projected design already run.
        space = GridSpace([10], projections={(5,): (6,)})
        campaign = bare_campaign(space, ScriptedStrategy(space, [[(5,)]]))
        campaign.next_batch(1)
        assert (5,) in campaign.seen and (6,) in campaign.seen

    def test_a_repeat_of_a_design_still_running_is_not_handed_back(self):
        # Its liar belongs to the run in flight, which reports on it.
        space = GridSpace([10])
        strategy = ScriptedStrategy(space, [[(2,), (7,)]])
        campaign = bare_campaign(space, strategy, seen=[(2,)], running=[(2,)])
        campaign.next_batch(2)
        assert strategy.discarded == []

    def test_a_bayesian_search_forgets_a_proposal_that_is_not_run(self):
        strategy = BayesianSearch(FakeSpace([6, 6]), random.Random(1))
        proposed = strategy.propose(2)
        assert set(proposed) <= set(strategy.pending)
        strategy.discard([proposed[0]])
        assert proposed[0] not in strategy.pending

    def test_a_bayesian_search_through_a_campaign_keeps_no_ghost(self):
        # Half the space is a hole: every proposal landing there would have
        # stayed pending forever, in the front and in the reference.
        space = GridSpace([4, 4], holes=[(row, column) for row in range(2) for column in range(4)])
        strategy = BayesianSearch(space, random.Random(3))
        campaign = bare_campaign(space, strategy)
        designs = campaign.next_batch(4)
        running = set(design.genome for design in designs)
        assert set(strategy.pending) <= running


######################################
# Bayesian models
######################################

class TestBayesianModels:
    def test_an_objective_nothing_moves_is_still_modeled(self):
        # A flat objective used to leave the search proposing at random for
        # as long as it stayed flat.
        space = FakeSpace([8, 8])
        strategy = BayesianSearch(space, random.Random(2), batch=2)
        rng = random.Random(5)
        genomes = set()
        while len(genomes) < 12:
            genomes.add((rng.randrange(8), rng.randrange(8)))
        strategy.observe([evaluation(genome, (float(sum(genome)), 5.0)) for genome in genomes])

        assert isinstance(strategy.models[1], ConstantModel)
        assert strategy._ready
        means, deviations = strategy._predict_many([(0, 0), (7, 7)])
        assert [mean[1] for mean in means] == [5.0, 5.0]
        assert [deviation[1] for deviation in deviations] == [0.0, 0.0]
        assert len(strategy.propose(1)) == 1

    def test_meeting_one_constraint_by_far_does_not_make_up_for_missing_another(self):
        class _Model(object):
            def __init__(self, means):
                self.means = np.array(means, dtype=float)

            def predict(self, points):
                return self.means, np.zeros(len(self.means))

        strategy = BayesianSearch(FakeSpace([4]), random.Random(1))
        # Candidate 0 meets the first constraint by a mile and misses the
        # second; candidate 1 misses both, by a little.
        strategy.feasibility = [_Model([-5.0, 0.4]), _Model([1.0, 0.4])]
        assert strategy._closest_to_feasible([(0,), (1,)]) == (1,)

    def test_the_shortlist_and_the_front_cap_are_settings(self, architecture, tmp_path):
        from odatix.workspace import Workspace

        settings = campaign_settings(
            search={"strategy": "bayesian", "budget": 4, "batch": 2, "seed": 1,
                    "shortlist": 7, "front_cap": 9},
        )
        campaign = Campaign(
            Workspace(str(tmp_path)), architecture, settings,
            evaluator=FakeEvaluator(settings.objective_list(), cost),
        )
        assert campaign.strategy.shortlist == 7
        assert campaign.strategy.front_cap == 9


######################################
# Async mode
######################################

class _OneAtATimeEvaluator(FakeAsyncEvaluator):
    """Every poll finishes exactly one design: a round is a single design."""

    def poll(self, pending, cancel_event=None):
        item = pending.pop(0)
        self.events.append(("finish", item.design.entry))
        return [item]


class _CancellingEvaluator(FakeAsyncEvaluator):
    """The campaign is cancelled while the second design is running."""

    def __init__(self, objectives, cost, cancel_event):
        FakeAsyncEvaluator.__init__(self, objectives, cost)
        self.cancel_event = cancel_event
        self.polls = 0

    def poll(self, pending, cancel_event=None):
        self.polls += 1
        if self.polls == 1:
            return [pending.pop(0)]
        self.cancel_event.set()
        return []


class TestAsync:
    def test_patience_is_counted_in_designs(self, architecture, tmp_path):
        # A round of an async campaign can be a single design: counted in
        # rounds, a patience of one batch stopped a search after one design.
        from odatix.workspace import Workspace

        settings = campaign_settings(
            search={"strategy": "exhaustive", "budget": 50, "batch": 2, "seed": 1,
                    "mode": "async", "patience": 2},
        )
        evaluator = _OneAtATimeEvaluator(settings.objective_list(), lambda design: {"speed": 1, "area": 1})
        archive = Campaign(Workspace(str(tmp_path)), architecture, settings, evaluator=evaluator).run()
        # One design that makes the front, then patience x batch that do not.
        assert len(archive) == 5

    def test_a_cancelled_async_campaign_keeps_what_finished(self, architecture, tmp_path):
        from odatix.workspace import Workspace

        cancel = threading.Event()
        settings = campaign_settings(
            search={"strategy": "exhaustive", "budget": 50, "batch": 2, "seed": 1, "mode": "async"},
        )
        evaluator = _CancellingEvaluator(settings.objective_list(), cost, cancel)
        campaign = Campaign(
            Workspace(str(tmp_path)), architecture, settings, evaluator=evaluator, cancel_event=cancel,
        )
        archive = campaign.run()
        assert len(archive) == 1
        assert os.path.isfile(archive.path)
        # Left running, for the next run of the campaign to pick up.
        assert len(campaign._pending) == 2
        submits = [entry for kind, entry in evaluator.events if kind == "submit"]
        assert len(submits) == 3


######################################
# Picking a campaign up
######################################

class TestRestore:
    def test_designs_folded_into_one_are_restored_once(self, tmp_path):
        # An exclusion added since the archive was written projects two of its
        # designs onto the same one.
        objectives = Objectives.from_list(["area"])
        path = str(tmp_path / "dse" / "Design.yml")
        archive = Archive(path, "Design", objectives)
        archive.improved_by([
            Evaluation(_Design(genome), metrics={"area": area}, costs=objectives.costs({"area": area}), batch=1)
            for genome, area in (((1,), 10), ((2,), 20))
        ])
        archive.save()

        space = GridSpace([4], projections={(1,): (2,)})
        again = Archive(path, "Design", objectives)
        assert again.restore(space) == [(2,)]
        assert len(again.evaluations) == 1

    def test_designs_measured_before_the_campaign_belong_to_batch_zero(self, architecture, tmp_path):
        from odatix.workspace import Workspace

        from test_dse import _KnowingEvaluator

        settings = campaign_settings(search={"strategy": "exhaustive", "budget": 2, "batch": 2, "seed": 1})
        evaluator = _KnowingEvaluator(settings.objective_list(), cost, [(0, 0)])
        archive = Campaign(Workspace(str(tmp_path)), architecture, settings, evaluator=evaluator).run()
        batches = dict((evaluation.genome, evaluation.batch) for evaluation in archive.evaluations)
        assert batches.pop((0, 0)) == 0
        assert set(batches.values()) == {1}


######################################
# Measuring what a run produced
######################################

class TestMeasure:
    def evaluator(self, tmp_path, **overrides):
        from odatix.workspace import Workspace

        settings = campaign_settings(**overrides)
        objectives = Objectives.from_list([{"metric": "frequency", "goal": "max"}, "LUT_count"])
        return Evaluator(Workspace(str(tmp_path)), settings, objectives)

    def measured(self, tmp_path, architecture, before, after, **overrides):
        evaluator = self.evaluator(tmp_path, **overrides)
        design = ArchitectureSpace(architecture).design((0, 0))
        identity = evaluator.design_identity(design)
        return evaluator.measure(design, {identity: after}, {identity: before})

    OLD = {"meta": {"frequency": 100, "timestamp": "2026-10-01"}, "metrics": {"LUT_count": 40}}
    RERUN = {"meta": {"frequency": 300, "timestamp": "2026-10-17"}, "metrics": {"LUT_count": 44}}

    def test_a_rerun_that_produced_nothing_is_not_measured_by_an_old_record(
        self, tmp_path, architecture
    ):
        result = self.measured(tmp_path, architecture, [self.OLD], [self.OLD], overwrite=True)
        assert not result.measured
        assert "no result" in result.note

    def test_a_design_the_run_skipped_as_done_is_measured_by_what_is_there(
        self, tmp_path, architecture
    ):
        result = self.measured(tmp_path, architecture, [self.OLD], [self.OLD])
        assert result.metrics["frequency"] == 100

    def test_a_record_replaced_in_place_is_what_is_read(self, tmp_path, architecture):
        # A re-run replaces its job's records rather than adding to them: the
        # count does not change, the meta does.
        result = self.measured(tmp_path, architecture, [self.OLD], [self.RERUN], overwrite=True)
        assert result.metrics["frequency"] == 300


######################################
# Waiting on the daemon
######################################

class TestDaemonStatus:
    def test_a_job_never_listed_is_not_finished(self):
        listed = set()
        assert _finished_jobs({"/w/a"}, {}, listed, since=1e12) == set()

    def test_a_job_that_was_listed_and_is_gone_is_finished(self):
        listed = set()
        assert _finished_jobs({"/w/a"}, {"/w/a": "running"}, listed, since=1e12) == set()
        assert _finished_jobs({"/w/a"}, {}, listed, since=1e12) == {"/w/a"}

    def test_a_job_never_listed_is_given_up_on_after_the_grace(self):
        import time

        since = time.time() - DAEMON_GRACE - 1
        assert _finished_jobs({"/w/a"}, {}, set(), since=since) == {"/w/a"}

    def test_a_batch_is_not_done_before_its_jobs_appear(self, tmp_path, monkeypatch):
        evaluator = TestMeasure().evaluator(tmp_path)
        directory = os.path.realpath(str(tmp_path / "job"))
        answers = [{}, {directory: "running"}, {directory: "success"}]
        calls = []

        def statuses(waited_since, what):
            calls.append(what)
            return answers[min(len(calls), len(answers)) - 1]

        class _Job(object):
            tmp_dir = directory

        class _Jobs(object):
            job_list = [_Job()]

        monkeypatch.setattr(evaluator, "_daemon_statuses", statuses)
        monkeypatch.setattr(evaluation_module, "POLL_INTERVAL", 0)
        evaluator.wait_for(_Jobs())
        assert len(calls) == 3

    def test_a_cancelled_poll_returns_what_is_done_without_raising(self, tmp_path, monkeypatch):
        evaluator = TestMeasure().evaluator(tmp_path)
        done = Pending(_Design((0,)), {"/w/done"}, ())
        running = Pending(_Design((1,)), {"/w/running"}, ())
        monkeypatch.setattr(
            evaluator, "_daemon_statuses",
            lambda waited_since, what: {"/w/done": "success", "/w/running": "running"},
        )
        cancel = threading.Event()
        cancel.set()
        pending = [done, running]
        assert evaluator.poll(pending, cancel_event=cancel) == [done]
        assert pending == [running]

        monkeypatch.setattr(evaluator, "_daemon_statuses", lambda waited_since, what: None)
        assert evaluator.poll(pending, cancel_event=cancel) == []
