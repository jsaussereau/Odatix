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
What it costs to know how good a design is: running it, and reading what came
out.

An evaluation is one batch of designs run through an ordinary Odatix command.
Nothing about the flows changes -- a search does not synthesize differently, it
synthesizes fewer things. What it does is write a run settings file naming the
designs of the batch, hand it to :class:`odatix.run.Run` exactly as the command
line would, wait for the daemon to be done with those jobs, and read the
metrics back out of the results file the run exported.

Reading the results back is the only new thing, and it is done through the same
records the charts are drawn from: a design is found in them by its
architecture and by the configuration of each of its parameter domains, which
is what a configuration *is* everywhere else in Odatix.

An objective is not restricted to what the synthesis measured. A batch may run
the simulations of its designs alongside the synthesis, and the derived metrics
of the workspace are recomputed once both are done, before anything is read:
whatever a testbench measured is then a metric of the synthesis record like any
other, and the search needs to know nothing about where it came from.
"""

import contextlib
import io
import os
import sys
import time

import odatix.lib.printc as printc
from odatix.dse.space import MAIN_DOMAIN
from odatix.lib.results_schema import load_results_file

__all__ = ["Evaluation", "Evaluator", "EvaluationError", "Pending"]

script_name = os.path.basename(__file__)

#: Statuses the daemon gives a job it is done with.
FINISHED_STATUSES = ("success", "done", "finished", "failed", "killed", "canceled", "cancelled", "error")

#: How often the daemon is asked whether the batch is over, in seconds. A job
#: takes minutes at the very least, so asking more often only costs requests.
POLL_INTERVAL = 5.0

#: How long the daemon may stay unreachable before the exploration gives up on
#: it, in seconds. Waiting forever on a session that will never answer again is
#: the other way an exploration hangs; treating one missed reply as the end of
#: a batch is the way it silently reads results that were never produced.
DAEMON_GRACE = 300.0

#: How often the wait says it is still waiting, in seconds. A batch of long
#: syntheses is otherwise hours of nothing in the driver log, which is
#: indistinguishable from a wait that will never end.
WAIT_HEARTBEAT = 300.0


@contextlib.contextmanager
def _quiet():
    """
    Keep what a run has to say for itself out of the search's log.

    A batch is one step of an exploration, and it says as much as a whole
    command does: what it selected, what it prepared, how many jobs it wrote.
    Repeated once per batch, that buries the only thing the log of an
    exploration is read for -- what the search learned. The jobs it starts are
    right there in the monitor, and say it better.

    What was said is handed back, so that a batch that did not run can explain
    itself with it.
    """
    captured = io.StringIO()
    stdout, stderr = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = captured
    try:
        yield captured
    finally:
        sys.stdout, sys.stderr = stdout, stderr


def _details(text, lines=20):
    """What a run said before it gave up, as something to put after a message."""
    kept = [line for line in str(text).splitlines() if line.strip()][-lines:]
    if not kept:
        return ""
    return "\n" + "\n".join("  " + line for line in kept)


def _default_session(session):
    """The daemon session a campaign works in, when it was not told one."""
    from odatix.dse.driver import default_session

    return default_session(session)


def _nb_jobs(value):
    """
    How many jobs run at once, as a run settings file is allowed to say it: an
    integer, or "auto". A number that came from a command line is a string, and
    a run refuses to start on one.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    return int(text) if text.isdigit() else (text or None)


def _freq_key(value):
    """
    A frequency as something to look a record up by.

    The results file holds it as a number, which a settings file may have said
    as "100" and a job directory as "100MHz": what matters is that 100 and 100.0
    are the same frequency.
    """
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value).strip()
    return str(int(number)) if number == int(number) else str(number)


class EvaluationError(RuntimeError):
    """A batch could not be run at all -- which stops the campaign."""


