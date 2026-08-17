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
What a design has to be for it to count at all.

An objective is something to get as much of as possible, and nothing is ever
enough of it. A constraint is the opposite: a design either meets it or it does
not, and meeting it twice over is worth nothing. "The slack has to be positive"
is not an objective -- a design with 4 ns of slack is not the answer to a search
that could have run it twice as fast -- it is the line between the designs that
work and the ones that do not::

    constraints:
      - metric: Slack
        min: 0
      - metric: LUT_count
        max: 20000

Writing that as an objective instead does two wrong things at once: it spends
the budget pushing the slack up long after it stopped mattering, and it leaves
designs that do not meet the timing on the answer, since a design that fails by
a nanosecond is still the smallest one anybody found.

*How* the search uses this is the part worth explaining. Dropping the designs
that violate a constraint is the obvious thing and the wrong one: at the start
of a search there are often only those, and a search told nothing but "all of
these are equally bad" has no idea which way to go. So an infeasible design is
kept and ranked, by how far it is from being feasible -- what NSGA-II calls
constrained domination, and what :func:`~odatix.dse.objectives.dominates`
implements:

- a feasible design always beats an infeasible one, whatever the objectives say;
- between two infeasible designs, the one closer to feasibility wins;
- between two feasible designs, the constraints have nothing to say and it is
  the objectives that decide, exactly as before.

