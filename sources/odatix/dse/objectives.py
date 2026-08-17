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
What makes one design better than another.

A sweep does not need this: it runs everything and the user looks at the charts
afterwards. A search does -- it has to decide, before the next batch, which of
the designs it has already run are worth going back to.

Odatix does not ask for the objectives to be weighed against each other. A
smaller design that runs slower is not worse than a faster one that is bigger;
it is a different trade-off, and both belong to the answer. So "better" here is
*dominance*: a design is better than another when it is at least as good on
every objective and strictly better on one. What a search is looking for is the
set of designs nothing dominates -- the Pareto front -- which is exactly the
curve a user draws by hand today after a full sweep.

Constraints, when a campaign declares any, come in one step earlier: a design
that does not meet them loses to one that does before any of this is looked at
(see :mod:`odatix.dse.constraints`). Every cost vector carries how far its
design is from feasible, and :func:`dominates` reads it first.
"""

__all__ = [
    "Objective",
    "Objectives",
    "Costs",
    "MINIMIZE",
    "MAXIMIZE",
    "dominates",
    "pareto_front",
    "non_dominated_sort",
    "crowding_distances",
    "hypervolume",
    "Progress",
]

MINIMIZE = "min"
MAXIMIZE = "max"

#: What a settings file may write for each direction. "min"/"max" is what the
#: documentation shows; the rest is what a user is likely to write instead.
GOALS = {
    "min": MINIMIZE, "minimize": MINIMIZE, "minimise": MINIMIZE, "lower": MINIMIZE, "low": MINIMIZE,
    "max": MAXIMIZE, "maximize": MAXIMIZE, "maximise": MAXIMIZE, "higher": MAXIMIZE, "high": MAXIMIZE,
}


class Costs(tuple):
    """
    A cost vector, and how far the design it came from is from feasible.

    It is a plain tuple of numbers to minimize, which is all that sorting,
    crowding and hypervolume ever wanted of it; the violation rides along as an
    attribute so that :func:`dominates` can put feasibility first without every
    function in between having to carry a second argument for it.

    A campaign with no constraints produces vectors whose violation is zero,
    which is what a bare tuple reads as too -- code that builds one by hand, and
    archives written before constraints existed, keep working unchanged.
    """

    # No __slots__: a subclass of tuple cannot have any, since the tuple itself
    # is already laid out at the end of the object.

    def __new__(cls, values, violation=0.0):
        costs = tuple.__new__(cls, values)
        costs.violation = float(violation or 0.0)
        return costs

    @property
    def feasible(self):
        return not self.violation


def violation_of(costs):
    """How far a cost vector is from feasible, zero for anything without one."""
    return getattr(costs, "violation", 0.0) or 0.0


class Objective(object):
    """
    One thing a search tries to get out of a design.

    Args:
        metric (str): what is read off the results of an evaluation. Any metric
            an Odatix run exports, plus the dimensions the results carry as
            numbers -- "frequency" being the one that matters, since that is
            where an fmax synthesis puts its answer.
        goal (str): "min" or "max".
    """

    __slots__ = ("metric", "goal")

    def __init__(self, metric, goal=MINIMIZE):
        self.metric = str(metric)
        key = str(goal).strip().lower()
        if key not in GOALS:
            raise ValueError(
                "Unknown goal \"{0}\" for objective \"{1}\": it is either \"min\" or \"max\".".format(goal, metric)
            )
        self.goal = GOALS[key]

    @property
    def maximized(self):
        return self.goal == MAXIMIZE

    def cost_of(self, value):
        """
        The value as something to *minimize*, whichever way the objective goes.

        Everything downstream compares costs, so that dominance, sorting and
        the spread of a front are written once instead of once per direction.
        """
        return -float(value) if self.maximized else float(value)

    def to_dict(self):
        return {"metric": self.metric, "goal": self.goal}

    def __repr__(self):
        return "<Objective {0} {1}>".format(self.goal, self.metric)

    def __eq__(self, other):
        if not isinstance(other, Objective):
            return NotImplemented
        return self.metric == other.metric and self.goal == other.goal

    def __ne__(self, other):
        result = self.__eq__(other)
        return result if result is NotImplemented else not result


class Objectives(object):
    """
    What a campaign is looking for, in the order it was asked for.

    A design is described by its cost vector -- one number per objective, all of
    them to be minimized. A design missing any of them was not measured, and a
    search cannot place it: it is reported as failed rather than guessed at.

    Args:
        objectives (list): what the search is looking for.
        constraints (Constraints): what a design has to be for it to count at
            all, empty when the campaign declared none. A constrained metric
            that was not measured leaves the design unplaceable the same way a
            missing objective does -- there is no telling whether it is
            feasible, so there is no honest place to put it.
    """

    def __init__(self, objectives=(), constraints=None):
        from odatix.dse.constraints import Constraints

        self.objectives = list(objectives)
        self.constraints = constraints if constraints is not None else Constraints()

    @classmethod
    def from_list(cls, declared, constraints=None):
        """
        The objectives a settings file declares::

            objectives:
              - metric: Fmax
                goal: max
              - metric: LUT_count
                goal: min

        A plain string is read as a metric to minimize, which is what most of
        them are.

        Args:
            declared (list): the objectives, as written.
            constraints (Constraints): the bounds declared next to them (see
                :mod:`odatix.dse.constraints`).
        """
        objectives = []
        for entry in (declared or []):
            if isinstance(entry, str):
                objectives.append(Objective(entry))
            elif isinstance(entry, dict):
                if len(entry) == 1 and "metric" not in entry:
                    # "- LUT_count: min", which reads well enough to accept.
                    metric, goal = list(entry.items())[0]
                    objectives.append(Objective(metric, goal))
                else:
                    objectives.append(Objective(entry.get("metric", ""), entry.get("goal", MINIMIZE)))
        return cls(objectives, constraints)

    @property
    def metrics(self):
        return [objective.metric for objective in self.objectives]

    @property
    def measured_metrics(self):
        """Every metric a design has to produce a number for: objectives and bounds."""
        return self.metrics + [
            metric for metric in self.constraints.metrics if metric not in self.metrics
        ]

    def costs(self, metrics):
        """
        The cost vector of a set of measurements, or None when one of the
        objectives -- or one of the constrained metrics -- was not measured.
        """
        violation = self.constraints.violation(metrics)
        if violation is None:
            return None
        vector = []
        for objective in self.objectives:
            value = (metrics or {}).get(objective.metric)
            if value is None or isinstance(value, bool):
                return None
            try:
                vector.append(objective.cost_of(value))
            except (TypeError, ValueError):
                return None
        return Costs(vector, violation)

    def describe(self, costs):
        """The cost vector read back as the numbers a user asked for."""
        return dict(
            (objective.metric, -cost if objective.maximized else cost)
            for objective, cost in zip(self.objectives, costs or ())
        )

    def feasible(self, costs):
        """Whether a cost vector met every constraint the campaign declared."""
        return costs is not None and not violation_of(costs)

    def to_list(self):
        return [objective.to_dict() for objective in self.objectives]

    def __len__(self):
        return len(self.objectives)

    def __iter__(self):
        return iter(self.objectives)

    def __getitem__(self, index):
        return self.objectives[index]

    def __repr__(self):
        return "<Objectives {0}>".format(", ".join(repr(o) for o in self.objectives))


######################################
# Dominance
######################################

def dominates(left, right):
    """
    Whether a cost vector is better than another: no worse anywhere, better
    somewhere.

    With a single objective this is plain comparison. With several it is what
    keeps a search from having to be told how many LUTs a megahertz is worth.

    Constraints come first, when there are any. A design that meets them beats
    one that does not however good its numbers are -- a design that misses the
    timing is not a trade-off, it is a design that does not work -- and between
    two that both miss them, the one closer to meeting them wins. That keeps the
    infeasible ones ranked instead of merely thrown away, which is what points
    the search towards the part of the space that works when it has not found it
    yet (see :mod:`odatix.dse.constraints`).
    """
    if left is None or right is None:
        return False
    left_violation, right_violation = violation_of(left), violation_of(right)
    if left_violation != right_violation:
        return left_violation < right_violation
    # Both meet the constraints, or both miss them by exactly as much: the
    # objectives are what is left to tell them apart.
    better_somewhere = False
    for a, b in zip(left, right):
        if a > b:
            return False
        if a < b:
            better_somewhere = True
    return better_somewhere


def pareto_front(vectors):
    """
    The indices of the vectors nothing dominates, in the order they came in.

    This is the answer of a campaign: the designs that are worth looking at,
    every one of them the best there is at some trade-off.
    """
    front = []
    for index, vector in enumerate(vectors):
        if vector is None:
            continue
        if not any(dominates(other, vector) for other in vectors if other is not None):
            front.append(index)
    return front


def non_dominated_sort(vectors):
    """
    The vectors sorted into fronts: the ones nothing dominates, then the ones
    only those dominate, and so on.

    This is how a search ranks designs it cannot otherwise compare -- the front
    a design sits in is how far it is from the best trade-offs found so far.

    Returns:
        list: fronts, each a list of indices into ``vectors``. Vectors that are
        None (a design that could not be measured) are left out of every front.
    """
    indices = [index for index, vector in enumerate(vectors) if vector is not None]
    remaining = list(indices)
    fronts = []
    while remaining:
        front = [
            index for index in remaining
            if not any(dominates(vectors[other], vectors[index]) for other in remaining)
        ]
        if not front:
            # Cannot happen with a well-formed dominance relation, but a front
            # that comes back empty would loop forever.
            fronts.append(remaining)
            break
        fronts.append(front)
        remaining = [index for index in remaining if index not in set(front)]
    return fronts


def crowding_distances(vectors):
    """
    How much room each vector has around it, along the front it belongs to.

    Ranking by front alone leaves a search free to crowd into one corner of the
    trade-off curve. Preferring the designs whose neighbours are far away is
    what keeps the front spread out, so what comes back covers the range of
    trade-offs instead of one end of it.

    Returns:
        list: one distance per vector, infinite for the extremes of each
        objective -- they are the ends of the front and are always kept.
    """
    count = len(vectors)
    distances = [0.0] * count
    if count == 0:
        return distances
    if count <= 2:
        return [float("inf")] * count

    for axis in range(len(vectors[0])):
        order = sorted(range(count), key=lambda index: vectors[index][axis])
        lowest = vectors[order[0]][axis]
        highest = vectors[order[-1]][axis]
        distances[order[0]] = float("inf")
        distances[order[-1]] = float("inf")
        if highest == lowest:
            # Every design agrees on this objective: it says nothing about how
            # crowded they are.
            continue
        span = highest - lowest
        for rank in range(1, count - 1):
            index = order[rank]
            if distances[index] == float("inf"):
                continue
            distances[index] += (vectors[order[rank + 1]][axis] - vectors[order[rank - 1]][axis]) / span
    return distances


######################################
# How good a front is
######################################

def hypervolume(vectors, reference):
    """
    How much of the space a front covers, between it and a reference point.

    Counting the designs on a front says almost nothing about whether a search
    is getting anywhere: a batch may add three designs that barely improve on
    what was already there, or replace two of them with one that is better on
    every objective at once. What does say it is the volume the front dominates
    -- the region of trade-offs a user is now guaranteed to be able to reach --
    which grows only when the answer actually got better.

    Args:
        vectors (list): cost vectors, all of them to be minimized. Ones that are
            None, or that are worse than the reference on any objective,
            contribute nothing.
        reference (tuple): the corner the volume is measured against, worse than
            every vector on every objective.

    Returns:
        float: the volume, zero when nothing is inside the reference.
    """
    points = [
        tuple(vector) for vector in vectors
        if vector is not None and all(value < bound for value, bound in zip(vector, reference))
    ]
    return _hypervolume(points, tuple(reference))


def _hypervolume(points, reference):
    """
    The volume of the union of the boxes between each point and the reference.

    Sliced along the last objective: between two consecutive values of it, the
    region covered is the union of the boxes of the points at or below the
    lower one, taken in one dimension less. Fronts hold tens of designs and a
    handful of objectives, so slicing is far below the cost of the synthesis
    that produced any single point.
    """
    if not points:
        return 0.0
    if len(reference) == 1:
        return reference[0] - min(point[0] for point in points)

    total = 0.0
    order = sorted(points, key=lambda point: point[-1])
    for position, point in enumerate(order):
        upper = order[position + 1][-1] if position + 1 < len(order) else reference[-1]
        depth = upper - point[-1]
        if depth <= 0:
            # Several points at the same depth: the slice is empty, and they are
            # all taken into account by the one that closes it.
            continue
        below = [other[:-1] for other in order[:position + 1]]
        total += depth * _hypervolume(below, reference[:-1])
    return total


def _least_violation(vectors):
    """
    How far the closest design of a front is from meeting the constraints, zero
    once one of them does -- and zero for a campaign that declared none.
    """
    amounts = [violation_of(vector) for vector in vectors if vector is not None]
    return min(amounts) if amounts else 0.0


class Progress(object):
    """
    Whether the answer is still getting better.

    A search is stopped early by "patience": so many batches in a row that
    taught it nothing. What counts as nothing is the question, and asking
    whether the designs on the front changed is a poor answer to it: it says yes
    to a design a hair better on one objective just as readily as to one that
    opened up a whole region of trade-offs, so an exploration either goes on for
    hours over rounding or stops in the middle of getting somewhere.

    What is compared here is the hypervolume of the front instead: a batch made
    progress when it grew it by more than a tolerance. The reference point is
    taken from the worst of everything measured so far and only ever moves
    outwards, and both fronts are measured against the current one, so a batch
    that widens the reference is not mistaken for one that improved the answer.

    Args:
        tolerance (float): the share of the volume a batch has to add for it to
            count. Zero means any growth at all does.
    """

    def __init__(self, tolerance=0.0):
        self.tolerance = max(0.0, float(tolerance or 0.0))
        self.worst = None
        self.best = None
        #: The volume of the front the last time it was measured, for a report.
        self.value = 0.0

    def observe(self, vectors):
        """Widen what is known of the range of each objective."""
        for vector in vectors:
            if vector is None:
                continue
            if self.worst is None:
                self.worst = list(vector)
                self.best = list(vector)
                continue
            for axis, value in enumerate(vector):
                self.worst[axis] = max(self.worst[axis], value)
                self.best[axis] = min(self.best[axis], value)
        return self

    @property
    def reference(self):
        """
        The corner the volume is measured against: the worst of every objective,
        pushed out far enough that a single design still covers something.

        Returns None when nothing has been measured yet.
        """
        if self.worst is None:
            return None
        return tuple(
            worst + (0.1 * (worst - best) or 0.1 * abs(worst) or 1.0)
            for worst, best in zip(self.worst, self.best)
        )

    def of(self, vectors):
        """The volume a front covers, as this tracker measures it."""
        reference = self.reference
        return 0.0 if reference is None else hypervolume(vectors, reference)

    def improved(self, before, after):
        """
        Whether a batch grew the front's hypervolume by more than the tolerance.

        A front that has not reached the feasible part of the space yet is a
        separate question, and the volume answers it badly: a batch that finally
        meets the constraints replaces a front of infeasible designs with a
        smaller one, and would be read as having achieved nothing. So while any
        constraint is still broken, getting closer to meeting it *is* the
        progress being measured, and the volume only takes over once the front
        is feasible.

        Args:
            before (list): the cost vectors of the front before the batch.
            after (list): the cost vectors of it afterwards.
        """
        was_missing = _least_violation(before)
        is_missing = _least_violation(after)
        if was_missing or is_missing:
            self.value = 0.0
            return is_missing < was_missing

        self.observe(list(before) + list(after))
        previous = self.of(before)
        self.value = self.of(after)
        return self.value > previous * (1.0 + self.tolerance) + (0.0 if previous else 1e-12)

    def __repr__(self):
        return "<Progress {0}>".format(self.value)
