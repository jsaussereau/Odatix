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
What an exploration is asked to do.

The architectures do not change: an exploration searches the parameters they
already describe, with the rules they already declare. What is written here is
only what a sweep never had to say -- what makes a design good, how long to
look for it, and how to look.

    # odatix_userconfig/dse_settings.yml

    run: fmax_synthesis
    tool: vivado
    # A list instead of a name is what the search chooses between:
    #   target:
    #     - xc7a100t-csg324-1
    #     - xc7k70t-fbg676-2

    objectives:
      - metric: frequency
        goal: max
      - metric: LUT_count
        goal: min

    constraints:
      - metric: Slack
        min: 0

    search:
      strategy: genetic
      budget: 60
      batch: 8

    architectures:
      - Example_ALU_sv
"""

from odatix.workspace.jobs import JobSettings
from odatix.workspace.settings import Setting, Settings

__all__ = ["FrequencyRangeSettings", "FrequencySettings", "SearchSettings", "DseSettings"]


class FrequencyRangeSettings(Settings):
    """The frequencies an exploration is allowed to choose from, in MHz."""

    start = Setting(50, type="optional_int", key="from", doc="Lowest frequency the search may choose, in MHz.")
    stop = Setting(500, type="optional_int", key="to", doc="Highest frequency the search may choose, in MHz.")
    step = Setting(10, type="optional_int", doc="Distance between two frequencies it may choose, in MHz.")

    def values(self):
        """The frequencies the range stands for, in order."""
        start, stop, step = self.start, self.stop, self.step
        if start is None or stop is None:
            return []
        step = int(step or 0) or 10
        start, stop = int(start), int(stop)
        if stop < start:
            start, stop = stop, start
        return list(range(start, stop + 1, abs(step)))


class FrequencySettings(Settings):
    """
    What "custom_freq_synthesis" synthesizes at, when a search runs it.

    A custom frequency synthesis is told the frequencies to run at, and that is
    a choice like any other: either it is made once and every design is run at
    the same one (or the same few), or it is left to the search, which then
    treats the frequency as one more axis of the space -- the only one that is
    not a parameter of the design.
    """

    explore = Setting(
        False, type="bool", style="yesno",
        comment="if yes, the frequency is searched like a parameter, within the range below",
        doc="Whether the search chooses the frequency of each design itself.",
    )
    frequencies = Setting(
        factory=list, type="int_list", key="list", style="flow",
        comment="if 'explore' is no, every design is synthesized at each of those",
        doc="Frequencies every design is synthesized at, in MHz.",
    )
    range = Setting(
        type=FrequencyRangeSettings,
        comment="if 'explore' is yes, the frequencies the search may choose from",
        doc="Frequencies the search may choose from.",
    )

    def values(self):
        """
        The frequencies this describes, in MHz: what the search may choose from
        when it explores them, what every design is run at when it does not.

        Returns:
            list: the frequencies, empty when nothing was said -- in which case
            whatever "odatix synth" is already set to run at is what runs.
        """
        chosen = [int(value) for value in (self.frequencies or [])]
        if not self.explore:
            return chosen
        return chosen if chosen else self.range.values()


class SearchSettings(Settings):
    """
    How the search moves, and when it stops.

    The budget is what an exploration is really about: the space is larger than
    anyone can synthesize, so the question is not which designs to leave out but
    how many hours to spend. Everything else has a default that works.
    """

    strategy = Setting(
        "genetic", type="str",
        comment="genetic, random or exhaustive - overridden by --strategy",
        doc="How the next designs to evaluate are chosen.",
    )
    budget = Setting(
        50, type="int",
        comment="how many designs are evaluated at most, per architecture - overridden by --budget",
        doc="How many designs the search evaluates before it stops.",
    )
    batch = Setting(
        8, type="int",
        comment="how many designs are evaluated together, between two decisions",
        doc="How many designs are run at once.",
    )
    patience = Setting(
        0, type="int",
        comment="stop after this many batches that do not improve the front (0: never)",
        doc="How many batches without progress the search puts up with.",
    )
    improvement = Setting(
        0.0, type="any",
        comment="how much the front has to grow for a batch to count (0.02: 2%)",
        doc="The share of the front a batch has to add for it to count as progress.",
    )
    seed = Setting(
        None, type="optional_int",
        comment="empty: a different search every time",
        doc="What makes a search reproducible.",
    )
    mutation = Setting(
        None, type="any",
        comment="genetic only, empty: one parameter per design on average",
        doc="How often a parameter is changed when a design is derived from another.",
    )
    tournament = Setting(
        2, type="int",
        comment="genetic only, how many designs a parent is picked out of",
        doc="How greedy the search is when it chooses what to look around.",
    )
    population = Setting(
        None, type="optional_int",
        comment="genetic only, empty: four batches' worth",
        doc="How many designs the search keeps to look around.",
    )


class DseSettings(JobSettings):
    """Settings of an "odatix dse" run."""

    selection_key = "architectures"

    write_all_settings = True

    # An exploration commits to hours of synthesis out of a few lines of
    # settings: it asks before it starts, like every other run does.
    ask_continue = Setting(
        True, type="bool", style="yesno", section=" prompt 'Continue? (Y/n)' after settings checks",
        comment="overridden by -y / --noask",
        doc="Whether the exploration stops for a confirmation once it knows what it will do.",
    )

    run = Setting(
        "fmax_synthesis", type="str", section=" what evaluating one design runs",
        comment="fmax_synthesis, custom_freq_synthesis or workflow - overridden by --run",
        doc="The Odatix command each evaluation runs.",
    )
    tool = Setting(
        "", type="any", comment="a tool, or a list of tools the search chooses between - overridden by -t / --tool",
        doc="EDA tool the evaluations run with, or the tools the search chooses between.",
    )
    flow = Setting(
        "", type="any", comment="a flow, or a list of them - empty: the default flow of each tool",
        doc="Flow of that tool, or the flows the search chooses between.",
    )
    target = Setting(
        "", type="any", comment="a target, or a list of them - empty: every target the tool enables",
        doc="Synthesis target the evaluations run on, or the targets the search chooses between.",
    )
    simulations = Setting(
        factory=list, type="str_list",
        section=" simulations every design is run through, before it is measured",
        comment="empty: none - the derived metrics then read what was simulated before",
        doc="Simulations run on every design the search evaluates.",
    )
    frequencies = Setting(
        type=FrequencySettings, section=" at what frequencies (custom_freq_synthesis only, in MHz)",
        doc="What a custom frequency synthesis is run at, and whether the search chooses it.",
    )
    objectives = Setting(
        factory=list, type="any", section=" what makes a design better than another",
        comment=(
            "each one is a metric to \"min\" or to \"max\";"
            "\n a design is kept when nothing beats it on all of them at once"
        ),
        doc="What the search is looking for.",
    )
    constraints = Setting(
        factory=list, type="any", section=" what a design has to be for it to count at all",
        comment=(
            "each one is a metric with a \"min\", a \"max\", or both;"
            "\n a design that breaks one is beaten by every design that does not"
        ),
        doc="Bounds a design has to be inside of for it to be part of the answer.",
    )
    search = Setting(
        type=SearchSettings, section=" how the search looks for it",
        doc="How the next designs to evaluate are chosen, and when to stop.",
    )
    architectures = Setting(
        factory=list, type="any", section=" architectures to explore, one search each",
        doc="Architectures whose parameters are searched.",
    )

    ######################################
    # What it amounts to
    ######################################

    def objective_list(self):
        """
        What the search is looking for, and what it is allowed to look at (see
        :class:`~odatix.dse.objectives.Objectives` and
        :mod:`odatix.dse.constraints`).
        """
        from odatix.dse.objectives import Objectives

        return Objectives.from_list(self.objectives, self.constraint_list())

    def constraint_list(self):
        """The constraints, read (see :class:`~odatix.dse.constraints.Constraints`)."""
        from odatix.dse.constraints import Constraints

        return Constraints.from_list(self.constraints)

    def simulation_names(self):
        """
        The simulations every design is run through, as plain names.

        Empty is the ordinary case: an exploration searching only what a
        synthesis measures has nothing to simulate. It is also what a workspace
        that simulated its designs beforehand writes -- the numbers are already
        in the results, and a derived metric brings them onto the records the
        search reads without anything having to be run again.
        """
        names = self.simulations
        if isinstance(names, str):
            names = [names]
        return [str(name).strip() for name in (names or []) if str(name).strip()]

    def uses_frequencies(self):
        """
        Whether the frequency is something this exploration says anything about.

        Only a custom frequency synthesis is *told* a frequency: an fmax
        synthesis looks for one, and a workflow is whatever it is. Frequency
        settings written next to any other command are left alone.
        """
        return self.run == "custom_freq_synthesis"

    def explores_frequency(self):
        """Whether the frequency is an axis of the search."""
        return bool(self.uses_frequencies() and self.frequencies.explore
                    and self.frequency_values())

    def frequency_values(self):
        """
        The frequencies the exploration works with, in MHz.

        Empty when it has nothing to say about them: the batches then run at
        whatever "odatix synth" is already set to.
        """
        return self.frequencies.values() if self.uses_frequencies() else []

    ######################################
    # What runs the designs
    ######################################

    @staticmethod
    def _names(value):
        """A setting that is either one name or several, as a list of names."""
        if value is None:
            return []
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, (list, tuple)):
            value = [value]
        return [str(name).strip() for name in value if str(name).strip()]

    def tool_names(self):
        """The eda tools the evaluations run with."""
        return self._names(self.tool)

    def flow_names(self):
        """The flows they run, empty for the default flow of each tool."""
        return self._names(self.flow)

    def target_names(self):
        """The targets they run on, empty for every target each tool enables."""
        return self._names(self.target)

    def toolchains(self, workspace):
        """
        Every (tool, flow, target) an evaluation may run with, checked against
        what the workspace holds (see
        :func:`~odatix.dse.space.toolchains_for`).
        """
        from odatix.dse.space import toolchains_for

        return toolchains_for(
            workspace, self.tool_names(), self.flow_names(), self.target_names()
        )

    def explores_toolchain(self, workspace):
        """Whether what runs a design is an axis of the search."""
        return len(self.toolchains(workspace)) > 1

    def architecture_entries(self):
        """The architectures to search, as written."""
        names = self.architectures
        if isinstance(names, str):
            names = [names]
        return [str(name).strip() for name in (names or []) if str(name).strip()]

    def architecture_selections(self):
        """
        What each entry selects: the architecture, and what it says about its
        parameter domains (see
        :class:`~odatix.dse.space.DomainSelection`).
        """
        from odatix.dse.space import DomainSelection

        return [DomainSelection.parse(entry) for entry in self.architecture_entries()]

    def architecture_names(self):
        """The architectures to search, as plain names."""
        return [selection.entry for selection in self.architecture_selections()]