The front a campaign reports is therefore made of feasible designs as soon as it
has found any, and of the least infeasible ones while it has not -- which is the
honest answer to "nothing here meets your constraints, here is the closest".
"""

__all__ = ["Constraint", "Constraints"]


class Constraint(object):
    """
    One bound a design has to be inside of.

    Args:
        metric (str): what is read off the results of an evaluation, the same
            way an objective is.
        minimum (float): the least it may be, None for no lower bound.
        maximum (float): the most it may be, None for no upper bound.

    Raises:
        ValueError: neither bound was given -- a constraint that constrains
            nothing is a line the user meant to write and did not.
    """

    __slots__ = ("metric", "minimum", "maximum")

    def __init__(self, metric, minimum=None, maximum=None):
        self.metric = str(metric)
        self.minimum = None if minimum is None else float(minimum)
        self.maximum = None if maximum is None else float(maximum)
        if self.minimum is None and self.maximum is None:
            raise ValueError(
                "The constraint on \"{0}\" says nothing: give it a \"min\", a \"max\", or both.".format(metric)
            )
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError(
                "The constraint on \"{0}\" cannot be met: its \"min\" ({1}) is above its \"max\" ({2}).".format(
                    metric, self.minimum, self.maximum
                )
            )

    def violation_of(self, value):
        """
        How far outside the bounds a value is, as a share of what the bound is
        worth -- zero when it is inside them.

        Several constraints are added up into one number, so how far outside a
        LUT count is has to be comparable to how far outside a slack is. A
        violation is therefore divided by the magnitude of the bound it broke:
        1000 LUTs over a bound of 20000 counts as 0.05, the same as 0.5 ns of
        negative slack against a bound of 10 ns. A bound of zero -- "the slack
        has to be positive", the ordinary case -- has no magnitude to divide by,
        and the violation is the raw distance.
        """
        try:
            value = float(value)
        except (TypeError, ValueError):
            return None
        if self.minimum is not None and value < self.minimum:
            return (self.minimum - value) / (abs(self.minimum) or 1.0)
        if self.maximum is not None and value > self.maximum:
            return (value - self.maximum) / (abs(self.maximum) or 1.0)
        return 0.0

    def describe(self):
        """The bound as a user wrote it, for a message."""
        if self.minimum is not None and self.maximum is not None:
            return "{0} between {1} and {2}".format(self.metric, self.minimum, self.maximum)
        if self.minimum is not None:
            return "{0} >= {1}".format(self.metric, self.minimum)
        return "{0} <= {1}".format(self.metric, self.maximum)

    def to_dict(self):
        bounds = {"metric": self.metric}
        if self.minimum is not None:
            bounds["min"] = self.minimum
        if self.maximum is not None:
            bounds["max"] = self.maximum
        return bounds

    def __repr__(self):
        return "<Constraint {0}>".format(self.describe())

    def __eq__(self, other):
        if not isinstance(other, Constraint):
            return NotImplemented
        return (self.metric, self.minimum, self.maximum) == (other.metric, other.minimum, other.maximum)

    def __ne__(self, other):
        result = self.__eq__(other)
        return result if result is NotImplemented else not result


class Constraints(object):
    """
    Every bound a campaign was given, in the order it was given them.

    An empty one is the ordinary case, and the one every campaign written before
    constraints existed has: it declares nothing infeasible, so the search
    behaves exactly as it did.
    """

    def __init__(self, constraints=()):
        self.constraints = list(constraints)

    @classmethod
    def from_list(cls, declared):
        """
        The constraints a settings file declares::

            constraints:
              - metric: Slack
                min: 0
              - metric: LUT_count
                max: 20000

        A single entry may carry both bounds, which is how a range is written.
        The keys "minimum"/"maximum" and "at_least"/"at_most" are read too: they
        are what a user writes when they do not have the file in front of them.

        Raises:
            ValueError: an entry names no metric, or no bound.
        """
        constraints = []
        for entry in (declared or []):
            if not isinstance(entry, dict):
                raise ValueError(
                    "A constraint is a metric and a bound, not \"{0}\": write \"- metric: {0}\" "
                    "with a \"min\" or a \"max\" under it.".format(entry)
                )
            metric = entry.get("metric", "")
            minimum = _first(entry, ("min", "minimum", "at_least"))
            maximum = _first(entry, ("max", "maximum", "at_most"))
            if not str(metric).strip():
                raise ValueError("A constraint names no metric: {0}.".format(entry))
            constraints.append(Constraint(metric, minimum, maximum))
        return cls(constraints)

    @property
    def metrics(self):
        return [constraint.metric for constraint in self.constraints]

    def violation(self, metrics):
        """
        How far a set of measurements is from meeting every constraint: zero
        when it meets them all, and the sum of what it is missing when it does
        not.

        Returns:
            float: the total violation, or None when a constrained metric was
            not measured -- the design cannot be told feasible or not, which
            makes it no more usable than one that produced no objective.
        """
        total = 0.0
        for constraint in self.constraints:
            value = (metrics or {}).get(constraint.metric)
            if value is None or isinstance(value, bool):
                return None
            amount = constraint.violation_of(value)
            if amount is None:
                return None
            total += amount
        return total

    def unmet(self, metrics):
        """The constraints a set of measurements breaks, described, for a report."""
        broken = []
        for constraint in self.constraints:
            value = (metrics or {}).get(constraint.metric)
            if value is None or isinstance(value, bool):
                continue
            if constraint.violation_of(value):
                broken.append("{0} (measured {1})".format(constraint.describe(), value))
        return broken

    def missing(self, metrics):
        """The constrained metrics a set of measurements has no number for."""
        return [
            constraint.metric for constraint in self.constraints
            if (metrics or {}).get(constraint.metric) is None
            or isinstance((metrics or {}).get(constraint.metric), bool)
        ]

    def to_list(self):
        return [constraint.to_dict() for constraint in self.constraints]

    def __len__(self):
        return len(self.constraints)

    def __iter__(self):
        return iter(self.constraints)

    def __getitem__(self, index):
        return self.constraints[index]

    def __repr__(self):
        return "<Constraints {0}>".format(", ".join(c.describe() for c in self.constraints))


def _first(entry, keys):
    """The first of several spellings of a bound that the entry actually uses."""
    for key in keys:
        if entry.get(key) is not None:
            return entry[key]
    return None
