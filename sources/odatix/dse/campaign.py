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
One exploration, from what it would do to what it found.

The loop is the whole of it, and it is three lines long: ask the strategy where
to look, run what it said, tell it how that turned out. Everything else here is
about stopping -- a budget, a space that runs out, a front that stops moving, a
user who interrupts -- because an exploration is defined by when it stops, not
by when it is done.

A campaign searches one architecture at a time (see
:class:`~odatix.dse.space.ArchitectureSpace`), and reports what it found the
same way a run reports what it ran.
"""

import os
import random
import time

import odatix.lib.printc as printc
from odatix.dse.archive import Archive
from odatix.dse.evaluation import EvaluationError, Evaluator
from odatix.dse.space import (
    ArchitectureSpace,
    DomainSelection,
    EmptySpaceError,
    UnknownConfigurationError,
    UnknownToolchainError,
)
from odatix.dse.strategies import strategy_for

__all__ = ["Campaign", "Exploration", "CampaignError"]

script_name = os.path.basename(__file__)

#: Past this many combinations, the designs an exclusion leaves out are not
#: counted: walking the space to say how big it is costs more than the answer is
#: worth, and a search that large never enumerates it anyway.
EXCLUSION_COUNT_LIMIT = 5000


def _number(value):
    """A metric as a log shows it: readable, and not fifteen decimals long."""
    if value is None:
        return "-"
    if isinstance(value, bool) or not isinstance(value, float):
        return str(value)
    if value == int(value) and abs(value) < 1e15:
        return str(int(value))
    return "{0:.4g}".format(value)


def _duration(seconds):
    """How long something took, as something to read rather than to compute with."""
    seconds = int(max(0, seconds))
    if seconds < 60:
        return "{0}s".format(seconds)
    if seconds < 3600:
        return "{0}m{1:02d}s".format(seconds // 60, seconds % 60)
    return "{0}h{1:02d}m".format(seconds // 3600, (seconds % 3600) // 60)


class CampaignError(RuntimeError):
    """An exploration cannot be run at all."""


class Campaign(object):
    """
    The search of one architecture.

    Args:
        workspace (Workspace): the workspace being explored.
        architecture (Architecture): what is searched.
        settings (RunSettings): the campaign being run, and the run it is part
            of (see :class:`~odatix.dse.campaigns.RunSettings`).
        evaluator (Evaluator): what runs a design and measures it. One is built
            from the settings when none is given; handing one over is what lets
            an exploration be tested without synthesizing anything.
        cancel_event (threading.Event): asking the campaign to stop.
        session (str): the daemon session the batches are enqueued into.
        on_progress (callable): called with (campaign, evaluated) whenever the
            campaign has evaluated more designs, which is how an exploration
            running as a job of the daemon shows how far along it is.
    """

    def __init__(self, workspace, architecture, settings, evaluator=None, cancel_event=None,
                 session=None, on_progress=None, selection=None):
        self.workspace = workspace
        self.architecture = architecture
        self.settings = settings
        # The campaign this comes from, which is what it is named after (see
        # :attr:`name`). Empty when a campaign is built by hand, from settings
        # rather than from a file of the campaign directory.
        self.campaign_name = str(getattr(settings, "name", "") or "")
        # What the entry that asked for this campaign says about the parameter
        # domains of the architecture: which of them are searched, and what the
        # others are fixed to (see :class:`~odatix.dse.space.DomainSelection`).
        self.selection = selection if selection is not None else DomainSelection(entry=architecture.name)
        try:
            self.objectives = settings.objective_list()
        except ValueError as error:
            # A malformed objective or constraint is a settings file to fix, not
            # a traceback: it is caught here so that every entry point into an
            # exploration reports it the same way.
            raise CampaignError(str(error))
        self.cancel_event = cancel_event
        self.on_progress = on_progress

        # The frequency and the toolchain are axes only when the exploration
        # says they are: a custom frequency synthesis whose frequencies are
        # fixed, run by one tool on one target, searches the parameters of the
        # architecture and nothing else.
        try:
            self.toolchains = settings.toolchains(workspace)
        except UnknownToolchainError as error:
            raise CampaignError(str(error))
        try:
            self.space = ArchitectureSpace(
                architecture,
                frequencies=settings.frequency_values() if settings.explores_frequency() else None,
                toolchains=self.toolchains,
                selection=self.selection,
                exclusions=settings.exclusion_set(),
            )
        except UnknownConfigurationError as error:
            raise CampaignError(str(error))
        self.search = settings.search
        self.rng = random.Random(self.search.seed)
        self.evaluator = evaluator if evaluator is not None else Evaluator(
            workspace, settings, self.objectives, cancel_event=cancel_event,
            session=session, toolchains=self.toolchains,
        )
        self.strategy = strategy_for(self.search.strategy)(
            self.space, self.rng,
            mutation=self.search.mutation,
            tournament=self.search.tournament,
            population=self.search.population,
            batch=self.search.batch,
            candidates=self.search.candidates,
            samples=self.search.samples,
            constraints=self.objectives.constraints,
            constraint_models=self.search.constraint_models,
        )
        self.archive = Archive(
            self.archive_path, self.name, self.objectives,
            strategy=self.strategy.name, space_size=self.space.size(),
            tolerance=self.search.improvement,
            results_path=self.results_path,
        )
        #: The genomes already proposed, so that no design is ever run twice --
        #: which is what makes a budget mean "this many designs", not "this many
        #: jobs, some of them the same".
        self.seen = set()
        #: How many designs the space holds once its exclusions are applied,
        #: counted on first use (see :attr:`space_size`).
        self._space_size = None
        #: Which batch is running, and when the campaign started: an exploration
        #: is read while it runs, and "how long has this been going" is the
        #: question its log is opened for.
        self.batch_index = 0
        self.started_at = None
        #: Designs submitted and not yet finished, in ``async`` mode -- empty
        #: whenever the campaign runs in ``batch`` mode instead (see
        #: :meth:`next_wave`).
        self._pending = []

    @property
    def name(self):
        """
        What this campaign is called, which is what its archive is called.

        It is the name of the campaign file: what makes two searches two
        campaigns is what they are looking for, not only the space they look
        in, and only the file says that. A campaign file naming several
        architectures searches each of them separately, and the name then says
        which one -- the architecture, and what the entry fixed when it fixed
        anything.
        """
        selection = self.selection.slug or self.architecture.name
        if not self.campaign_name:
            return selection
        if len(self.settings.architecture_entries()) <= 1:
            return self.campaign_name
        return "{0}_{1}".format(self.campaign_name, selection)

    @property
    def source(self):
        """The file this campaign is written in, which is where it is fixed."""
        from odatix.dse.campaigns import campaign_path

        if not self.campaign_name:
            return self.workspace.paths.dse_settings_file
        return campaign_path(self.workspace, self.campaign_name)

    @property
    def archive_path(self):
        return os.path.join(
            self.workspace.paths.result_path, "dse", "{0}.yml".format(self.name)
        )

    @property
    def results_path(self):
        """
        Where the designs the campaign evaluated are exported as a results
        source of their own, next to the results of the tools -- which is what
        makes them show up in the explorer as something to chart.
        """
        from odatix.dse.export import results_path_for

        return results_path_for(self.workspace.paths.result_path, self.name)

    ######################################
    # What it would do
    ######################################

    def check(self):
        """
        Make sure the exploration can run, and say what it amounts to.

        Raises:
            CampaignError: there is nothing to search, or nothing to search for.
        """
        if not len(self.objectives):
            raise CampaignError(
                "The exploration has no objective: it cannot tell one design from another. "
                "Name at least one metric to minimize or to maximize."
            )
        if self.search.mode not in ("batch", "async"):
            raise CampaignError(
                "Unknown search mode \"{0}\": it is either \"batch\" or \"async\".".format(self.search.mode)
            )
        try:
            self.space.require_choice()
        except EmptySpaceError as error:
            raise CampaignError(str(error))
        self.check_simulations()
        return self

    def check_simulations(self):
        """
        Make sure the simulations an evaluation runs exist.

        A simulation that is not there would fail every batch in the same way,
        hours in, with the designs coming back unmeasured for want of a metric
        nothing produced: it is worth saying before anything is synthesized.
        """
        missing = [
            name for name in self.settings.simulation_names()
            if name not in self.workspace.simulations
        ]
        if missing:
            raise CampaignError(
                "The exploration runs simulation(s) that do not exist: {0}. "
                "Check \"simulations\" in \"{1}\".".format(
                    ", ".join(missing), self.source
                )
            )
        return self

    @property
    def space_size(self):
        """
        How many designs this campaign may evaluate.

        What the space holds once its exclusions are applied, when that can be
        counted without walking a space too large to walk -- the number the
        budget is compared against has to be the number of designs that exist,
        not the number of combinations of the axes.
        """
        if getattr(self, "_space_size", None) is None:
            size, _counted = self.space.feasible_size(limit=EXCLUSION_COUNT_LIMIT)
            object.__setattr__(self, "_space_size", size)
        return self._space_size

    def describe(self):
        """One line saying what this campaign is about to do."""
        return (
            "{9}Exploring \"{0}\": {1} designs, {2} of them evaluated at most, "
            "{3} at a time, by {4} search.{5}{6}{7}{8}".format(
                self.selection.describe(), self.space_size, self.budget,
                self.search.batch, self.strategy.name, self.describe_frequencies(),
                self.describe_toolchains(), self.describe_simulations(), self.describe_mode(),
                "[{0}] ".format(self.campaign_name) if self.campaign_name else "",
            )
            + self.describe_exclusions()
            + self.describe_constraints()
        )

    def describe_exclusions(self):
        """What the campaign leaves out of the space, when it leaves anything out."""
        rules = self.space.exclusions.active()
        if not rules:
            return ""
        left_out = self.space.size() - self.space_size
        kinds = []
        for kind in ("illegal", "duplicate", "dominated"):
            count = len([rule for rule in rules if rule.kind == kind])
            if count:
                kinds.append("{0} {1}".format(count, kind))
        if left_out > 0:
            return " {0} exclusion(s) ({1}) take {2} combination(s) out of the space.".format(
                len(rules), ", ".join(kinds), left_out,
            )
        return " {0} exclusion(s) ({1}) apply.".format(len(rules), ", ".join(kinds))

    def describe_mode(self):
        """Whether the campaign waits for a whole batch, or fills slots as they free up."""
        if self.search.mode != "async":
            return ""
        return (
            " Runs continuously: a new design starts the moment a slot frees, instead of "
            "waiting for the rest of the batch."
        )

    def describe_constraints(self):
        """What a design has to be, when the campaign says anything about it."""
        constraints = self.objectives.constraints
        if not len(constraints):
            return ""
        return " Only designs with {0} count.".format(
            ", ".join(constraint.describe() for constraint in constraints)
        )

    def describe_toolchains(self):
        """What runs the designs, when there is more than one way it could."""
        if len(self.toolchains) <= 1:
            return ""
        return " What runs a design is searched too, out of {0} ({1} combinations).".format(
            ", ".join(chain.label for chain in self.toolchains[:4])
            + (", ..." if len(self.toolchains) > 4 else ""),
            len(self.toolchains),
        )

    def describe_simulations(self):
        """What else an evaluation runs, when it runs anything else."""
        simulations = self.settings.simulation_names()
        if not simulations:
            return ""
        return " Each design is also simulated with {0}.".format(", ".join(simulations))

    def describe_frequencies(self):
        """What the campaign has to say about the frequencies, if anything."""
        frequencies = self.settings.frequency_values()
        if not frequencies:
            return ""
        if self.settings.explores_frequency():
            return " The frequency is searched too, between {0} and {1} MHz ({2} values).".format(
                min(frequencies), max(frequencies), len(frequencies)
            )
        return " Each design is synthesized at {0} MHz.".format(
            ", ".join(str(value) for value in frequencies)
        )

    @property
    def budget(self):
        """
        How many designs this campaign evaluates at most.

        Never more than the space holds: a budget of a hundred on a space of
        twelve is a sweep, and saying so is more useful than pretending to
        search.
        """
        return min(int(self.search.budget), self.space_size)

    ######################################
    # Doing it
    ######################################

    def run(self):
        """
        Search, until the budget is spent or there is nothing left to learn.

        Returns:
            Archive: what was evaluated, and what the answer is.
        """
        self.check()
        printc.bold("\n" + self.describe())
        printc.say("Looking for: {0}.".format(self.describe_objectives()), script_name)

        self.started_at = time.time()
        evaluated = self.resume()
        idle = 0
        self.progress(evaluated)

        asynchronous = self.search.mode == "async"
        if asynchronous:
            self.evaluator.begin_async()

        while evaluated < self.budget:
            if self.cancel_event is not None and self.cancel_event.is_set():
                printc.note("The exploration was cancelled after {0}/{1} design(s).".format(
                    evaluated, self.budget
                ), script_name)
                break

            started = time.time()
            try:
                if asynchronous:
                    designs, evaluations = self.next_wave(self.budget - evaluated)
                else:
                    designs = self.next_batch(min(int(self.search.batch), self.budget - evaluated))
                    evaluations = None
            except EvaluationError as error:
                raise CampaignError(str(error))

            if not designs:
                printc.note(
                    "The search has nothing left to propose after {0} design(s): every design "
                    "it can reach in a space of {1} has been evaluated.".format(
                        evaluated, self.space.size()
                    ),
                    script_name,
                )
                break

            self.batch_index += 1
            if not asynchronous:
                self.announce(designs, evaluated)
                try:
                    evaluations = self.evaluator.evaluate(designs)
                except EvaluationError as error:
                    raise CampaignError(str(error))

            for evaluation in evaluations:
                # Which batch found a design is what makes the search readable
                # afterwards, and it is only known here.
                evaluation.batch = self.batch_index

            self.strategy.observe(evaluations)
            before = self.archive.progress.value
            improved = self.archive.improved_by(evaluations)
            self.save()
            evaluated += len(evaluations)
            self.report(evaluations, evaluated, improved, elapsed=time.time() - started,
                        volume_before=before)
            self.progress(evaluated)

            idle = 0 if improved else idle + 1
            if self.search.patience and idle >= self.search.patience:
                printc.note(
                    "The front has not grown in {0} batches: stopping there, "
                    "{1} design(s) of the budget unspent.".format(
                        idle, max(0, self.budget - evaluated)
                    ),
                    script_name,
                )
                break
            if idle:
                printc.note("The front has not grown in {0} batch(es){1}.".format(
                    idle,
                    " (stopping after {0})".format(self.search.patience)
                    if self.search.patience else "",
                ), script_name)

        if self.started_at is not None:
            printc.say("Campaign \"{0}\" ran for {1} over {2} batch(es).".format(
                self.name, _duration(time.time() - self.started_at), self.batch_index
            ), script_name)
        self.save()
        return self.archive

    def save(self):
        """
        Write the archive, and the results the explorer reads with it.

        The units come from the results files the batch was measured in, so
        that a chart of the exported designs labels its axes exactly like a
        chart of the same designs read from the tool that ran them. An
        evaluator that measures designs some other way than by reading results
        files declares none, and the export goes without.
        """
        units = getattr(self.evaluator, "units", None)
        self.archive.save(units=units() if callable(units) else None)

    def resume(self):
        """
        Pick the campaign up where an earlier one left it.

        What was evaluated is read back from the archive, and counts against the
        budget: an exploration that was interrupted after forty designs has ten
        left to spend, not fifty. The designs are also marked as seen, so the
        search proposes something else -- and the strategy is told how they
        turned out, or it would start over from nothing but the front.

        Nothing is thrown away when the archive holds designs the space no
        longer has: those are simply not restored, and the campaign starts over.

        Whatever else the workspace already measured of this space is taken in
        at the same time (see :meth:`adopt`), and does not count against the
        budget.

        Returns:
            int: how many designs are already evaluated.
        """
        if self.settings.overwrite:
            # "Evaluate again what is already done" is what the run was asked
            # for: there is nothing to pick up.
            return 0
        genomes = self.archive.restore(self.space, self.objectives)
        evaluated = len([
            evaluation for evaluation in self.archive.evaluations if not evaluation.reused
        ])
        if genomes:
            self.seen.update(genomes)
            self.strategy.observe(self.archive.evaluations)
            printc.note(
                "Picking up where \"{0}\" left off: {1} design(s) already evaluated.".format(
                    self.archive.path, evaluated
                ),
                script_name,
            )
        self.adopt()
        return evaluated

    def adopt(self):
        """
        Start from what the workspace already measured.

        Designs of this space that some earlier run measured -- a sweep, a
        single synthesis, another campaign -- are worth exactly as much to the
        search as designs it would have run itself, and cost nothing. They are
        taken in whenever the run that produced them recorded where they sit in
        the space (see :mod:`odatix.workspace.design_point`); nothing is
        reconstructed for the ones that did not.

        They do not count against the budget: it says how many designs this
        exploration evaluates, and it evaluated none of these. They are part of
        the answer all the same, so they go into the archive and are marked as
        reused there -- which is what keeps an exploration started a second
        time from counting them as its own.

        Returns:
            list: the evaluations that were taken in.
        """
        if not getattr(self.settings, "reuse_results", True):
            return []
        known = getattr(self.evaluator, "known", None)
        if known is None:
            return []
        try:
            adopted = [
                evaluation for evaluation in known(self.space)
                if evaluation.genome not in self.seen
            ]
        except Exception as error:
            # Reading results that are already there must never be what stops
            # an exploration from starting.
            printc.warning(
                "Could not read the results already measured: {0}".format(error), script_name
            )
            return []
        if not adopted:
            return []

        self.seen.update(evaluation.genome for evaluation in adopted)
        self.strategy.observe(adopted)
        self.archive.improved_by(adopted)
        self.save()
        printc.note(
            "{0} design(s) of this space had already been measured: the search starts from "
            "them, and will not run them again.".format(len(adopted)),
            script_name,
        )
        return adopted

    def progress(self, evaluated):
        """Say how far along the campaign is, to whoever asked to be told."""
        if self.on_progress is not None:
            self.on_progress(self, evaluated)

    def next_batch(self, count):
        """
        The next designs to evaluate: what the strategy proposes, minus what has
        already been run and what the space does not actually hold.

        A strategy is free to propose a design twice -- two parents often have a
        child that already exists -- so asking again is normal and is not a sign
        that it has run out. Asking a bounded number of times is what tells the
        two apart.
        """
        designs = []
        attempts = 0
        # Enough tries to fill a batch out of a strategy that keeps proposing
        # designs already evaluated, without spinning on a space that is spent.
        while len(designs) < count and attempts < 20:
            attempts += 1
            proposed = self.strategy.propose(count - len(designs))
            if not proposed and self.strategy.exhausted:
                break
            for genome in proposed:
                design = self.space.design(genome)
                if design is None:
                    # The genome names nothing runnable -- a configuration the
                    # domain blacklists, or a combination its constraints rule
                    # out. Marked as seen so a constrained space is not asked
                    # about the same hole over and over.
                    self.seen.add(self.space.clamp(genome))
                    continue
                if design.genome in self.seen:
                    continue
                self.seen.add(design.genome)
                designs.append(design)
                if len(designs) >= count:
                    break
        return designs

    def next_wave(self, remaining):
        """
        ``async`` mode's equivalent of :meth:`next_batch` and evaluating it.

        What "batch" means here is how many designs are kept running at once,
        not how many are decided between two rounds: designs are topped back
        up to that many every time one finishes, instead of only once every
        one of them has. That is the whole difference from ``batch`` mode --
        a straggler ties up its own slot and nothing else, because the next
        design is already running next to it rather than waiting on it.

        Args:
            remaining (int): how many more designs the budget allows for,
                counting the ones already in flight.

        Returns:
            tuple: the designs that finished and what they turned out to be
            worth, in the same order. Both empty means there is nothing left
            running and nothing left to propose either.
        """
        self._top_up(remaining)
        if not self._pending:
            return [], []

        finished = self.evaluator.poll(self._pending, cancel_event=self.cancel_event)
        self.evaluator.derive()
        evaluations = [self.evaluator.collect(pending) for pending in finished]
        return [pending.design for pending in finished], evaluations

    def _top_up(self, remaining):
        """Submit designs until as many are running as the batch size asks for."""
        depth = min(max(1, int(self.search.batch)), max(0, remaining))
        while len(self._pending) < depth:
            designs = self.next_batch(1)
            if not designs:
                break
            design = designs[0]
            printc.say("  -> {0}{1}".format(design.label, self.describe_values(design)), script_name)
            self._pending.append(self.evaluator.submit(design))

    def describe_objectives(self):
        """What the campaign is looking for, as a user reads it."""
        return ", ".join(
            "{0} {1}".format("maximize" if objective.maximized else "minimize", objective.metric)
            for objective in self.objectives
        )

    def announce(self, designs, evaluated):
        """
        What a batch is about to run, before it runs it.

        A batch is hours of synthesis, and the monitor underneath shows the jobs
        without saying which design of the search each of them is: naming them
        here is what connects the two.
        """
        printc.bold("\n[batch {0}] {1} design(s), {2}/{3} evaluated so far.".format(
            self.batch_index, len(designs), evaluated, self.budget
        ))
        for design in designs:
            printc.say("  -> {0}{1}".format(design.label, self.describe_values(design)), script_name)

    def describe_values(self, design):
        """What a design is made of, when its parameters are known values."""
        if not design.values:
            return ""
        return "  ({0})".format(", ".join(
            "{0}={1}".format(name, design.values[name]) for name in sorted(design.values)
        ))

    def report(self, evaluations, evaluated, improved, elapsed=None, volume_before=None):
        """What a batch ran, what it measured, and what it changed."""
        measured = [evaluation for evaluation in evaluations if evaluation.measured]
        front = self.archive.front()
        on_front = set(id(evaluation) for evaluation in front)

        printc.bold("[batch {0}] done{1}.".format(
            self.batch_index, "" if elapsed is None else " in " + _duration(elapsed)
        ))
        for evaluation in evaluations:
            self.report_design(evaluation, id(evaluation) in on_front)

        printc.say(
            "{0}/{1} designs evaluated, {2}/{3} measured in this batch, {4} on the front{5}.".format(
                evaluated, self.budget, len(measured), len(evaluations), len(front),
                " (further out{0})".format(self.describe_growth(volume_before))
                if improved else " (no further out)",
            ),
            script_name,
        )
        self.report_best(front)
        self.report_remaining(evaluated, elapsed)

        if len(self.objectives.constraints) and not any(
            self.objectives.feasible(evaluation.costs) for evaluation in front
        ):
            # Worth saying every batch rather than once at the end: an
            # exploration that never gets there is usually a constraint written
            # the wrong way round, and an hour of synthesis is what it costs to
            # find that out at the end.
            printc.note(
                "No design meets the constraints yet: the search is heading for them.", script_name
            )

    def report_design(self, evaluation, on_front):
        """
        One design of the batch, and what it turned out to be worth.

        A design that failed is said as a warning, since it is the one thing in
        a batch that may need a user to do something about it; one that made the
        front is marked, since that is what the whole run is for.
        """
        if not evaluation.measured:
            printc.warning("  x  {0}: {1}.".format(
                evaluation.label, evaluation.note or "not measured"
            ), script_name)
            return

        numbers = ", ".join(
            "{0}: {1}".format(objective.metric, _number(evaluation.metrics.get(objective.metric)))
            for objective in self.objectives
        )
        unmet = self.objectives.constraints.unmet(evaluation.metrics) \
            if len(self.objectives.constraints) else []
        printc.say("  {0}  {1}  ({2}){3}".format(
            "*" if on_front else ".", evaluation.label, numbers,
            "  -- misses {0}".format(", ".join(unmet)) if unmet else "",
        ), script_name)

    def describe_growth(self, volume_before):
        """By how much the batch grew what the front covers, when that is known."""
        after = self.archive.progress.value
        if not volume_before or not after or after <= volume_before:
            return ""
        return ": +{0:.1f}%".format(100.0 * (after - volume_before) / volume_before)

    def report_best(self, front):
        """
        The best value reached on each objective so far.

        The front is the answer, but it grows to a size nobody reads batch after
        batch; what a reader follows between two batches is whether the numbers
        are still moving.
        """
        if not front:
            return
        bests = []
        for index, objective in enumerate(self.objectives):
            values = [
                evaluation.metrics.get(objective.metric) for evaluation in front
                if evaluation.metrics.get(objective.metric) is not None
            ]
            if not values:
                continue
            best = max(values) if objective.maximized else min(values)
            bests.append("{0} {1}: {2}".format(
                "best" if objective.maximized else "lowest", objective.metric, _number(best)
            ))
        if bests:
            printc.say("Best so far -- {0}.".format(", ".join(bests)), script_name)

    def report_remaining(self, evaluated, elapsed):
        """
        What is left to run, and roughly how long it will take.

        The estimate is the last batch's rate and nothing cleverer: batches of a
        search take wildly different times, and pretending otherwise would give
        a number a reader would then have to distrust.
        """
        left = max(0, self.budget - evaluated)
        if not left:
            return
        message = "{0} design(s) left in this campaign".format(left)
        if elapsed and self.search.batch:
            batches = (left + int(self.search.batch) - 1) // int(self.search.batch)
            message += ", about {0} more batch(es) (~{1} at this batch's pace)".format(
                batches, _duration(elapsed * batches)
            )
        printc.say(message + ".", script_name)

    def __repr__(self):
        return "<Campaign {0}>".format(self.architecture.name)


class Exploration(object):
    """
    Every campaign one "odatix dse" runs: the ones its settings file selects,
    each searching the architectures its own file names.

    Two architectures do not share parameters, so a design of one says nothing
    about a design of the other: they are searched one after the other, each
    with its own budget and its own answer.

    Args:
        workspace (Workspace): the workspace being explored.
        settings (DseSettings): how the run is run, and which campaigns it
            runs.
        campaigns (list): the campaigns, already read. They are read from the
            campaign directory when none is given (see
            :mod:`odatix.dse.campaigns`).
    """

    def __init__(self, workspace, settings=None, cancel_event=None, session=None,
                 progress_file=None, campaigns=None):
        self.workspace = workspace
        self.settings = settings if settings is not None else self.load(workspace)
        self._campaign_settings = campaigns
        self.cancel_event = cancel_event
        self.session = session
        #: Where how far along the exploration is gets written, as a percentage
        #: on a line of its own. An exploration run as a job of the daemon
        #: reports its progress the way every job does (see odatix.dse.driver).
        self.progress_file = progress_file
        self.archives = []
        #: How many designs the campaigns already over have evaluated, so that
        #: the progress being reported is that of the whole exploration.
        self._evaluated_before = 0
        self._total = 0

    @staticmethod
    def load(workspace):
        """The exploration settings of a workspace."""
        from odatix.dse.settings import DseSettings
        from odatix.workspace.settings import load_settings

        return load_settings(DseSettings, workspace.paths.dse_settings_file)

    def campaign_settings(self):
        """
        The campaigns this run selects, read from the campaign directory.

        Raises:
            CampaignError: one of them does not exist.
        """
        from odatix.dse.campaigns import CampaignNotFoundError, resolve_campaigns

        if self._campaign_settings is not None:
            return self._campaign_settings
        try:
            self._campaign_settings = resolve_campaigns(self.workspace, self.settings)
        except CampaignNotFoundError as error:
            raise CampaignError(str(error))
        return self._campaign_settings

    def campaigns(self):
        """
        One campaign per design named, campaign file by campaign file, in the
        order they were named.

        What a name is looked up in is what the campaign runs: an "odatix
        workflow" exploration searches the workflows of the workspace, every
        other one its architectures. They are swept the same way -- a workflow
        *is* an architecture, with commands instead of sources (see
        :class:`odatix.workspace.workflows.Workflow`) -- so nothing but where
        the name is read from changes.
        """
        from odatix.dse.campaigns import RunSettings
        from odatix.workspace.errors import NotFoundError

        campaigns = []
        for campaign_settings in self.campaign_settings():
            settings = RunSettings(campaign_settings, self.settings)
            for selection in settings.architecture_selections():
                try:
                    architecture = settings.designs(self.workspace)[selection.entry]
                except NotFoundError as error:
                    raise CampaignError(str(error))
                campaigns.append(
                    Campaign(
                        self.workspace, architecture, settings,
                        cancel_event=self.cancel_event, session=self.session,
                        on_progress=self.progress, selection=selection,
                    )
                )
        return campaigns

    def check(self):
        """
        What the exploration would do, without touching anything.

        Raises:
            CampaignError: it cannot be run.
        """
        if not self.campaign_settings():
            raise CampaignError(
                "The exploration names no campaign. Say which campaigns to run under "
                "\"campaigns\" in \"{0}\", or name one with \"-p\".".format(
                    self.workspace.paths.dse_settings_file
                )
            )
        campaigns = self.campaigns()
        if not campaigns:
            raise CampaignError(
                "The campaign(s) {0} name no architecture. Say which architectures to explore "
                "under \"architectures\" in their file, in \"{1}\".".format(
                    ", ".join('"{0}"'.format(settings.name) for settings in self.campaign_settings()),
                    self.workspace.paths.dse_campaign_path,
                )
            )
        return [campaign.check() for campaign in campaigns]

    def confirm(self, campaigns):
        """
        Say what the exploration amounts to, and stop for a confirmation the way
        every other run does before it starts working.

        An exploration is asked for once and then runs by itself for hours, so
        what it is about to spend is worth showing before it spends it.
        """
        from odatix.lib.utils import ask_to_continue

        for campaign in campaigns:
            printc.say(campaign.describe(), script_name)
        if not self.settings.ask_continue:
            return
        printc.bold("\nTotal: {0} design(s) to evaluate".format(
            sum(campaign.budget for campaign in campaigns)
        ))
        ask_to_continue()

    def run(self, confirm=True):
        """
        Run every campaign, and keep what each of them found.

        Args:
            confirm (bool): whether to say what the exploration amounts to and
                ask before starting. An exploration run as a job of the daemon
                was asked in the terminal the command was typed in, and says it
                again there rather than in its own log (see odatix.dse.driver).

        Returns:
            list: the :class:`~odatix.dse.archive.Archive` of each architecture.
        """
        self.archives = []
        campaigns = self.check()
        if confirm:
            self.confirm(campaigns)

        self._evaluated_before = 0
        self._total = sum(campaign.budget for campaign in campaigns)
        for campaign in campaigns:
            self.archives.append(campaign.run())
            self._evaluated_before += campaign.budget
            self.summarize(campaign.archive)
        self.report_progress(self._total)
        return self.archives

    def progress(self, campaign, evaluated):
        """
        How far along the whole exploration is: what the campaigns already over
        were given, plus what the running one has evaluated.

        A campaign that stops early -- a spent space, a front that stopped
        moving -- leaves the rest of its budget unspent, and the exploration
        counts it as spent when it moves on: what is being shown is how much of
        the work is behind, not how many designs will be run in the end.
        """
        self.report_progress(self._evaluated_before + evaluated)

    def report_progress(self, evaluated):
        """Write where the exploration is, for whoever is showing it."""
        if not self.progress_file or self._total <= 0:
            return
        percentage = max(0, min(100, int(100.0 * evaluated / self._total)))
        try:
            directory = os.path.dirname(self.progress_file)
            if directory:
                os.makedirs(directory, exist_ok=True)
            with open(self.progress_file, "w") as f:
                f.write("{0}\n".format(percentage))
        except OSError:
            # How far along it is, is not worth stopping an exploration for.
            pass

    def summarize(self, archive):
        """What one campaign found, once it is over."""
        front = archive.front()
        constraints = archive.objectives.constraints
        infeasible = [e for e in front if not archive.objectives.feasible(e.costs)]
        failed = len(archive) - len(archive.measured)
        printc.bold("\n{0}: {1} design(s) on the front, out of {2} evaluated{3}.".format(
            archive.architecture, len(front), len(archive),
            " ({0} unmeasured)".format(failed) if failed else "",
        ))
        if len(constraints) and infeasible:
            printc.warning(
                "No design met the constraints ({0}). What follows is the closest the search got, "
                "not an answer.".format("; ".join(c.describe() for c in constraints)),
                script_name,
            )
        for evaluation in front:
            numbers = ", ".join(
                "{0}: {1}".format(objective.metric, _number(evaluation.metrics.get(objective.metric)))
                for objective in archive.objectives
            )
            unmet = constraints.unmet(evaluation.metrics) if len(constraints) else []
            printc.say("  {0}  ({1}){2}".format(
                evaluation.label, numbers, " -- misses {0}".format(", ".join(unmet)) if unmet else ""
            ), script_name)
        printc.note("Written to \"{0}\".".format(archive.path), script_name)

    def __repr__(self):
        return "<Exploration of {0}>".format(self.workspace.root)