class Evaluation(object):
    """
    One design, run and measured.

    Attributes:
        design (Design): what was run.
        metrics (dict): what the run measured, as the results file holds it.
        costs (tuple): the objectives of the campaign, all turned into things
            to minimize -- None when the design was not measured, whether it
            failed to build or simply produced no number for one objective.
        note (str): why there are no costs, when there are none.
        batch (int): which batch of the campaign proposed the design. It is
            what makes the order of the search readable afterwards -- a front
            reached in three batches and one reached in thirty are not the same
            answer -- and 0 for a design read back from an archive written
            before batches were recorded.
        reused (bool): whether the design was not run by this campaign at all,
            but read from results some earlier run had already measured (see
            :meth:`Evaluator.known`). It counts for the front and not for the
            budget: nothing was spent on it.
    """

    __slots__ = ("design", "metrics", "costs", "note", "batch", "source", "reused")

    def __init__(self, design, metrics=None, costs=None, note="", batch=0, source=None,
                 reused=False):
        self.design = design
        self.metrics = dict(metrics) if metrics else {}
        self.costs = costs
        self.note = note
        self.batch = int(batch or 0)
        #: The meta of the result record the numbers were read from -- what the
        #: design was run as (type, tool, flow, target, ...). Kept so that the
        #: exported results say it, and empty for a design that produced none.
        self.source = dict(source) if source else {}
        self.reused = bool(reused)

    @property
    def genome(self):
        return self.design.genome

    @property
    def entry(self):
        return self.design.entry

    @property
    def label(self):
        """How the evaluated design is named to a user."""
        return self.design.label

    @property
    def measured(self):
        return self.costs is not None

    def to_dict(self):
        """
        The evaluation as the archive writes it: what was run, what it is made
        of, and what came out.
        """
        record = {
            "configuration": self.design.entry,
            "batch": self.batch,
            # Where the design sits in the space, so that a campaign that is
            # started again knows what it already looked at without having to
            # search the space for it (see Campaign.resume).
            "genome": list(self.design.genome),
            "parameters": dict(self.design.values),
            "metrics": dict(self.metrics),
        }
        if self.design.frequency is not None:
            # Part of what was run, and not of what the configuration names: an
            # archive that left it out would show the same design several times.
            record["frequency"] = self.design.frequency
        if self.design.chose_toolchain and self.design.toolchain is not None:
            # Same reason: what ran the design is what tells two of its records
            # apart when the search is the one that chose it.
            record["toolchain"] = self.design.toolchain.to_dict()
        if self.source:
            # What the design ran as, so that an exploration picked up again
            # can still export the results of the designs it did not re-run.
            record["source"] = dict(self.source)
        if self.reused:
            # So that an exploration started again spends its budget on designs
            # it has to run, and not on the ones it was given for free.
            record["reused"] = True
        if not self.measured:
            record["failed"] = True
            if self.note:
                record["reason"] = self.note
        return record

    def __repr__(self):
        return "<Evaluation {0}{1}>".format(self.label, "" if self.measured else " (failed)")


class Pending(object):
    """
    One design, submitted and not yet finished.

    What ties it to the daemon is the set of its own work directories -- one
    per underlying job, since a design fixed at several frequencies, or one
    whose entry is also being simulated, is still one design of the search and
    several jobs of the daemon. It counts as finished once none of them are
    left (see :meth:`Evaluator.poll`).
    """

    __slots__ = ("design", "tmp_dirs", "before_count", "failure")

    def __init__(self, design, tmp_dirs, before_count, failure=None):
        self.design = design
        self.tmp_dirs = set(tmp_dirs)
        #: How many records this design's identity already had in the results
        #: files at the moment it was submitted -- what :meth:`Evaluator.collect`
        #: reads past, the same way :meth:`Evaluator.evaluate` reads past a
        #: whole batch's "before" (see :meth:`Evaluator.measure`).
        self.before_count = before_count
        #: Why the submission itself did not go through, when it did not --
        #: a batch that turned out to be already cached is not this, and
        #: leaves it None.
        self.failure = failure

    @property
    def ready(self):
        return not self.tmp_dirs

    def __repr__(self):
        return "<Pending {0}{1}>".format(
            self.design.label, "" if self.tmp_dirs else " (ready)"
        )


