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
What a campaign found, kept where a user can read it.

The metrics themselves are already exported the way every Odatix run exports
them, and the charts already draw them: an exploration adds no result format.
What it adds is the part a results file cannot say -- which designs the search
looked at, in what order, and which of them are the answer.

The file is written after every batch, not at the end. An exploration is long
and is going to be interrupted; what it knew when it stopped has to be on disk.
"""

import os

import odatix.lib.printc as printc
from odatix.dse.objectives import Progress, pareto_front
from odatix.workspace.yaml_io import file_header

__all__ = ["Archive"]

script_name = os.path.basename(__file__)

TITLE = "Design space exploration"

NOTICE = (
    "\n"
    "# What the search evaluated, in the order it evaluated it, and which of those\n"
    "# designs are the answer: the ones no other design beats on every objective at\n"
    "# once (the Pareto front).\n"
    "#\n"
    "# The metrics themselves are in the results file of the run, and are read from\n"
    "# there by the result explorer like any other result. Deleting this file loses\n"
    "# the trace of the search, not the results it produced.\n"
    "\n"
)


class Archive(object):
    """
    The record of one campaign.

    Args:
        path (str): the file to write.
        architecture (str): the architecture that was searched.
        objectives (Objectives): what it was searched for.
        tolerance (float): how much of the front's hypervolume a batch has to
            add for it to count as progress (see
            :class:`~odatix.dse.objectives.Progress`).
    """

    def __init__(self, path, architecture, objectives, strategy="", space_size=0, tolerance=0.0,
                 results_path=None):
        self.path = path
        #: Where the designs the search evaluated are exported as an ordinary
        #: Odatix results file, or None to export none (see
        #: :mod:`odatix.dse.export`).
        self.results_path = results_path
        self.architecture = architecture
        self.objectives = objectives
        self.strategy = strategy
        self.space_size = space_size
        self.evaluations = []
        #: How good the front is, and whether it is still getting better.
        self.progress = Progress(tolerance)

    ######################################
    # What it holds
    ######################################

    def add(self, evaluations):
        self.evaluations.extend(evaluations)
        return self

    @property
    def measured(self):
        """The evaluations that produced a number for every objective."""
        return [evaluation for evaluation in self.evaluations if evaluation.measured]

    def front(self):
        """
        The best designs found: the ones nothing dominates.

        This is the answer of the campaign -- not one design but the whole
        trade-off curve, since nothing said how a megahertz compares to a LUT.
        """
        measured = self.measured
        return [measured[index] for index in pareto_front([e.costs for e in measured])]

    def history(self):
        """
        What the front was worth after each batch.

        This is what makes a campaign readable as a *search* and not only as a
        list of designs: a front reached in three batches and one reached in
        thirty are not the same answer, and a curve that went flat ten batches
        ago says the budget of the next run can be smaller.

        It is recomputed here rather than recorded batch by batch, because the
        volume is measured against the worst of every objective seen so far
        (see :class:`~odatix.dse.objectives.Progress`) -- a corner that moves
        as the search discovers bad designs. Two volumes measured against two
        different corners do not belong on one curve, so the whole curve is
        measured again, against the corner known now.

        Returns:
            list: one entry per batch, in order.
        """
        measured = self.measured
        if not measured:
            return []
        self.progress.observe([evaluation.costs for evaluation in measured])

        history = []
        # Every batch, and not only the ones that measured something: a batch
        # whose designs all failed to build spent the budget and moved the
        # front nowhere, which is exactly what a flat point on the curve says.
        for batch in sorted(set(evaluation.batch for evaluation in self.evaluations)):
            # Everything known once that batch was done -- so the curve grows
            # the way the campaign learned, not the way it was written down.
            so_far = [evaluation for evaluation in measured if evaluation.batch <= batch]
            costs = [so_far[index].costs for index in pareto_front([e.costs for e in so_far])]
            history.append({
                "batch": batch,
                "evaluated": len([e for e in self.evaluations if e.batch <= batch]),
                "measured": len(so_far),
                "front": len(costs),
                "hypervolume": self.progress.of(costs),
            })
        return history

    def improved_by(self, evaluations):
        """
        Whether a batch made the answer better.

        A campaign stops when several batches in a row have not: continuing to
        synthesize designs that do not move the front is spending hours to learn
        nothing.

        What is compared is how much the front covers -- its hypervolume -- and
        not which designs are on it. Asking whether the front changed answers
        yes to a design a hair better on a single objective just as readily as
        to one that opened up a whole region of trade-offs, which makes a poor
        reason to spend another batch of synthesis or to stop spending it. The
        volume says how much was gained, so how much is worth going on for can
        be said too (see :class:`~odatix.dse.objectives.Progress`).
        """
        before = [evaluation.costs for evaluation in self.front()]
        self.add(evaluations)
        after = [evaluation.costs for evaluation in self.front()]
        return self.progress.improved(before, after)

    ######################################
    # Reading it back
    ######################################

    def restore(self, space, objectives=None):
        """
        Put back what a previous run of this campaign had already evaluated.

        An exploration is long and is interrupted -- a machine goes down, a user
        stops the monitor, a driver is killed from it. What it had done is on
        disk after every batch, and starting again from an empty archive would
        spend the whole budget a second time on designs that are already
        synthesized.

        A design is found back by the genome the archive kept with it: it is a
        place in the space, which is what tells the search where it has been.
        Records without one were written before, and are read for the front but
        not for the search.

        Args:
            space (ArchitectureSpace): the space the campaign searches. The
                designs are rebuilt from it, so that a search that has moved on
                (an architecture whose parameters changed) starts over rather
                than reasoning about designs that no longer exist.
            objectives (Objectives): what makes a design good, when it is not
                the ones the archive was built with.

        Returns:
            list: the genomes that are already evaluated.
        """
        import yaml

        from odatix.dse.evaluation import Evaluation

        if not os.path.isfile(self.path):
            return []
        try:
            with open(self.path, "r") as f:
                content = yaml.safe_load(f) or {}
        except Exception:
            return []
        if not isinstance(content, dict) or content.get("architecture") != self.architecture:
            return []

        objectives = objectives if objectives is not None else self.objectives
        restored = []
        genomes = []
        for record in content.get("evaluations") or []:
            if not isinstance(record, dict):
                continue
            genome = record.get("genome")
            if not isinstance(genome, list) or len(genome) != len(space.lengths):
                # The space is not the one that was searched: the architecture
                # gained or lost a parameter since.
                continue
            design = space.design(tuple(int(gene) for gene in genome))
            if design is None:
                continue
            metrics = record.get("metrics") or {}
            costs = None if record.get("failed") else objectives.costs(metrics)
            restored.append(Evaluation(
                design, metrics=metrics, costs=costs, note=record.get("reason", ""),
                batch=record.get("batch") or 0, source=record.get("source"),
            ))
            genomes.append(design.genome)

        self.evaluations = restored
        return genomes

    ######################################
    # Writing it down
    ######################################

    def record(self, evaluation):
        """
        One evaluation as the file holds it, with what the constraints made of
        it -- a design that broke one is on record as having broken it, and
        which, rather than as a number a reader has to check by hand.
        """
        written = evaluation.to_dict()
        if evaluation.measured and len(self.objectives.constraints):
            unmet = self.objectives.constraints.unmet(evaluation.metrics)
            written["feasible"] = not unmet
            if unmet:
                written["unmet"] = unmet
        return written

    def to_dict(self):
        front = self.front()
        costs = [evaluation.costs for evaluation in front]
        written = {
            "architecture": self.architecture,
            "strategy": self.strategy,
            "objectives": self.objectives.to_list(),
        }
        if len(self.objectives.constraints):
            written["constraints"] = self.objectives.constraints.to_list()
            # A front that meets none of them is the search saying it did not
            # find the feasible part of the space, and is worth saying outright:
            # the designs below are then the closest it got, not the answer.
            written["feasible"] = bool(costs) and all(
                self.objectives.feasible(cost) for cost in costs
            )
        written.update({
            "designs_in_space": self.space_size,
            "evaluated": len(self.evaluations),
            "measured": len(self.measured),
            # How far the front reaches, which is what a campaign is trying to
            # grow: two runs of the same exploration are compared by it.
            "hypervolume": self.progress.observe(costs).of(costs),
            "history": self.history(),
            "front": [self.record(evaluation) for evaluation in front],
            "evaluations": [self.record(evaluation) for evaluation in self.evaluations],
        })
        return written

    def save(self, units=None):
        """
        Write what is known so far, replacing what was written before it.

        The designs are exported alongside as an ordinary results source (see
        :mod:`odatix.dse.export`), so that the explorer charts what the search
        found without knowing anything about searches. Failing to write it does
        not fail the campaign: the archive is the record, the export is a
        convenience, and an exploration that ran for six hours is not thrown
        away over a results file that could not be written.
        """
        import yaml

        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(self.path, "w") as f:
            f.write(file_header(TITLE) + NOTICE)
            yaml.safe_dump(self.to_dict(), f, default_flow_style=False, sort_keys=False)

        if self.results_path:
            from odatix.dse.export import export_results

            try:
                export_results(self, self.results_path, units=units)
            except Exception as error:
                printc.warning(
                    "Could not export the results of the exploration to \"{0}\": {1}".format(
                        self.results_path, error
                    ),
                    script_name,
                )
        return self

    def __len__(self):
        return len(self.evaluations)

    def __repr__(self):
        return "<Archive {0} ({1} evaluated, {2} on the front)>".format(
            self.architecture, len(self.evaluations), len(self.front())
        )