class Evaluator(object):
    """
    Runs designs and reads what they are worth.

    Args:
        workspace (Workspace): the workspace being explored.
        settings (DseSettings): what the campaign was asked to do.
        objectives (Objectives): what makes a design good.
        cancel_event (threading.Event): asking the campaign to stop. Looked at
            between batches and while waiting for one.
        session (str): the daemon session the batches are enqueued into. Every
            batch of a campaign goes into the same one: a run that names no
            session gets a new daemon each time it starts, and an exploration
            starts a run per batch -- it would leave a daemon behind for every
            step of its search, and show a monitor that knows nothing of what
            the campaign already ran.
    """

    def __init__(self, workspace, settings, objectives, cancel_event=None, session=None,
                 toolchains=None):
        self.workspace = workspace
        self.settings = settings
        self.objectives = objectives
        self.cancel_event = cancel_event
        self.session = _default_session(session)
        #: What may run a design (see :class:`~odatix.dse.space.Toolchain`).
        #: Read from the settings when not given, which is what a campaign
        #: already did to build its space.
        self.toolchains = list(
            toolchains if toolchains is not None else settings.toolchains(workspace)
        )
        #: How many designs have actually been run, which is what a budget counts.
        self.count = 0

    ######################################
    # Where it works
    ######################################

    @property
    def mode(self):
        """The Odatix command each evaluation runs."""
        return self.settings.run

    @property
    def campaign_path(self):
        """
        Where the campaign keeps what belongs to it and not to the workspace:
        the run settings file of each batch.

        One directory per session, so that two explorations running at once do
        not hand each other their batches (see odatix.dse.driver).
        """
        from odatix.dse.driver import driver_paths

        return driver_paths(self.workspace, self.session)["directory"]

    def results_file(self, tool):
        return os.path.join(self.workspace.paths.result_path, "results_{0}.yml".format(tool))

    ######################################
    # What runs a design
    ######################################

    def _varies(self, attribute):
        """Whether the toolchains of the exploration differ by one of their parts."""
        return len(set(getattr(chain, attribute) for chain in self.toolchains)) > 1

    @property
    def explores_tool(self):
        return self._varies("tool")

    @property
    def explores_flow(self):
        return self._varies("flow")

    @property
    def explores_target(self):
        return self._varies("target")

    @property
    def tools(self):
        """
        The eda tools an exploration reads results from.

        One results file per tool, so a search moving between tools reads
        several of them. Falls back on what the settings name, for an
        exploration whose evaluations are not run by a tool at all.
        """
        tools = []
        for chain in self.toolchains:
            if chain.tool and chain.tool not in tools:
                tools.append(chain.tool)
        return tools or [name for name in self.settings.tool_names()]

    ######################################
    # Running a batch
    ######################################

    def evaluate(self, designs):
        """
        Run a batch of designs and measure them.

        Returns:
            list: one :class:`Evaluation` per design, in the order they came in.
            A design whose job failed comes back unmeasured rather than left
            out: a search has to be told that a place in the space leads
            nowhere, or it goes back to it.
        """
        designs = list(designs)
        if not designs:
            return []

        before = self._records()
        failure = self.run_batch(designs)
        self.count += len(designs)
        after = self._records()

        evaluations = [self.measure(design, after, before) for design in designs]
        if failure is not None and not any(evaluation.measured for evaluation in evaluations):
            # The batch did not run *and* none of its designs was already
            # measured: there is nothing to learn from it, and the next batch
            # would fail the same way.
            raise EvaluationError(failure)
        return evaluations

    @property
    def explores_frequency(self):
        """Whether the designs carry a frequency the search chose for them."""
        return bool(self.settings.explores_frequency())

    def groups(self, designs):
        """
        The batch cut up into what can be run together.

        One run does one thing: it runs with one eda tool, one of its flows, on
        the targets it is given, and a custom frequency synthesis says one set of
        frequencies for everything it selects. So designs the search gave
        different toolchains or different frequencies cannot go into the same
        run, and are grouped by what they were given instead. Every group is
        started before any of them is waited for: a batch is still one step of
        the search, whether it took one run or five.

        Returns:
            list: ``(toolchain, frequency, designs)``, the frequency being None
            when the search did not choose one.
        """
        groups = {}
        for design in designs:
            frequency = design.frequency if self.explores_frequency else None
            key = ((design.toolchain.key if design.toolchain is not None else None), frequency)
            groups.setdefault(key, (design.toolchain, frequency, []))[2].append(design)
        return [
            groups[key] for key in sorted(
                groups, key=lambda key: (key[0] or ("", "", ""), key[1] is None, key[1] or 0)
            )
        ]

    def run_batch(self, designs):
        """
        Hand a batch to the daemon through ordinary runs, and wait for them.

        The batch is written as a run settings file of its own, next to the work
        directory rather than in the workspace: a campaign must not rewrite the
        selection the user keeps in "fmax_synthesis_settings.yml".

        Nothing is attached and nothing is reconfigured: the batch goes into the
        session the exploration is itself running in (see odatix.dse.driver),
        where the monitor is already showing it, underneath the driver that
        asked for it.

        Returns:
            str: why the run did not happen, or None when it did. A run refuses
            to start when every design of the batch is already done, which is
            not a failure -- those designs are measured, they were measured
            earlier -- so the caller reads the results before deciding.
        """
        started = []
        failures = []

        # The simulations first, so that they run alongside the synthesis
        # instead of after it: neither needs the other's result, only the
        # derived metrics computed once both are done do.
        parallel_jobs, failure = self.start_simulations(designs)
        if failure is not None:
            failures.append(failure)
        if parallel_jobs is not None:
            started.append(parallel_jobs)

        for toolchain, frequency, group in self.groups(designs):
            parallel_jobs, failure = self.start_batch(group, toolchain, frequency)
            if failure is not None:
                failures.append(failure)
            if parallel_jobs is not None:
                started.append(parallel_jobs)

        for parallel_jobs in started:
            self.wait_for(parallel_jobs)
        self.derive()
        return "\n".join(failures) if failures else None

    def start_batch(self, designs, toolchain=None, frequency=None):
        """
        Enqueue one group of designs, without waiting for it.

        The toolchain is what the run is told to run with: its tool and its
        flow, and the one target it works on when the search is choosing the
        targets. A toolchain naming no flow or no target leaves the run to do
        what it does by itself -- the default flow of the tool, and every target
        its target file enables.

        Returns:
            tuple: what the run started (None when it did not), and why it did
            not (None when it did).
        """
        from odatix.run import Run
        from odatix.run.errors import NOTHING_TO_RUN, RunError

        settings_file = self.write_batch_settings(designs, toolchain, frequency)
        run = Run(
            self.workspace,
            self.mode,
            settings_file=settings_file,
            tool=(toolchain.tool if toolchain is not None else self.settings.tool),
            flow=(toolchain.flow if toolchain is not None else self.settings.flow) or None,
            targets=[toolchain.target] if toolchain is not None and toolchain.target else [],
            overwrite=self.settings.overwrite,
            nb_jobs=self.settings.nb_jobs,
            noask=True,
            detach=True,
            session=self.session,
            configure_session=False,
            cancel_event=self.cancel_event,
        )
        try:
            # What the run says about itself is not what the search's log is
            # for -- except when it refuses to run, where it is the only
            # explanation there is.
            with _quiet() as said:
                run.check()
                parallel_jobs = run.prepare()
                run.start()
        except RunError as error:
            if error.code == NOTHING_TO_RUN:
                # Every design of the group was already run by someone else.
                # Nothing to start, and nothing to report: the results are in
                # the results file, where measure() reads them from.
                return None, None
            return None, "The exploration could not run its batch of {0} design(s){1}{2}: {3}{4}".format(
                len(designs),
                "" if toolchain is None else " with {0}".format(toolchain.label),
                "" if frequency is None else " at {0} MHz".format(frequency),
                error, _details(said.getvalue()),
            )

        return parallel_jobs, None

    @property
    def simulations(self):
        """The simulations every design of a batch is run through."""
        return self.settings.simulation_names()

    def start_simulations(self, designs):
        """
        Enqueue the simulations of a batch, without waiting for them.

        A simulation is how a number no synthesis can produce -- a cycle count,
        an error rate, whatever a testbench measures -- comes to exist for the
        design being evaluated. It is not an objective by itself: what the
        search reads is the synthesis record, and the simulated number reaches
        it through a derived metric (see :meth:`derive`).

        The designs are named by the same entry the synthesis selects, each of
        them once: what a simulation measures does not depend on the frequency
        the search may have chosen, so a design evaluated at two frequencies is
        still simulated once.

        Returns:
            tuple: what the run started (None when there was nothing to
            simulate, or when it did not start), and why it did not.
        """
        if not self.simulations:
            return None, None

        from odatix.run import Run
        from odatix.run.errors import NOTHING_TO_RUN, RunError

        settings_file = self.write_simulation_settings(designs)
        run = Run(
            self.workspace,
            "simulation",
            settings_file=settings_file,
            overwrite=self.settings.overwrite,
            nb_jobs=self.settings.nb_jobs,
            noask=True,
            detach=True,
            session=self.session,
            configure_session=False,
            cancel_event=self.cancel_event,
        )
        try:
            with _quiet() as said:
                run.check()
                parallel_jobs = run.prepare()
                run.start()
        except RunError as error:
            if error.code == NOTHING_TO_RUN:
                return None, None
            return None, "The exploration could not simulate its batch of {0} design(s): {1}{2}".format(
                len(designs), error, _details(said.getvalue()),
            )

        return parallel_jobs, None

    def write_simulation_settings(self, designs):
        """
        The run settings file of the simulations of one batch: the settings the
        workspace already holds for "odatix sim", with every named simulation
        pointed at the designs being evaluated.

        The selection the user keeps is replaced rather than added to: an
        exploration simulates the designs it is evaluating, and nothing else.
        """
        from odatix.workspace.jobs import job_config

        source = self.workspace.jobs["simulation"]
        settings = source.settings_class.from_dict(
            source.settings.to_dict() if source.exists else {}
        )

        entries = []
        for design in designs:
            if design.entry not in entries:
                entries.append(design.entry)
        settings.simulations = dict((name, list(entries)) for name in self.simulations)
        settings.overwrite = bool(self.settings.overwrite)
        settings.ask_continue = False
        settings.nb_jobs = _nb_jobs(self.settings.nb_jobs) or settings.nb_jobs

        path = os.path.join(self.campaign_path, "simulation_batch.yml")
        batch = job_config(path, "simulation")
        batch.settings = settings
        batch.save(regenerate=True)
        return path

    def derive(self):
        """
        Recompute the derived metrics of the workspace, now that the batch is
        over and before it is measured.

        This is what lets an objective be something the synthesis never
        measured. A derived metric copies a number from a record of another kind
        -- the cycle count of a simulation, typically -- onto the synthesis
        record, or computes an expression over the metrics that record now has;
        either way the result is an ordinary metric of an ordinary record, which
        is why the search needs to know nothing about where it came from (see
        :mod:`odatix.lib.derived_metrics`).

        It cannot be done when a job finishes, since the record it borrows from
        may belong to a job still running, so it is a whole-workspace pass. It
        is idempotent, which is what makes running it once per batch cheap
        enough to be worth the certainty.

        Returns:
            bool: whether anything was derived at all. A workspace that declares
            no derived metric does not pay for the pass.
        """
        path = getattr(self.workspace.paths, "derived_metrics_file", None)
        if not path or not os.path.isfile(path):
            return False

        from odatix.components.export_derived_metrics import apply_derived_metrics

        try:
            with _quiet():
                apply_derived_metrics(self.workspace.paths.result_path, path)
        except Exception as error:
            # A design whose objective could not be derived comes back
            # unmeasured, which the campaign already reports design by design:
            # there is nothing here worth stopping an exploration for.
            printc.warning(
                "Could not derive the metrics of this batch: {0}".format(error), script_name
            )
            return False
        return True

    def write_batch_settings(self, designs, toolchain=None, frequency=None):
        """
        The run settings file of one batch: the settings of the command being
        run, with its selection replaced by the designs to evaluate.

        Starting from the file the workspace already holds is what lets a
        campaign say nothing about frequencies, bounds or targets: whatever the
        user set for "odatix fmax" is what an evaluation runs with.
        """
        from odatix.workspace.jobs import job_config

        source = self.workspace.jobs[self.mode]
        settings = source.settings_class.from_dict(
            source.settings.to_dict() if source.exists else {}
        )
        settings[source.selection_key] = [design.entry for design in designs]
        settings.overwrite = bool(self.settings.overwrite)
        settings.ask_continue = False
        settings.nb_jobs = _nb_jobs(self.settings.nb_jobs) or settings.nb_jobs
        self.set_frequencies(settings, frequency)

        # One file per group of a batch, named after what tells the groups
        # apart, so that what a run was handed is still readable afterwards.
        name = "{0}_batch".format(self.mode)
        if toolchain is not None and (self.explores_tool or self.explores_flow or self.explores_target):
            name += "_{0}".format(toolchain.slug())
        if frequency is not None:
            name += "_{0}MHz".format(frequency)
        path = os.path.join(self.campaign_path, "{0}.yml".format(name))
        batch = job_config(path, self.mode)
        batch.settings = settings
        batch.save(regenerate=True)
        return path

    def set_frequencies(self, settings, frequency):
        """
        Tell a batch of custom frequency synthesis what to run at.

        The exploration settings say it in one of two ways: a frequency the
        search chose for this group of designs, or the fixed frequencies every
        design of the campaign is run at. Either one replaces whatever the
        workspace holds -- the point of saying it in the exploration settings is
        that it is not the same question as "what does 'odatix synth' run at" --
        and saying neither leaves the workspace's own frequencies alone.
        """
        if not self.settings.uses_frequencies():
            return settings

        chosen = [frequency] if frequency is not None else self.settings.frequency_values()
        if not chosen:
            return settings

        frequencies = settings.frequencies
        frequencies.frequencies = [int(value) for value in chosen]
        frequencies.use_custom_freq_list = True
        # A range next to them would add frequencies nobody asked for, and the
        # architectures' own would be run instead of the ones chosen here.
        frequencies.use_custom_freq_range = False
        frequencies.override = True
        return settings

    def _daemon_statuses(self, waited_since, what):
        """
        What the daemon says about its jobs, by work directory.

        Returns ``None`` when the session could not be reached, rather than an
        empty answer: a caller that cannot tell those apart concludes that
        every job it was waiting on has finished, and goes on to read results
        that do not exist. Raises once the session has been silent for
        :data:`DAEMON_GRACE`, so that an exploration whose daemon died ends
        with a reason instead of polling forever.
        """
        from odatix.lib.parallel_job_handler.daemon_control import (
            JOBS_QUERY_TIMEOUT_BLOCKING,
            daemon_jobs_report,
        )

        try:
            report = daemon_jobs_report(
                workspace_root=self.workspace.root, timeout=JOBS_QUERY_TIMEOUT_BLOCKING
            )
        except Exception as error:
            report = None
            reason = "{0}: {1}".format(error.__class__.__name__, error)
        else:
            reason = ", ".join(report["unreachable"])

        if report is None or report["unreachable"] or not report["queried"]:
            silent_for = time.time() - waited_since[0]
            if silent_for >= DAEMON_GRACE:
                raise EvaluationError(
                    "The daemon session stopped answering while {0} ({1:.0f}s without a reply): {2}".format(
                        what, silent_for, reason or "no session found"
                    )
                )
            printc.warning(
                "daemon did not answer while {0} ({1:.0f}s so far): {2}".format(
                    what, silent_for, reason or "no session found"
                ),
                script_name,
            )
            return None

        waited_since[0] = time.time()
        statuses = {}
        for job in report["jobs"]:
            directory = job.get("tmp_dir") if isinstance(job, dict) else None
            if directory:
                statuses[os.path.realpath(str(directory))] = str(job.get("status", "")).strip().lower()
        return statuses

    def wait_for(self, parallel_jobs):
        """
        Block until the daemon is done with every job of the batch.

        This is what a batch amounts to, from the search's point of view: it
        hands its designs over and has nothing to do until they are done. The
        jobs are followed by their work directories, which is what the daemon
        reports them under.
        """
        pending = set(
            os.path.realpath(str(job.tmp_dir))
            for job in (getattr(parallel_jobs, "job_list", None) or [])
            if getattr(job, "tmp_dir", None)
        )
        if not pending:
            return

        total = len(pending)
        started = time.time()
        answered_at = [started]
        last_heartbeat = started
        first = True
        while pending:
            if self.cancel_event is not None and self.cancel_event.is_set():
                raise EvaluationError("The exploration was cancelled while a batch was running.")
            if not first:
                time.sleep(POLL_INTERVAL)
            first = False

            known = self._daemon_statuses(answered_at, "waiting for a batch")
            if known is None:
                continue

            for directory in list(pending):
                status = known.get(directory)
                if status is None or status in FINISHED_STATUSES:
                    # Either the daemon is done with it, or it does not know it
                    # any more -- a session that exited took its jobs with it.
                    pending.discard(directory)

            now = time.time()
            if pending and now - last_heartbeat >= WAIT_HEARTBEAT:
                last_heartbeat = now
                printc.say(
                    "still waiting on {0}/{1} job(s) after {2:.0f}s".format(len(pending), total, now - started),
                    script_name,
                )

    ######################################
    # Running one design at a time
    ######################################

    def begin_async(self):
        """
        Start a rolling session: designs may from now on be submitted one at a
        time and polled without waiting on a whole batch (see :meth:`submit`,
        :meth:`poll`, :meth:`collect`), which is what a campaign's ``async``
        mode runs on.

        Only what a simulation is shared by needs remembering between calls --
        one entry may be the design of several genomes, an explored frequency
        does not change what a testbench measures, and it is submitted once
        for all of them (see :meth:`submit`).
        """
        self._async_simulated_entries = set()
        self._async_simulation_jobs = {}

    def submit(self, design):
        """
        Enqueue one design, without waiting for it.

        Its own synthesis is always started; its entry's simulation only the
        first time that entry comes up. Both go into the same daemon session a
        batch would have used, which is what lets a design started this way
        run alongside whatever a batch already had running rather than behind
        it -- the whole point of an async campaign.

        Returns:
            Pending: what to hand to :meth:`poll` and, once it is ready, to
            :meth:`collect`.
        """
        before_count = len(self._records().get(self.design_identity(design), []))

        failures = []
        tmp_dirs = set()

        if self.simulations:
            if design.entry not in self._async_simulated_entries:
                self._async_simulated_entries.add(design.entry)
                parallel_jobs, failure = self.start_simulations([design])
                if failure is not None:
                    failures.append(failure)
                self._async_simulation_jobs[design.entry] = self._tmp_dirs_of(parallel_jobs)
            tmp_dirs |= self._async_simulation_jobs.get(design.entry, set())

        for toolchain, frequency, group in self.groups([design]):
            parallel_jobs, failure = self.start_batch(group, toolchain, frequency)
            if failure is not None:
                failures.append(failure)
            tmp_dirs |= self._tmp_dirs_of(parallel_jobs)

        self.count += 1
        return Pending(design, tmp_dirs, before_count, failure="\n".join(failures) or None)

    @staticmethod
    def _tmp_dirs_of(parallel_jobs):
        return set(
            os.path.realpath(str(job.tmp_dir))
            for job in (getattr(parallel_jobs, "job_list", None) or [])
            if getattr(job, "tmp_dir", None)
        )

    def poll(self, pending, cancel_event=None):
        """
        Wait until at least one design of ``pending`` is finished.

        A design already resolved when it was submitted -- a cache hit, or a
        submission that failed outright and started nothing -- is returned
        immediately, without asking the daemon anything, which is what lets a
        campaign keep moving when a whole run of designs turns out to already
        be done. Every design returned is removed from ``pending``, which is
        what makes it safe to call again with what is left.

        Args:
            pending (list): the :class:`Pending` designs to wait on. Mutated
                in place: what is returned is taken out of it.
            cancel_event (threading.Event): asking the wait to stop.

        Returns:
            list: the designs that are ready to :meth:`collect`, in no
            particular order.
        """
        resolved = [item for item in pending if item.ready]
        if resolved:
            for item in resolved:
                pending.remove(item)
            return resolved

        started = time.time()
        answered_at = [started]
        last_heartbeat = started
        first = True
        while True:
            if cancel_event is not None and cancel_event.is_set():
                raise EvaluationError("The exploration was cancelled while designs were running.")
            if not first:
                time.sleep(POLL_INTERVAL)
            first = False

            known = self._daemon_statuses(answered_at, "waiting for designs")
            if known is None:
                continue

            now = time.time()
            if now - last_heartbeat >= WAIT_HEARTBEAT:
                last_heartbeat = now
                printc.say(
                    "still waiting on {0} design(s) after {1:.0f}s".format(len(pending), now - started),
                    script_name,
                )

            finished = []
            for item in pending:
                item.tmp_dirs = set(
                    directory for directory in item.tmp_dirs
                    if known.get(directory) is not None and known.get(directory) not in FINISHED_STATUSES
                )
                if item.ready:
                    finished.append(item)
            if finished:
                for item in finished:
                    pending.remove(item)
                return finished

    def collect(self, pending):
        """
        What a finished design turned out to be worth (see :meth:`measure`).

        Called once :meth:`derive` has been run again for whatever just
        finished -- collecting before that would measure a design against
        derived metrics from before its own simulation was accounted for,
        which would only be correct by accident.
        """
        after = self._records()
        identity = self.design_identity(pending.design)
        before = {identity: [None] * pending.before_count}
        evaluation = self.measure(pending.design, after, before)
        if not evaluation.measured and pending.failure:
            evaluation.note = pending.failure
        return evaluation

    ######################################
    # Measuring what came out
    ######################################

    def _records(self):
        """
        The result records that exist right now, by what identifies the design
        they belong to.

        Read before and after a batch so that a design is measured by what its
        own run produced. Reading only "after" would take an older result of the
        same design for the new one, which is what makes a campaign run with
        "overwrite" report the same numbers twice.

        Every tool the exploration may run with is read, since a search that
        chooses the tool has its designs spread over one results file per tool.
        """
        records = {}
        for tool in self.tools:
            path = self.results_file(tool)
            if not os.path.isfile(path):
                continue
            try:
                results = load_results_file(path)
            except Exception as error:
                printc.warning("Could not read \"{0}\": {1}".format(path, error), script_name)
                continue

            for record in results.records:
                meta = record.get("meta", {}) if isinstance(record, dict) else {}
                records.setdefault(self.identity(meta), []).append(record)
        return records

    def known(self, space):
        """
        The designs of ``space`` that something already measured.

        A workspace is full of results nobody explored towards: a sweep of one
        parameter, a single synthesis, an earlier campaign that was looking for
        something else. Each of those is a design of the space evaluated at no
        cost -- provided the run that produced it recorded where it sits (see
        :mod:`odatix.workspace.design_point`), which is the only thing that
        says what a record *is* in the space rather than what it is called.
        Nothing is reconstructed: a record without coordinates is read for the
        front, as it always was, and not for the search.

        The records are read the way a batch of the campaign is read -- one
        design keeps the best of its records, measured against this campaign's
        own objectives -- so a design given for free is worth exactly what it
        would have been worth had the campaign run it itself.

        Args:
            space (ArchitectureSpace): the space being searched.

        Returns:
            list: one :class:`Evaluation` per design found, marked as reused.
        """
        from odatix.workspace import design_point

        architecture = str(getattr(space, "name", "") or "")
        by_genome = {}
        for records in self._records().values():
            for record in records:
                meta = record.get("meta", {}) if isinstance(record, dict) else {}
                if str(meta.get("architecture", "")) != architecture:
                    continue
                genome = space.genome_of(
                    design_point.point_of_meta(meta),
                    configurations=self._record_configurations(meta),
                    frequency=meta.get("frequency") if self.explores_frequency else None,
                    toolchain=self._record_toolchain(meta),
                )
                if genome is None:
                    continue
                by_genome.setdefault(genome, []).append(record)

        known = []
        for genome, records in by_genome.items():
            design = space.design(genome, project=False)
            if design is None:
                continue
            metrics, source = self.best_of(records)
            costs = self.objectives.costs(metrics)
            if costs is None:
                # Measured, but not for what this campaign is looking for: a
                # design the search would learn nothing from is left to be run.
                continue
            known.append(Evaluation(
                design, metrics=metrics, costs=costs, source=source, reused=True,
            ))
        return known

    @staticmethod
    def _record_configurations(meta):
        """What a record says each parameter domain of its design was set to."""
        reserved = ("type", "tool", "flow", "step", "target", "configuration", "frequency",
                    "timestamp", "architecture")
        configurations = {}
        for key, value in meta.items():
            if key in reserved or str(key).startswith("_"):
                continue
            # The results schema names the main domain "main" (see
            # odatix.lib.results_schema).
            configurations[MAIN_DOMAIN if key == "main" else str(key)] = str(value)
        return configurations

    def _record_toolchain(self, meta):
        """
        What ran a record, kept down to what the search chose.

        A record always names a tool, a flow and a target; the space only holds
        the ones the campaign is choosing between, and leaves the others empty
        -- what a toolchain nobody is searching looks like.
        """
        from odatix.dse.space import Toolchain

        if not (self.explores_tool or self.explores_flow or self.explores_target):
            return None
        return Toolchain(
            str(meta.get("tool", "") or "") if self.explores_tool else "",
            str(meta.get("flow", "") or "") if self.explores_flow else "",
            str(meta.get("target", "") or "") if self.explores_target else "",
        )

    def units(self):
        """
        The unit of every metric, as the results files of the tools declare it.

        Read for the export of the campaign (:mod:`odatix.dse.export`): the
        designs it writes are the ones these files measured, so they are
        measured in the same units.
        """
        units = {}
        for tool in self.tools:
            path = self.results_file(tool)
            if not os.path.isfile(path):
                continue
            try:
                units.update(load_results_file(path).units or {})
            except Exception:
                continue
        return units

    def identity(self, meta):
        """
        What tells the design a record belongs to: its architecture, and the
        configuration of each of its parameter domains -- plus whatever else the
        search chose for it, since two records that differ by one of those are
        then two designs. That is the frequency it was synthesized at, and what
        ran it: the eda tool, its flow, its target.

        What the search did *not* choose is left out, so that an exploration
        running one tool over every target its file enables still sees one
        design with several records, and keeps the best of them.
        """
        reserved = ("type", "tool", "flow", "step", "target", "configuration", "frequency", "timestamp")
        domains = tuple(sorted(
            (str(key), str(value))
            for key, value in meta.items()
            if key not in reserved and not str(key).startswith("_") and key != "architecture"
        ))
        frequency = _freq_key(meta.get("frequency")) if self.explores_frequency else None
        return (str(meta.get("architecture", "")), domains, frequency, self.toolchain_key(meta))

    def toolchain_key(self, meta):
        """What a record says ran it, kept down to what the search chose."""
        return (
            str(meta.get("tool", "") or "") if self.explores_tool else "",
            str(meta.get("flow", "") or "") if self.explores_flow else "",
            str(meta.get("target", "") or "") if self.explores_target else "",
        )

    def design_toolchain_key(self, design):
        toolchain = design.toolchain
        if toolchain is None:
            return ("", "", "")
        return (
            toolchain.tool if self.explores_tool else "",
            toolchain.flow if self.explores_flow else "",
            toolchain.target if self.explores_target else "",
        )

    def design_identity(self, design):
        domains = {MAIN_DOMAIN: design.configuration}
        domains.update(
            (name, value) for name, value in design.configurations.items() if name != MAIN_DOMAIN
        )
        # A record names the main configuration "main", the way the results
        # schema flattens the parameter domains.
        flattened = [("main", domains.pop(MAIN_DOMAIN))]
        flattened.extend((name, value) for name, value in domains.items())
        frequency = _freq_key(design.frequency) if self.explores_frequency else None
        return (
            design.architecture,
            tuple(sorted((str(k), str(v)) for k, v in flattened)),
            frequency,
            self.design_toolchain_key(design),
        )

    def measure(self, design, after, before):
        """
        What a design turned out to be worth, from the records its run added.

        A campaign asks for a metric; where the number comes from is the
        results file's business. The dimensions a record carries as numbers
        count as metrics too, which is how "frequency" -- where an fmax
        synthesis puts its answer -- is an objective like any other.
        """
        identity = self.design_identity(design)
        new = list(after.get(identity, []))
        if not new:
            return Evaluation(design, note="the run produced no result for this design")

        previous = before.get(identity, [])
        if len(new) > len(previous):
            new = new[len(previous):]

        metrics, source = self.best_of(new)
        costs = self.objectives.costs(metrics)
        if costs is None:
            missing = [
                metric for metric in self.objectives.measured_metrics if metrics.get(metric) is None
            ]
            return Evaluation(
                design, metrics=metrics, source=source,
                note="nothing was measured for: {0}".format(", ".join(missing)),
            )
        return Evaluation(design, metrics=metrics, costs=costs, source=source)

    def best_of(self, records):
        """
        One set of numbers for a design that produced several records.

        A design synthesized at ten frequencies has ten records; the design is
        worth what its best one is worth. "Best" is the campaign's own
        objectives, so an exploration maximizing the frequency keeps the
        fastest record, and one minimizing the area keeps the smallest -- and,
        when the campaign declared constraints, a record that meets them is
        kept over one that does not, however fast it was. The design is being
        run at ten frequencies to find one that works; keeping the fastest of
        the ones that do not would be answering another question.

        Returns:
            tuple: the metrics of the best record, and the meta of that record
            -- which is what the design was actually run as, and is what the
            exported results say about it (see :mod:`odatix.dse.export`).
        """
        from odatix.dse.objectives import violation_of

        best = None
        best_meta = {}
        best_rank = None
        for record in records:
            metrics = self.metrics_of(record)
            meta = dict(record.get("meta", {}) or {})
            costs = self.objectives.costs(metrics)
            if costs is None:
                if best is None:
                    best, best_meta = metrics, meta
                continue
            rank = (violation_of(costs), tuple(costs))
            if best_rank is None or rank < best_rank:
                best, best_meta, best_rank = metrics, meta, rank
        return (best if best is not None else {}), best_meta

    @staticmethod
    def metrics_of(record):
        """
        Everything a record says in numbers: the metrics it measured, plus the
        dimensions that are numbers themselves.
        """
        metrics = dict(record.get("metrics", {}) or {})
        for key, value in (record.get("meta", {}) or {}).items():
            if str(key).startswith("_") or key in metrics:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            metrics[str(key)] = value
        return metrics

    def __repr__(self):
        return "<Evaluator {0} ({1} evaluated)>".format(self.mode, self.count)
