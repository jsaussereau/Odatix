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
Searching a design space instead of sweeping it.

Nothing here runs a synthesis: an evaluation is replaced by a formula, which is
what lets the search itself be tested -- whether it finds the good designs, and
whether what it proposes is something Odatix could actually have run.
"""

import os
import random
import re
import textwrap

import numpy as np
import pytest

from odatix.dse.archive import Archive
from odatix.dse.bayesian import BayesianSearch
from odatix.dse.campaign import Campaign, CampaignError
from odatix.dse.constraints import Constraint, Constraints
from odatix.dse.evaluation import Evaluation, Evaluator
from odatix.dse.gp import GaussianProcess
from odatix.dse.objectives import (
    Costs,
    Objective,
    Objectives,
    Progress,
    crowding_distances,
    dominates,
    hypervolume,
    hypervolume_improvement,
    non_dominated_sort,
    pareto_front,
)
from odatix.dse.campaigns import RunSettings
from odatix.dse.settings import CampaignSettings, DseSettings
from odatix.dse.space import (
    ArchitectureSpace,
    DomainSelection,
    EmptySpaceError,
    UnknownConfigurationError,
)
from odatix.dse.strategies import ExhaustiveSearch, GeneticSearch, RandomSearch, strategy_for
from odatix.workspace.space import ParameterSpace


######################################
# What makes a design better
######################################

class TestObjectives:
    def test_a_goal_says_which_way_is_better(self):
        # Everything downstream minimizes, whichever way the user asked.
        assert Objective("area", "min").cost_of(10) == 10
        assert Objective("Fmax", "max").cost_of(10) == -10
        with pytest.raises(ValueError):
            Objective("area", "sideways")

    def test_the_objectives_are_read_the_way_they_are_written(self):
        declared = [
            {"metric": "Fmax", "goal": "max"},
            {"LUT_count": "min"},
            "Total_Power",
        ]
        objectives = Objectives.from_list(declared)
        assert objectives.metrics == ["Fmax", "LUT_count", "Total_Power"]
        assert [objective.goal for objective in objectives] == ["max", "min", "min"]

    def test_a_design_missing_a_measurement_has_no_cost(self):
        # Guessing at it would place a design the run never measured.
        objectives = Objectives.from_list([{"metric": "Fmax", "goal": "max"}, "LUT_count"])
        assert objectives.costs({"Fmax": 100, "LUT_count": 20}) == (-100, 20)
        assert objectives.costs({"Fmax": 100}) is None
        assert objectives.costs({"Fmax": 100, "LUT_count": None}) is None

    def test_better_means_better_everywhere_and_worse_nowhere(self):
        assert dominates((1, 1), (2, 2))
        assert dominates((1, 2), (1, 3))
        # A trade-off: smaller one way, larger the other. Neither is the answer
        # on its own, which is the whole reason a front is what comes back.
        assert not dominates((1, 3), (3, 1))
        assert not dominates((1, 1), (1, 1))

    def test_the_front_is_what_nothing_beats(self):
        # (2, 6) is beaten by (1, 5) on both counts; (4, 4) by (3, 3).
        vectors = [(1, 5), (5, 1), (3, 3), (4, 4), (2, 6)]
        assert pareto_front(vectors) == [0, 1, 2]
        # And the ones only the front beats come next.
        fronts = non_dominated_sort(vectors)
        assert fronts[0] == [0, 1, 2]
        assert fronts[1] == [3, 4]

    def test_the_ends_of_a_front_are_always_kept(self):
        # Crowding is what keeps a search spread along the trade-off curve
        # instead of piling into one corner of it.
        distances = crowding_distances([(0.0, 10.0), (5.0, 5.0), (10.0, 0.0)])
        assert distances[0] == float("inf")
        assert distances[2] == float("inf")
        assert distances[1] < float("inf")


class TestConstraints:
    def test_a_constraint_is_a_bound_and_says_so_when_it_is_not(self):
        assert Constraint("Slack", minimum=0).describe() == "Slack >= 0.0"
        assert Constraint("LUT_count", maximum=20000).describe() == "LUT_count <= 20000.0"
        with pytest.raises(ValueError):
            # A line the user meant to write and did not.
            Constraint("Slack")
        with pytest.raises(ValueError):
            Constraint("Slack", minimum=5, maximum=1)
        with pytest.raises(ValueError):
            Constraints.from_list(["Slack"])

    def test_how_far_outside_a_bound_is_measured_against_the_bound(self):
        # Several constraints are added up, so a LUT count and a slack have to
        # end up on the same scale.
        assert Constraint("LUT_count", maximum=20000).violation_of(21000) == pytest.approx(0.05)
        assert Constraint("LUT_count", maximum=20000).violation_of(19000) == 0.0
        # A bound of zero has no magnitude to divide by: the raw distance.
        assert Constraint("Slack", minimum=0).violation_of(-0.5) == pytest.approx(0.5)

    def test_a_design_that_meets_them_beats_one_that_does_not(self):
        constraints = Constraints.from_list([{"metric": "Slack", "min": 0}])
        objectives = Objectives.from_list([{"metric": "Fmax", "goal": "max"}, "area"], constraints)
        fails = objectives.costs({"Fmax": 300, "area": 10, "Slack": -0.5})
        works = objectives.costs({"Fmax": 100, "area": 90, "Slack": 0.2})
        # Faster *and* smaller, and still not the answer: it does not work.
        assert dominates(works, fails)
        assert not dominates(fails, works)
        assert pareto_front([fails, works]) == [1]

    def test_the_closest_to_feasible_wins_while_none_are(self):
        # Dropping the infeasible ones would leave a search with nothing to
        # steer by, which is exactly the state it starts in.
        constraints = Constraints.from_list([{"metric": "Slack", "min": 0}])
        objectives = Objectives.from_list(["area"], constraints)
        far = objectives.costs({"area": 1, "Slack": -1.0})
        near = objectives.costs({"area": 90, "Slack": -0.1})
        assert dominates(near, far)
        assert pareto_front([far, near]) == [1]

    def test_a_constrained_metric_nobody_measured_leaves_a_design_unplaceable(self):
        objectives = Objectives.from_list(
            ["area"], Constraints.from_list([{"metric": "Slack", "min": 0}])
        )
        assert objectives.costs({"area": 10}) is None
        assert objectives.measured_metrics == ["area", "Slack"]

    def test_getting_closer_to_feasible_counts_as_progress(self):
        # A batch that finally meets the constraints replaces a front with a
        # smaller one: measured by volume alone it would look like nothing.
        objectives = Objectives.from_list(
            [{"metric": "Fmax", "goal": "max"}], Constraints.from_list([{"metric": "Slack", "min": 0}])
        )
        fails = objectives.costs({"Fmax": 300, "Slack": -0.5})
        closer = objectives.costs({"Fmax": 280, "Slack": -0.1})
        works = objectives.costs({"Fmax": 100, "Slack": 0.1})
        assert Progress().improved([fails], [closer])
        assert Progress().improved([fails], [works])
        assert not Progress().improved([closer], [fails])

    def test_a_campaign_with_no_constraint_is_left_alone(self):
        objectives = Objectives.from_list(["area"])
        assert objectives.costs({"area": 10}) == (10,)
        assert objectives.feasible(objectives.costs({"area": 10}))


class TestHypervolume:
    def test_how_far_a_front_reaches_is_the_area_behind_it(self):
        # One point, minimizing both: the box between it and the reference.
        assert hypervolume([(1.0, 1.0)], (3.0, 3.0)) == pytest.approx(4.0)
        # Two: the union of two boxes, counted once where they overlap.
        assert hypervolume([(1.0, 2.0), (2.0, 1.0)], (3.0, 3.0)) == pytest.approx(3.0)
        # A dominated design adds nothing, which is the whole point.
        assert hypervolume([(1.0, 2.0), (2.0, 1.0), (2.0, 2.0)], (3.0, 3.0)) == pytest.approx(3.0)
        # Neither does one outside the reference.
        assert hypervolume([(1.0, 1.0), (9.0, 9.0)], (3.0, 3.0)) == pytest.approx(4.0)

    def test_it_works_with_more_than_two_objectives(self):
        assert hypervolume([(1.0, 1.0, 1.0)], (2.0, 3.0, 4.0)) == pytest.approx(6.0)
        assert hypervolume(
            [(0.0, 1.0, 1.0), (1.0, 0.0, 1.0)], (2.0, 2.0, 2.0)
        ) == pytest.approx(3.0)

    def test_what_one_point_adds_is_what_measuring_twice_would_have_said(self):
        # The shortcut the Bayesian acquisition scores candidates with: it has
        # to be the difference between the two volumes, not an approximation
        # of it, or the search would be ranking candidates by rounding error.
        rng = random.Random(20240517)
        for axes in range(1, 6):
            for _ in range(40):
                reference = tuple(1.0 + 0.5 * rng.random() for _ in range(axes))
                front = [
                    tuple(1.4 * rng.random() for _ in range(axes))
                    for _ in range(rng.randrange(0, 10))
                ]
                point = tuple(1.4 * rng.random() for _ in range(axes))
                assert hypervolume_improvement(point, front, reference) == pytest.approx(
                    hypervolume(front + [point], reference) - hypervolume(front, reference)
                )

    def test_a_point_adds_nothing_when_it_is_already_covered(self):
        # Dominated by the front, and outside the reference: zero either way.
        assert hypervolume_improvement((2.0, 2.0), [(1.0, 1.0)], (3.0, 3.0)) == 0.0
        assert hypervolume_improvement((9.0, 9.0), [(1.0, 1.0)], (3.0, 3.0)) == 0.0
        # An empty front leaves it the whole of its own box.
        assert hypervolume_improvement((1.0, 1.0), [], (3.0, 3.0)) == pytest.approx(4.0)

    def test_a_batch_counts_when_the_front_reaches_further(self):
        progress = Progress()
        # From nothing to something.
        assert progress.improved([], [(1.0, 1.0)])
        # A design that is exactly as good as one already found teaches nothing:
        # it is another way of building a trade-off that was already reachable.
        assert not progress.improved([(1.0, 1.0)], [(1.0, 1.0)])
        assert not progress.improved([(0.0, 2.0), (2.0, 0.0)], [(0.0, 2.0), (2.0, 0.0)])
        # Ground actually gained does.
        assert progress.improved([(1.0, 1.0)], [(1.0, 1.0), (0.0, 2.0)])

    def test_a_tolerance_is_how_much_is_worth_another_batch(self):
        # A front 1% wider is not worth an hour of synthesis when 5% was asked.
        patient = Progress(tolerance=0.05)
        patient.observe([(0.0, 0.0), (10.0, 10.0)])
        assert not patient.improved([(1.0, 1.0)], [(0.99, 1.0)])
        assert patient.improved([(1.0, 1.0)], [(0.5, 0.5)])


######################################
# What there is to choose from
######################################

def write_architecture(root, name, settings, domains=None):
    """An architecture directory, as a workspace holds it."""
    path = os.path.join(str(root), name)
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, "_settings.yml"), "w") as f:
        f.write(textwrap.dedent(settings))
    for domain, content in (domains or {}).items():
        domain_path = os.path.join(path, domain)
        os.makedirs(domain_path, exist_ok=True)
        with open(os.path.join(domain_path, "_settings.yml"), "w") as f:
            f.write(textwrap.dedent(content))
    return path


PARAMETERIZED = """\
    rtl_path: "rtl"
    top_level_file: "top.v"
    top_level_module: "top"
    clock_signal: "clk"
    use_parameters: Yes
    start_delimiter: "#("
    stop_delimiter: ")("
    param_target_file: "rtl/top.v"

    configurations:
      name: "${width}bits_${depth}deep"
      template: "parameter WIDTH = ${width}, DEPTH = ${depth};"

    variables:
      width:
        type: list
        settings:
          list: [8, 16, 32]
      depth:
        type: list
        settings:
          list: [2, 4]
"""

HLS = """\
    design_path: "src"
    top_level_file: "fir.v"
    top_level_module: "fir"
    clock_signal: "ap_clk"
    generate_rtl: Yes
    generate_command: "hls ${taps} ${ii}"
    use_parameters: No

    variables:
      taps:
        type: list
        settings:
          list: [8, 16, 32]
      ii:
        type: list
        settings:
          list: [1, 2]
"""


@pytest.fixture
def architecture(tmp_path):
    """An architecture whose parameters describe six designs."""
    from odatix.workspace import Workspace

    root = tmp_path / "odatix_userconfig" / "architectures"
    root.mkdir(parents=True)
    write_architecture(root, "Design", PARAMETERIZED)
    (tmp_path / "odatix.yml").write_text("arch_path: odatix_userconfig/architectures\n")
    workspace = Workspace(str(tmp_path))
    return workspace.architectures["Design"]


@pytest.fixture
def hls_architecture(tmp_path):
    """An architecture whose knobs are variables of its generation command."""
    from odatix.workspace import Workspace

    root = tmp_path / "odatix_userconfig" / "architectures"
    root.mkdir(parents=True)
    write_architecture(root, "Filter", HLS)
    (tmp_path / "odatix.yml").write_text("arch_path: odatix_userconfig/architectures\n")
    workspace = Workspace(str(tmp_path))
    return workspace.architectures["Filter"]


CORNERS = """\
    use_parameters: Yes
    start_delimiter: "// corner"
    stop_delimiter: "// end"
    param_target_file: "rtl/top.v"

    configurations:
      name: "${corner}"
      template: "corner = ${corner};"

    variables:
      corner:
        type: list
        settings:
          list: [ss, tt, ff]
"""


@pytest.fixture
def multi_domain_architecture(tmp_path):
    """An architecture with a second parameter domain of its own."""
    from odatix.workspace import Workspace

    root = tmp_path / "odatix_userconfig" / "architectures"
    root.mkdir(parents=True)
    write_architecture(root, "Design", PARAMETERIZED, domains={"corner": CORNERS})
    (tmp_path / "odatix.yml").write_text("arch_path: odatix_userconfig/architectures\n")
    return Workspace(str(tmp_path)).architectures["Design"]


CONSTRAINED = PARAMETERIZED.replace(
    '      template: "parameter WIDTH = ${width}, DEPTH = ${depth};"',
    '      template: "parameter WIDTH = ${width}, DEPTH = ${depth};"\n'
    '      constraints:\n'
    '        - "${depth} * ${width} <= 64"',
)


@pytest.fixture
def constrained_architecture(tmp_path):
    """An architecture whose rules rule some combinations out."""
    from odatix.workspace import Workspace

    root = tmp_path / "odatix_userconfig" / "architectures"
    root.mkdir(parents=True)
    write_architecture(root, "Design", CONSTRAINED)
    (tmp_path / "odatix.yml").write_text("arch_path: odatix_userconfig/architectures\n")
    return Workspace(str(tmp_path)).architectures["Design"]


class TestConstrainedSpace:
    def test_a_rejected_combination_names_no_design(self, constrained_architecture):
        space = ArchitectureSpace(
            constrained_architecture, selection=DomainSelection.parse("Design")
        )
        # The axes are unchanged -- a constraint is not a value that went away --
        # so the size is what the cross product holds, and what it really holds
        # is what the genomes name.
        assert space.size() == 6
        designs = [space.design(genome) for genome in space.genomes()]
        named = sorted(
            design.configuration for design in designs if design is not None
        )
        assert named == ["16bits_2deep", "16bits_4deep", "32bits_2deep", "8bits_2deep", "8bits_4deep"]
        assert designs.count(None) == 1


class TestSelection:
    def test_naming_no_domain_searches_all_of_them(self, multi_domain_architecture):
        space = ArchitectureSpace(
            multi_domain_architecture, selection=DomainSelection.parse("Design")
        )
        assert space.size() == 6 * 3
        assert space.pinned == {}

    def test_naming_one_domain_leaves_the_others_out(self, multi_domain_architecture):
        # Naming a domain is saying which ones a design is made of, so one that
        # is not named is not part of it -- the same thing that entry would run
        # as a sweep.
        space = ArchitectureSpace(
            multi_domain_architecture, selection=DomainSelection.parse("Design/*+corner/tt")
        )
        assert space.size() == 6
        space = ArchitectureSpace(
            multi_domain_architecture, selection=DomainSelection.parse("Design/8bits_2deep+corner/*")
        )
        assert space.size() == 3

    def test_a_domain_fixed_is_part_of_every_design_without_being_searched(
        self, multi_domain_architecture
    ):
        selection = DomainSelection.parse("Design/* + corner/tt")
        space = ArchitectureSpace(multi_domain_architecture, selection=selection)
        assert space.size() == 6
        assert space.pinned == {"corner": "tt"}
        assert space.design((0, 0)).entry == "Design/8bits_2deep+corner/tt"
        # Two searches of the same architecture with different domains fixed are
        # two campaigns, so they cannot share an archive.
        assert selection.slug != DomainSelection.parse("Design/*+corner/ss").slug

    def test_the_main_domain_can_be_fixed_too(self, multi_domain_architecture):
        space = ArchitectureSpace(
            multi_domain_architecture, selection=DomainSelection.parse("Design/8bits_2deep+corner/*")
        )
        assert space.size() == 3
        assert space.design((1,)).entry == "Design/8bits_2deep+corner/tt"

    def test_a_configuration_that_is_not_there_is_said_so(self, multi_domain_architecture):
        with pytest.raises(UnknownConfigurationError):
            ArchitectureSpace(
                multi_domain_architecture, selection=DomainSelection.parse("Design/*+corner/nope")
            )

    def test_a_domain_that_is_not_there_is_said_so(self, multi_domain_architecture):
        # A misspelled domain would otherwise silently narrow the search.
        with pytest.raises(UnknownConfigurationError):
            ArchitectureSpace(
                multi_domain_architecture, selection=DomainSelection.parse("Design/*+corners/*")
            )


class TestSpace:
    def test_a_variable_is_an_axis_and_a_choice_is_a_design(self, architecture):
        space = ArchitectureSpace(architecture)
        assert space.lengths == [3, 2]
        assert space.size() == 6

        design = space.design((0, 0))
        # The design says what a run selects, spelled the way a user would.
        assert design.entry == "Design/8bits_2deep"
        assert design.values == {"width": 8, "depth": 2}
        assert space.design((2, 1)).entry == "Design/32bits_4deep"

    def test_the_designs_of_the_space_are_the_ones_a_sweep_would_run(self, architecture):
        space = ArchitectureSpace(architecture)
        searched = sorted(space.design(genome).entry for genome in space.genomes())
        swept = sorted(
            "Design/" + name for name in architecture.domains.main.configuration_names()
        )
        assert searched == swept

    def test_the_variables_of_a_command_are_axes_too(self, hls_architecture):
        # The case an exploration is most needed for: a design generated by
        # high-level synthesis has all of its knobs on the command line.
        space = ArchitectureSpace(hls_architecture)
        assert space.lengths == [3, 2]
        assert space.design((0, 0)).entry == "Filter+ii/1+taps/8"
        assert space.design((2, 1)).entry == "Filter+ii/2+taps/32"

    def test_an_architecture_with_one_design_is_not_something_to_search(self, tmp_path):
        from odatix.workspace import Workspace

        root = tmp_path / "odatix_userconfig" / "architectures"
        root.mkdir(parents=True)
        write_architecture(root, "Fixed", HLS.replace("list: [8, 16, 32]", "list: [8]").replace(
            "list: [1, 2]", "list: [1]"
        ))
        (tmp_path / "odatix.yml").write_text("arch_path: odatix_userconfig/architectures\n")
        space = ArchitectureSpace(Workspace(str(tmp_path)).architectures["Fixed"])
        with pytest.raises(EmptySpaceError):
            space.require_choice()


######################################
# Where a design that already ran sits
######################################

class FakeParamDomain(object):
    """A parameter domain of a job, as a run hands it to param_domains.yml."""

    def __init__(self, domain, domain_value, param_file):
        self.domain = domain
        self.domain_value = domain_value
        self.param_file = param_file
        self.use_parameters = True
        self.start_delimiter = None
        self.stop_delimiter = None
        self.param_target_file = None


def coordinates_of(arch_root, architecture, design, virtual_keys=()):
    """
    What a job running this design would record, going through exactly what a
    run calls -- so the coordinates under test are the ones a synthesis writes,
    not ones the test made up.
    """
    from odatix.workspace import design_point

    virtual = {
        domain: name for domain, name in design.configurations.items()
        if domain in set(virtual_keys)
    }
    param_domains = [
        FakeParamDomain(domain, name, os.path.join(
            str(arch_root), architecture, domain, str(name) + ".txt"
        ))
        for domain, name in design.configurations.items()
        if domain != "__main__" and domain not in set(virtual_keys)
    ]
    arch_name = architecture
    if "__main__" in design.configurations:
        arch_name += "/" + design.configurations["__main__"]
    return design_point.coordinates(str(arch_root), arch_name, param_domains, virtual)


class TestDesignPoint:
    """
    A run records where it sits, so that a search run later starts from what it
    measured. What is recorded are coordinates -- one value per variable -- and
    turning them back into a genome is a lookup per axis, never a guess.
    """

    def test_a_job_records_the_values_behind_its_configuration_name(self, tmp_path, architecture):
        space = ArchitectureSpace(architecture, selection=DomainSelection.parse("Design"))
        root = tmp_path / "odatix_userconfig" / "architectures"
        design = space.design((1, 0))

        point = coordinates_of(root, "Design", design)

        # The name says "16bits_2deep"; the coordinates say which variable is
        # worth what, which is what a search reasons about.
        assert point == {"width": "16", "depth": "2"}

    def test_every_design_is_found_back_from_what_its_job_recorded(self, tmp_path, architecture):
        space = ArchitectureSpace(architecture, selection=DomainSelection.parse("Design"))
        root = tmp_path / "odatix_userconfig" / "architectures"

        for genome in space.genomes():
            design = space.design(genome)
            if design is None:
                continue
            point = coordinates_of(root, "Design", design)
            assert space.genome_of(point, design.configurations) == design.genome

    def test_a_domain_of_its_own_names_its_variables_apart(self, tmp_path, multi_domain_architecture):
        space = ArchitectureSpace(
            multi_domain_architecture, selection=DomainSelection.parse("Design+corner")
        )
        root = tmp_path / "odatix_userconfig" / "architectures"
        design = space.design(space.clamp((0, 0, 2)))

        point = coordinates_of(root, "Design", design)

        # A variable outside the main domain is named for its domain: two
        # domains are free to declare the same variable.
        assert point["corner.corner"] == "ff"
        assert space.genome_of(point, design.configurations) == design.genome

    def test_the_variables_of_a_generation_command_are_coordinates_too(self, tmp_path, hls_architecture):
        space = ArchitectureSpace(hls_architecture, selection=DomainSelection.parse("Filter"))
        root = tmp_path / "odatix_userconfig" / "architectures"
        virtual_keys = {"taps", "ii"}

        for genome in space.genomes():
            design = space.design(genome)
            if design is None:
                continue
            point = coordinates_of(root, "Filter", design, virtual_keys)
            # The job spells them the way its directory is named; what is
            # recorded is the value its axis holds.
            assert space.genome_of(point, design.configurations) == design.genome

    def test_a_configuration_written_by_hand_is_found_back_by_its_name(self, tmp_path):
        from odatix.workspace import Workspace

        root = tmp_path / "odatix_userconfig" / "architectures"
        root.mkdir(parents=True)
        path = write_architecture(root, "Design", """\
            rtl_path: "rtl"
            top_level_file: "top.v"
            top_level_module: "top"
            clock_signal: "clk"
            use_parameters: Yes
            start_delimiter: "#("
            stop_delimiter: ")("
            param_target_file: "rtl/top.v"
        """)
        for name in ("small", "big"):
            with open(os.path.join(path, name + ".txt"), "w") as f:
                f.write("parameter WIDTH = 8;")
        (tmp_path / "odatix.yml").write_text("arch_path: odatix_userconfig/architectures\n")
        space = ArchitectureSpace(Workspace(str(tmp_path)).architectures["Design"])

        design = space.design((1,))
        # Nothing to record: the name is everything such a configuration says,
        # and the record already carries it.
        assert coordinates_of(root, "Design", design) == {}
        assert space.genome_of({}, design.configurations) == design.genome

    def test_a_record_of_another_space_is_not_placed_in_this_one(self, tmp_path, architecture):
        space = ArchitectureSpace(architecture, selection=DomainSelection.parse("Design"))

        # A variable the architecture gained since: the coordinates say nothing
        # about it, and guessing where it would go is exactly what is refused.
        assert space.genome_of({"width": "16"}) is None
        # A value that is not on the axis any more.
        assert space.genome_of({"width": "64", "depth": "2"}) is None
        # A variable that is not an axis of this space at all is not a reason
        # to reject a record, but it is not a coordinate either.
        assert space.genome_of({"width": "16", "depth": "2", "gone": "1"}) == (1, 0)

    def test_a_combination_the_rules_rule_out_is_no_design_to_start_from(self, constrained_architecture):
        space = ArchitectureSpace(
            constrained_architecture, selection=DomainSelection.parse("Design")
        )
        # 32 * 4 > 64: the coordinates are on the axes, and name nothing the
        # architecture runs.
        assert space.genome_of({"width": "32", "depth": "4"}) is None
        assert space.genome_of({"width": "32", "depth": "2"}) is not None

    def test_the_frequency_and_the_toolchain_come_from_the_record(self, architecture):
        from odatix.dse.space import Toolchain

        space = ArchitectureSpace(
            architecture,
            frequencies=[100, 200],
            toolchains=[Toolchain("vivado"), Toolchain("design_compiler")],
            selection=DomainSelection.parse("Design"),
        )
        point = {"width": "16", "depth": "2"}

        genome = space.genome_of(point, frequency=200, toolchain=Toolchain("design_compiler"))
        design = space.design(genome)
        assert design.frequency == 200
        assert design.toolchain.tool == "design_compiler"
        assert design.configuration == "16bits_2deep"

        # A record run at a frequency this exploration does not search, or by a
        # tool it does not run, is a result and not a place in this space.
        assert space.genome_of(point, frequency=150, toolchain=Toolchain("vivado")) is None
        assert space.genome_of(point, frequency=100, toolchain=Toolchain("genus")) is None
        assert space.genome_of(point, frequency=100) is None

    def test_a_pinned_domain_the_record_contradicts_is_another_space(self, tmp_path, multi_domain_architecture):
        space = ArchitectureSpace(
            multi_domain_architecture, selection=DomainSelection.parse("Design+corner/tt")
        )
        point = {"width": "16", "depth": "2"}

        assert space.genome_of(point, {"corner": "tt"}) is not None
        # The exploration is about the typical corner; a slow-corner record of
        # the same parameters is not one of its designs.
        assert space.genome_of(point, {"corner": "ss"}) is None

    def test_the_coordinates_stay_out_of_what_identifies_a_record(self):
        from odatix.lib import results_schema
        from odatix.workspace import design_point

        meta = {}
        results_schema.flatten_param_domains(
            {"__main__": "16bits_2deep", "__point__": {"width": "16", "depth": "2"}}, meta
        )

        assert meta["_point.width"] == "16"
        # Where a record sits is not what it is: two runs of the same design are
        # still the same record, and the coordinates are not a dimension to
        # chart or to join derived metrics on.
        assert results_schema.record_identity(meta) == (("main", "16bits_2deep"),)
        assert design_point.point_of_meta(meta) == {"width": "16", "depth": "2"}


######################################
# How the next designs are chosen
######################################

class FakeSpace(object):
    """A space of plain numbers, so a strategy can be watched on its own."""

    def __init__(self, lengths):
        self.lengths = list(lengths)

    def size(self):
        total = 1
        for length in self.lengths:
            total *= length
        return total

    def genomes(self):
        import itertools

        return itertools.product(*[range(length) for length in self.lengths])


def evaluation(genome, costs, metrics=None):
    class _Design(object):
        pass

    design = _Design()
    design.genome = tuple(genome)
    design.entry = str(genome)
    design.label = str(genome)
    design.values = {}
    design.frequency = None
    design.toolchain = None
    design.chose_toolchain = False
    result = Evaluation.__new__(Evaluation)
    result.design = design
    result.metrics = dict(metrics or {})
    result.costs = costs
    result.note = ""
    return result


class TestStrategies:
    def test_a_sweep_is_one_of_the_strategies(self):
        # Which is what makes the exhaustive run a special case rather than a
        # different mechanism.
        space = FakeSpace([2, 3])
        strategy = ExhaustiveSearch(space, random.Random(1))
        assert strategy.propose(4) == [(0, 0), (0, 1), (0, 2), (1, 0)]
        assert strategy.propose(10) == [(1, 1), (1, 2)]
        assert strategy.propose(1) == []
        assert strategy.exhausted

    def test_a_seed_makes_a_search_repeat_itself(self):
        # An evaluation costs an hour of synthesis; being able to run the same
        # search twice is what tells a change in the rules from noise.
        space = FakeSpace([5, 5, 5])
        first = RandomSearch(space, random.Random(7)).propose(6)
        second = RandomSearch(space, random.Random(7)).propose(6)
        assert first == second
        assert all(0 <= gene < 5 for genome in first for gene in genome)

    def test_a_search_with_nothing_evaluated_yet_looks_anywhere(self):
        strategy = GeneticSearch(FakeSpace([4, 4]), random.Random(3))
        assert len(strategy.propose(5)) == 5

    def test_a_search_looks_around_what_turned_out_well(self):
        # With the mutation practically off, a child is made of the genes of two
        # designs already evaluated -- and mostly of the good one's.
        space = FakeSpace([8, 8])
        strategy = GeneticSearch(space, random.Random(3), mutation=0.0000001)
        strategy.observe([
            evaluation((0, 0), (1.0,)),
            evaluation((7, 7), (100.0,)),
            evaluation((6, 6), (90.0,)),
        ])
        proposed = strategy.propose(200)
        assert all(gene in (0, 6, 7) for genome in proposed for gene in genome)
        genes = [gene for genome in proposed for gene in genome]
        # The best design contributes more genes than either of the others: the
        # search is drawn towards it without ever being confined to it.
        assert genes.count(0) > genes.count(6) and genes.count(0) > genes.count(7)

    def test_a_design_that_could_not_be_measured_teaches_nothing(self):
        strategy = GeneticSearch(FakeSpace([4]), random.Random(1))
        strategy.observe([evaluation((2,), None)])
        assert strategy.population == []

    def test_the_search_only_keeps_the_best_to_look_around(self):
        # Without a bound, a parent would be drawn out of everything ever run,
        # and the odds of looking around a good design would fall batch after
        # batch until the search was sampling at random.
        strategy = GeneticSearch(FakeSpace([16, 16]), random.Random(2), population=4)
        strategy.observe([evaluation((index, index), (float(index),)) for index in range(12)])
        assert len(strategy.population) == 4
        # And what it keeps is the best of them, not the last ones evaluated.
        assert sorted(strategy.costs) == [(0.0,), (1.0,), (2.0,), (3.0,)]

    def test_how_many_it_keeps_follows_the_batch_when_nothing_is_said(self):
        strategy = GeneticSearch(FakeSpace([16]), random.Random(2), batch=5)
        assert strategy.size == 20

    def test_a_mutation_always_changes_something(self):
        strategy = GeneticSearch(FakeSpace([3, 3]), random.Random(5), mutation=1.0)
        for _ in range(20):
            assert strategy.mutate([1, 1]) != [1, 1]

    def test_a_strategy_is_named_the_way_a_settings_file_names_it(self):
        assert strategy_for("genetic") is GeneticSearch
        assert strategy_for("sweep") is ExhaustiveSearch
        assert strategy_for("NSGA2") is GeneticSearch
        assert strategy_for("bayesian") is BayesianSearch
        assert strategy_for("bo") is BayesianSearch
        with pytest.raises(ValueError):
            strategy_for("gradient descent")


class TestGaussianProcess:
    """
    What a Bayesian search's acquisition is built on: a model of one
    objective, fit on a handful of points, at the size a campaign ever hands
    it.
    """

    def test_it_interpolates_what_it_was_fit_on(self):
        gp = GaussianProcess(seed=1)
        X = np.array([[0.0], [0.5], [1.0]])
        y = np.array([0.0, 10.0, 0.0])
        gp.fit(X, y)
        mean, variance = gp.predict(X)
        assert mean == pytest.approx(y, abs=0.05)
        # It has actually seen these points: there is little left to be
        # unsure about.
        assert all(v < 0.5 for v in variance)

    def test_it_is_less_sure_far_from_what_it_has_seen(self):
        gp = GaussianProcess(seed=2)
        X = np.array([[0.0], [0.1], [1.0]])
        y = np.array([0.0, 1.0, 5.0])
        gp.fit(X, y)
        _, variance = gp.predict(np.array([[0.1], [0.5]]))
        # 0.5 sits in the gap between the two clusters of points; 0.1 is
        # right on top of one of them.
        assert variance[1] > variance[0]

    def test_fitting_on_a_flat_surface_does_not_explode(self):
        # A GP whose signal has nothing to explain is a division by zero
        # waiting to happen if nothing guards against it -- callers do (see
        # BayesianSearch._fit), but the model itself should not crash either.
        gp = GaussianProcess(seed=3)
        X = np.array([[0.0], [0.3], [0.7], [1.0]])
        y = np.array([4.0, 4.0, 4.0, 4.0])
        gp.fit(X, y)
        mean, variance = gp.predict(np.array([[0.5]]))
        assert mean == pytest.approx([4.0], abs=0.1)

    def test_the_best_fit_wins_even_when_its_line_search_gave_up(self, monkeypatch):
        # Old scipy versions (the ones Python 3.6 gets) often end L-BFGS-B
        # with an abnormal line search termination, on the best optimum.
        import odatix.dse.gp as gp_module
        from types import SimpleNamespace

        results = iter([
            SimpleNamespace(fun=-10.0, success=True, x=np.log([0.001, 1.0, 1e-4])),
            SimpleNamespace(fun=-20.0, success=False, x=np.log([0.5, 1.0, 1e-4])),
            SimpleNamespace(fun=np.nan, success=False, x=np.log([0.2, 1.0, 1e-4])),
        ])
        monkeypatch.setattr(gp_module, "minimize", lambda *args, **kwargs: next(results))

        gp = GaussianProcess(restarts=3, seed=4).fit(np.array([[0.0], [0.5], [1.0]]), np.array([0.0, 1.0, 0.0]))
        assert gp.length_scales == pytest.approx([0.5])


class TestBayesianSearch:
    """
    The strategy meant for a campaign whose evaluations are too expensive to
    spend on a genetic search's batches: it models each objective and asks
    for the design expected to teach it the most (see
    :mod:`odatix.dse.bayesian`).
    """

    def test_a_search_with_nothing_evaluated_yet_looks_anywhere(self):
        strategy = BayesianSearch(FakeSpace([4, 4]), random.Random(3))
        proposed = strategy.propose(5)
        assert len(proposed) == 5
        assert all(0 <= gene < 4 for genome in proposed for gene in genome)
        assert strategy.models == []

    def test_a_design_that_could_not_be_measured_teaches_nothing(self):
        strategy = BayesianSearch(FakeSpace([4]), random.Random(1))
        strategy.observe([evaluation((2,), None)])
        assert strategy.genomes == []
        assert strategy.models == []

    def test_a_proposal_is_held_pending_until_it_is_observed(self):
        # What keeps two proposals made moments apart, before either has come
        # back, from landing on top of each other in async mode.
        strategy = BayesianSearch(FakeSpace([8, 8]), random.Random(2))
        genome = strategy.propose(1)[0]
        assert genome in strategy.pending
        strategy.observe([evaluation(genome, (1.0, 2.0))])
        assert genome not in strategy.pending
        assert strategy.genomes == [genome]

    def test_it_fits_one_model_per_objective_once_it_has_enough_to_go_on(self):
        strategy = BayesianSearch(FakeSpace([10, 10]), random.Random(4))
        strategy.observe([
            evaluation((index, index), (float(index), float(10 - index))) for index in range(6)
        ])
        assert len(strategy.models) == 2
        assert all(model is not None for model in strategy.models)
        # And it can now be asked for a candidate without falling back to
        # sampling at random.
        genome = strategy.propose(1)[0]
        assert 0 <= genome[0] < 10 and 0 <= genome[1] < 10

    def test_it_models_how_far_a_design_is_from_feasible(self):
        # A constraint is not an objective, so it gets a model of its own: how
        # much the constraints are missed by, which is what turns into how
        # likely a candidate is to be feasible at all.
        strategy = BayesianSearch(FakeSpace([10, 10]), random.Random(6))
        strategy.observe([
            evaluation(
                (index, index),
                Costs((float(index), float(10 - index)), violation=max(0.0, index - 4.0)),
            )
            for index in range(9)
        ])
        assert strategy.feasibility
        inside, outside = strategy._feasibility_of([(1, 1), (8, 8)])
        assert inside > 0.5 > outside

    def test_a_search_with_nothing_to_meet_takes_every_candidate_as_feasible(self):
        # No constraints declared, so nothing is ever missed and there is no
        # boundary to learn: the acquisition is the plain one.
        strategy = BayesianSearch(FakeSpace([10, 10]), random.Random(7))
        strategy.observe([
            evaluation((index, index), (float(index), float(10 - index))) for index in range(6)
        ])
        assert not strategy.feasibility
        assert strategy._feasibility_of([(1, 1), (8, 8)]) == [1.0, 1.0]

    def test_while_nothing_meets_the_constraints_it_looks_for_something_that_does(self):
        # There is no front worth growing yet -- every design measured so far
        # is, by the campaign's own terms, not an answer -- so the whole of the
        # ranking is which candidate is likeliest to be one.
        strategy = BayesianSearch(FakeSpace([12, 12]), random.Random(8))
        # Every design misses the constraints, by an amount that depends on
        # the second axis alone.
        strategy.observe([
            evaluation((x, y), Costs((float(x), float(11 - x)), violation=float(y) + 1.0))
            for x in (1, 5, 9) for y in (1, 5, 9)
        ])
        assert strategy.feasibility
        assert not strategy._has_feasible
        # The violation falls as the second axis falls, so that is where a
        # feasible design is to be looked for.
        proposed = [strategy.propose(1)[0] for _ in range(5)]
        assert sum(genome[1] for genome in proposed) / 5.0 < 4.0

    def test_it_can_model_each_constraint_on_its_own(self):
        # Two constraints missed along two different axes sum to a surface
        # shaped like neither of them, which is what one model of their total
        # has to fit. Asked for it, the search fits one model per constraint
        # instead and multiplies what they say.
        constraints = [Constraint("slack", minimum=0.0), Constraint("area", maximum=4.0)]
        strategy = BayesianSearch(
            FakeSpace([10, 10]), random.Random(11),
            constraints=constraints, constraint_models=True,
        )
        strategy.observe([
            evaluation(
                (x, y),
                Costs((float(x), float(y)), violation=max(0.0, x - 4.0) / 4.0 + max(0.0, y - 4.0) / 4.0),
                metrics={"slack": float(4 - x), "area": float(y)},
            )
            for x in (0, 3, 6, 9) for y in (0, 3, 6, 9)
        ])
        # One model per constraint, and a design has to satisfy both: missing
        # either one is enough to make a candidate an unlikely answer.
        assert len(strategy.feasibility) == 2
        both, one, neither = strategy._feasibility_of([(1, 1), (1, 9), (9, 9)])
        assert both > 0.5 > one
        assert both > 0.5 > neither

    def test_one_model_per_constraint_is_not_what_a_search_does_unasked(self):
        # It is one more Gaussian process to refit per constraint, on every
        # refit, so a campaign that has not asked for it gets the total.
        constraints = [Constraint("slack", minimum=0.0), Constraint("area", maximum=4.0)]
        strategy = BayesianSearch(FakeSpace([10, 10]), random.Random(12), constraints=constraints)
        strategy.observe([
            evaluation(
                (x, y),
                Costs((float(x), float(y)), violation=max(0.0, x - 4.0) / 4.0 + max(0.0, y - 4.0) / 4.0),
                metrics={"slack": float(4 - x), "area": float(y)},
            )
            for x in (0, 3, 6, 9) for y in (0, 3, 6, 9)
        ])
        assert len(strategy.feasibility) == 1

    def test_a_design_missing_a_constrained_metric_falls_back_to_the_total(self):
        # A channel with a hole in it is not one to fit: the violation the
        # cost vector carries is what is left to learn from.
        constraints = [Constraint("slack", minimum=0.0)]
        strategy = BayesianSearch(
            FakeSpace([10, 10]), random.Random(13),
            constraints=constraints, constraint_models=True,
        )
        strategy.observe([
            evaluation(
                (index, index),
                Costs((float(index), float(9 - index)), violation=max(0.0, index - 4.0)),
                metrics={} if index == 3 else {"slack": float(4 - index)},
            )
            for index in range(9)
        ])
        assert strategy.violations[3] is None
        assert len(strategy.feasibility) == 1
        inside, outside = strategy._feasibility_of([(1, 1), (8, 8)])
        assert inside > 0.5 > outside

    def test_an_infeasible_design_is_not_a_front_a_candidate_is_scored_against(self):
        # Once anything meets the constraints, a design that does not is out of
        # the front: it would otherwise cover volume no candidate can be
        # credited for reaching.
        strategy = BayesianSearch(FakeSpace([10, 10]), random.Random(9))
        strategy.observe([
            evaluation((1, 1), Costs((1.0, 1.0), violation=0.0)),
            evaluation((2, 2), Costs((0.0, 0.0), violation=3.0)),
            evaluation((3, 3), Costs((2.0, 2.0), violation=0.0)),
        ])
        assert [tuple(cost) for cost in strategy._current_front()] == [(1.0, 1.0)]

    def test_it_never_proposes_a_design_already_measured_or_in_flight(self):
        # Doing so would teach it nothing -- the point is either answered
        # already or on its way to being answered -- and would only have the
        # campaign discard it as already seen.
        strategy = BayesianSearch(FakeSpace([30]), random.Random(5))
        strategy.observe([
            evaluation((value,), (float(value),)) for value in (0, 14, 29)
        ])
        proposed = strategy.propose(10)
        assert len(proposed) == len(set(proposed)) == 10
        assert not (set(proposed) & {(0,), (14,), (29,)})


######################################
# The loop
######################################

class FakeEvaluator(object):
    """
    Runs nothing: a design is worth what a formula says it is worth.

    The formula is the point of the test -- the best designs are known in
    advance, so what is being checked is whether the search finds them.
    """

    def __init__(self, objectives, cost):
        self.objectives = objectives
        self.cost = cost
        self.evaluated = []

    def evaluate(self, designs):
        evaluations = []
        for design in designs:
            self.evaluated.append(design.entry)
            metrics = self.cost(design)
            evaluations.append(Evaluation(design, metrics=metrics, costs=self.objectives.costs(metrics)))
        return evaluations


class _FakePending(object):
    """A design in flight, in :class:`FakeAsyncEvaluator`'s made-up units of time."""

    def __init__(self, design, ticks):
        self.design = design
        self.ticks = ticks


class FakeAsyncEvaluator(object):
    """
    Runs nothing, in ``async`` mode: a design takes a made-up number of ticks
    to finish rather than a real one, which is what lets the mechanism --
    filling a slot the moment it frees rather than waiting for a batch -- be
    watched without a daemon or a clock.

    Every submission and every finish is recorded in order, which is the
    point: what is being checked is not only that every design gets run, but
    *when* the next one starts.
    """

    def __init__(self, objectives, cost, slow_first=0):
        self.objectives = objectives
        self.cost = cost
        #: How many ticks the first ``slow_first`` submissions take; every one
        #: after that takes a single tick. Zero: every design is as fast as
        #: any other.
        self.slow_first = slow_first
        self.events = []
        self._submitted = 0

    def begin_async(self):
        self._submitted = 0

    def submit(self, design):
        self._submitted += 1
        ticks = 5 if self._submitted <= self.slow_first else 1
        self.events.append(("submit", design.entry))
        return _FakePending(design, ticks)

    def derive(self):
        pass

    def poll(self, pending, cancel_event=None):
        while True:
            for item in pending:
                item.ticks -= 1
            finished = [item for item in pending if item.ticks <= 0]
            if finished:
                for item in finished:
                    pending.remove(item)
                    self.events.append(("finish", item.design.entry))
                return finished

    def collect(self, pending):
        metrics = self.cost(pending.design)
        return Evaluation(pending.design, metrics=metrics, costs=self.objectives.costs(metrics))


def campaign_settings(name="campaign", **overrides):
    """
    One campaign, as a run holds it: what it searches for, and the settings of
    the run it is part of (see :class:`odatix.dse.campaigns.RunSettings`).
    """
    campaign = CampaignSettings.from_dict({
        "run": "fmax_synthesis",
        "tool": "vivado",
        "objectives": [{"metric": "speed", "goal": "max"}, {"metric": "area", "goal": "min"}],
        "search": {"strategy": "genetic", "budget": 12, "batch": 4, "seed": 1},
        "architectures": ["Design"],
    })
    settings = DseSettings.from_dict({"campaigns": [name]})
    for key, value in overrides.items():
        if DseSettings.spec(key) is not None:
            settings[key] = value
        else:
            campaign[key] = value
    object.__setattr__(campaign, "name", name)
    return RunSettings(campaign, settings)


class TestCampaign:
    def cost(self, design):
        """A design is fast when it is wide, and small when it is narrow."""
        width = design.values["width"]
        depth = design.values["depth"]
        return {"speed": width * 10, "area": width * depth}

    def test_a_campaign_evaluates_no_more_than_its_budget(self, architecture, tmp_path):
        from odatix.workspace import Workspace

        settings = campaign_settings(search={"strategy": "random", "budget": 4, "batch": 2, "seed": 1})
        workspace = Workspace(str(tmp_path))
        objectives = settings.objective_list()
        evaluator = FakeEvaluator(objectives, self.cost)
        campaign = Campaign(workspace, architecture, settings, evaluator=evaluator)
        campaign.run()
        assert len(evaluator.evaluated) == 4

    def test_a_campaign_never_runs_the_same_design_twice(self, architecture, tmp_path):
        from odatix.workspace import Workspace

        # A budget larger than the space: what comes back is the space, once.
        settings = campaign_settings(search={"strategy": "genetic", "budget": 50, "batch": 3, "seed": 2})
        evaluator = FakeEvaluator(settings.objective_list(), self.cost)
        campaign = Campaign(Workspace(str(tmp_path)), architecture, settings, evaluator=evaluator)
        campaign.run()
        assert len(evaluator.evaluated) == len(set(evaluator.evaluated)) == 6

    def test_what_comes_back_is_the_trade_off_curve(self, architecture, tmp_path):
        from odatix.workspace import Workspace

        settings = campaign_settings(search={"strategy": "exhaustive", "budget": 50, "batch": 6, "seed": 1})
        evaluator = FakeEvaluator(settings.objective_list(), self.cost)
        campaign = Campaign(Workspace(str(tmp_path)), architecture, settings, evaluator=evaluator)
        archive = campaign.run()

        # The fastest design and the smallest one are both answers; a design
        # that is neither the fastest nor the smallest at its speed is not.
        front = sorted(evaluation.entry for evaluation in archive.front())
        assert front == ["Design/16bits_2deep", "Design/32bits_2deep", "Design/8bits_2deep"]
        assert os.path.isfile(archive.path)

    def test_a_campaign_stops_when_the_front_stops_moving(self, architecture, tmp_path):
        from odatix.workspace import Workspace

        settings = campaign_settings(
            search={"strategy": "random", "budget": 50, "batch": 2, "seed": 4, "patience": 1},
        )
        evaluator = FakeEvaluator(settings.objective_list(), lambda design: {"speed": 1, "area": 1})
        campaign = Campaign(Workspace(str(tmp_path)), architecture, settings, evaluator=evaluator)
        campaign.run()
        # Every design is worth the same, so the second batch improves nothing
        # and there is no reason to spend the rest of the budget.
        assert len(evaluator.evaluated) == 4

    def test_a_constrained_campaign_answers_with_designs_that_meet_them(
        self, architecture, tmp_path
    ):
        from odatix.workspace import Workspace

        # The widest designs are the fastest and the ones that miss the timing:
        # without the constraint they are the whole answer.
        def cost(design):
            width = design.values["width"]
            depth = design.values["depth"]
            return {"speed": width * 10, "area": width * depth, "slack": 1.0 if width < 32 else -0.5}

        settings = campaign_settings(
            search={"strategy": "exhaustive", "budget": 50, "batch": 6, "seed": 1},
            constraints=[{"metric": "slack", "min": 0}],
        )
        evaluator = FakeEvaluator(settings.objective_list(), cost)
        campaign = Campaign(Workspace(str(tmp_path)), architecture, settings, evaluator=evaluator)
        archive = campaign.run()

        front = sorted(evaluation.entry for evaluation in archive.front())
        assert front == ["Design/16bits_2deep", "Design/8bits_2deep"]
        assert all(evaluation.metrics["slack"] >= 0 for evaluation in archive.front())

    def test_a_campaign_whose_constraint_cannot_be_met_says_so(self, architecture, tmp_path):
        import yaml
        from odatix.workspace import Workspace

        settings = campaign_settings(
            search={"strategy": "exhaustive", "budget": 50, "batch": 6, "seed": 1},
            constraints=[{"metric": "slack", "min": 0}],
        )
        evaluator = FakeEvaluator(
            settings.objective_list(),
            lambda design: {"speed": 1, "area": design.values["width"], "slack": -1.0},
        )
        campaign = Campaign(Workspace(str(tmp_path)), architecture, settings, evaluator=evaluator)
        archive = campaign.run()

        # The closest it got, on record as not being an answer.
        assert archive.front()
        with open(archive.path) as f:
            written = yaml.safe_load(f)
        assert written["feasible"] is False
        assert written["front"][0]["unmet"] == ["slack >= 0.0 (measured -1.0)"]

    def test_a_malformed_constraint_is_a_settings_error(self, architecture, tmp_path):
        from odatix.workspace import Workspace

        settings = campaign_settings(constraints=[{"metric": "slack"}])
        with pytest.raises(CampaignError):
            Campaign(Workspace(str(tmp_path)), architecture, settings, evaluator=object())

    def test_an_exploration_with_no_objective_says_so(self, architecture, tmp_path):
        from odatix.workspace import Workspace

        settings = campaign_settings(objectives=[])
        campaign = Campaign(Workspace(str(tmp_path)), architecture, settings, evaluator=object())
        with pytest.raises(CampaignError):
            campaign.check()

    def test_an_unknown_search_mode_is_a_settings_error(self, architecture, tmp_path):
        from odatix.workspace import Workspace

        settings = campaign_settings(search={"strategy": "random", "mode": "parallel"})
        campaign = Campaign(Workspace(str(tmp_path)), architecture, settings, evaluator=object())
        with pytest.raises(CampaignError):
            campaign.check()


######################################
# Running continuously instead of by batch
######################################

class TestAsyncCampaign:
    """
    ``async`` mode's whole point: a straggler ties up its own slot, and not
    the slots next to it, because the next design is already running rather
    than waiting on the batch it happened to be drawn into (see
    Campaign.next_wave).
    """

    def cost(self, design):
        width = design.values["width"]
        depth = design.values["depth"]
        return {"speed": width * 10, "area": width * depth}

    def test_a_slow_design_does_not_hold_up_the_ones_after_it(self, architecture, tmp_path):
        from odatix.workspace import Workspace

        # The first design submitted takes five times as long as every other
        # one: in batch mode nothing new would start until it (and the batch
        # it was drawn into) finished. Here a third design must be submitted
        # the moment the fast one of the first two frees its slot.
        settings = campaign_settings(
            search={"strategy": "random", "budget": 3, "batch": 2, "seed": 1, "mode": "async"},
        )
        evaluator = FakeAsyncEvaluator(settings.objective_list(), self.cost, slow_first=1)
        campaign = Campaign(Workspace(str(tmp_path)), architecture, settings, evaluator=evaluator)
        campaign.run()

        submits = [entry for kind, entry in evaluator.events if kind == "submit"]
        assert len(submits) == 3
        third_submitted = evaluator.events.index(("submit", submits[2]))
        slow_finished = evaluator.events.index(("finish", submits[0]))
        assert third_submitted < slow_finished

    def test_an_async_campaign_evaluates_no_more_than_its_budget(self, architecture, tmp_path):
        from odatix.workspace import Workspace

        settings = campaign_settings(
            search={"strategy": "random", "budget": 4, "batch": 2, "seed": 1, "mode": "async"},
        )
        evaluator = FakeAsyncEvaluator(settings.objective_list(), self.cost)
        campaign = Campaign(Workspace(str(tmp_path)), architecture, settings, evaluator=evaluator)
        campaign.run()

        submits = [entry for kind, entry in evaluator.events if kind == "submit"]
        assert len(submits) == len(set(submits)) == 4

    def test_an_async_campaign_finds_the_same_kind_of_answer_a_batch_one_does(
        self, architecture, tmp_path
    ):
        from odatix.workspace import Workspace

        settings = campaign_settings(
            search={"strategy": "exhaustive", "budget": 50, "batch": 3, "seed": 1, "mode": "async"},
        )
        evaluator = FakeAsyncEvaluator(settings.objective_list(), self.cost)
        campaign = Campaign(Workspace(str(tmp_path)), architecture, settings, evaluator=evaluator)
        archive = campaign.run()

        front = sorted(evaluation.entry for evaluation in archive.front())
        assert front == ["Design/16bits_2deep", "Design/32bits_2deep", "Design/8bits_2deep"]


######################################
# Reading what came out
######################################

class TestEvaluator:
    def objectives(self):
        return Objectives.from_list([{"metric": "frequency", "goal": "max"}, "LUT_count"])

    def evaluator(self, tmp_path):
        from odatix.workspace import Workspace

        settings = campaign_settings()
        return Evaluator(Workspace(str(tmp_path)), settings, self.objectives())

    def test_a_dimension_that_is_a_number_is_a_metric_too(self, tmp_path):
        # Which is how "frequency" -- where an fmax synthesis puts its answer --
        # is an objective like any other.
        record = {
            "meta": {"architecture": "Design", "main": "8bits", "frequency": 250, "tool": "vivado"},
            "metrics": {"LUT_count": 40},
        }
        assert Evaluator.metrics_of(record) == {"LUT_count": 40, "frequency": 250}

    def test_a_design_is_worth_what_its_best_record_is_worth(self, tmp_path):
        # A design synthesized at ten frequencies has ten records.
        evaluator = self.evaluator(tmp_path)
        records = [
            {"meta": {"frequency": 100}, "metrics": {"LUT_count": 40}},
            {"meta": {"frequency": 250}, "metrics": {"LUT_count": 40}},
            {"meta": {"frequency": 180}, "metrics": {"LUT_count": 40}},
        ]
        assert evaluator.best_of(records)[0]["frequency"] == 250

    def test_a_record_that_meets_the_constraints_is_kept_over_a_faster_one(self, tmp_path):
        # The design is being run at several frequencies to find one that works:
        # keeping the fastest of the ones that do not answers another question.
        from odatix.workspace import Workspace

        objectives = Objectives.from_list(
            [{"metric": "frequency", "goal": "max"}, "LUT_count"],
            Constraints.from_list([{"metric": "Slack", "min": 0}]),
        )
        evaluator = Evaluator(Workspace(str(tmp_path)), campaign_settings(), objectives)
        records = [
            {"meta": {"frequency": 250}, "metrics": {"LUT_count": 40, "Slack": -0.4}},
            {"meta": {"frequency": 180}, "metrics": {"LUT_count": 40, "Slack": 0.1}},
        ]
        assert evaluator.best_of(records)[0]["frequency"] == 180

    def test_a_design_the_run_did_not_measure_comes_back_unmeasured(self, tmp_path, architecture):
        # And it comes back, rather than being left out: a search has to be told
        # that a place in the space leads nowhere, or it goes back to it.
        evaluator = self.evaluator(tmp_path)
        design = ArchitectureSpace(architecture).design((0, 0))
        result = evaluator.measure(design, {}, {})
        assert not result.measured
        assert "no result" in result.note

    def test_a_design_is_found_by_its_configuration(self, tmp_path, architecture):
        evaluator = self.evaluator(tmp_path)
        design = ArchitectureSpace(architecture).design((0, 0))
        meta = {
            "type": "fmax_synthesis", "tool": "vivado", "target": "xc7a100t",
            "architecture": "Design", "configuration": "8bits_2deep", "main": "8bits_2deep",
            "frequency": 300, "timestamp": "now",
        }
        assert evaluator.identity(meta) == evaluator.design_identity(design)

    def test_a_batch_is_run_through_an_ordinary_run_settings_file(self, tmp_path, architecture):
        # An exploration adds no kind of run: it fills in a selection and runs
        # the command that was already there. And it writes that selection next
        # to the work directory, never over the one the user keeps.
        from odatix.workspace.jobs import job_config

        evaluator = self.evaluator(tmp_path)
        space = ArchitectureSpace(architecture)
        designs = [space.design((0, 0)), space.design((2, 1))]

        path = evaluator.write_batch_settings(designs)
        assert os.path.realpath(path) != os.path.realpath(
            evaluator.workspace.jobs["fmax_synthesis"].path
        )

        written = job_config(path, "fmax_synthesis").load()
        assert written.architectures == ["Design/8bits_2deep", "Design/32bits_4deep"]
        assert written.ask_continue is False

    def test_a_batch_that_was_already_run_is_not_a_failure(self, tmp_path, architecture, monkeypatch):
        # A run refuses to start when every design of the batch is already
        # done. Those designs are measured -- they were measured earlier -- so
        # the exploration reads their results instead of giving up.
        evaluator = self.evaluator(tmp_path)
        design = ArchitectureSpace(architecture).design((0, 0))
        identity = evaluator.design_identity(design)
        known = {identity: [{"meta": {"frequency": 300}, "metrics": {"LUT_count": 44}}]}

        monkeypatch.setattr(evaluator, "run_batch", lambda designs: "nothing left to run")
        monkeypatch.setattr(evaluator, "_records", lambda: known)
        assert evaluator.evaluate([design])[0].metrics["frequency"] == 300

    def test_a_batch_that_failed_and_measured_nothing_stops_the_exploration(
        self, tmp_path, architecture, monkeypatch
    ):
        # Otherwise the next batch fails the same way, and the one after it.
        from odatix.dse.evaluation import EvaluationError

        evaluator = self.evaluator(tmp_path)
        design = ArchitectureSpace(architecture).design((0, 0))
        monkeypatch.setattr(evaluator, "run_batch", lambda designs: "the eda tool is not installed")
        with pytest.raises(EvaluationError):
            evaluator.evaluate([design])

    def test_only_what_the_batch_produced_is_read(self, tmp_path, architecture):
        # Reading everything would take an older result of the same design for
        # the one the batch just measured.
        evaluator = self.evaluator(tmp_path)
        design = ArchitectureSpace(architecture).design((0, 0))
        identity = evaluator.design_identity(design)
        old = {"meta": {"frequency": 100}, "metrics": {"LUT_count": 40}}
        new = {"meta": {"frequency": 300}, "metrics": {"LUT_count": 44}}
        result = evaluator.measure(design, {identity: [old, new]}, {identity: [old]})
        assert result.metrics["frequency"] == 300


######################################
# What runs the designs
######################################

TOOL_SETTINGS = """\
default_flow: synthesis
unix:
  tool_test_command: "true"
  custom_freq_synthesis_command: "true"
  fmax_synthesis_command: "true"
flows:
  power_opt:
    label: "Power optimized"
"""


@pytest.fixture
def tool_workspace(tmp_path):
    """
    A workspace holding two eda tools: one with two flows and two targets, one
    with a single flow and a target of its own.
    """
    from odatix.workspace import Workspace

    (tmp_path / "odatix.yml").write_text(
        "arch_path: odatix_userconfig/architectures\n"
        "tool_path: odatix_userconfig/tools\n"
        "target_path: odatix_userconfig/targets\n"
    )
    tools = tmp_path / "odatix_userconfig" / "tools"
    targets = tmp_path / "odatix_userconfig" / "targets"
    targets.mkdir(parents=True)

    for name, flows, enabled in (
        ("toolA", TOOL_SETTINGS, ["fast", "small"]),
        ("toolB", "default_flow: synthesis\nunix:\n  tool_test_command: \"true\"\n", ["tiny"]),
    ):
        (tools / name).mkdir(parents=True)
        (tools / name / "tool.yml").write_text(flows)
        (targets / "target_{0}.yml".format(name)).write_text(
            "constraint_file: constraints.txt\ntargets:\n"
            + "".join("  - {0}\n".format(target) for target in enabled)
            # A target that is turned off is not one the search may choose.
            + "  # - retired\n"
        )

    root = tmp_path / "odatix_userconfig" / "architectures"
    root.mkdir(parents=True)
    write_architecture(root, "Design", PARAMETERIZED)
    return Workspace(str(tmp_path))


def tool_settings(**overrides):
    settings = campaign_settings(run="custom_freq_synthesis")
    settings.update(overrides)
    return settings


class TestToolchains:
    def test_one_tool_on_every_target_is_not_an_axis(self, tool_workspace):
        # Which is what an exploration that says nothing about them looks like:
        # a design is run the way "odatix synth" would run it, and is worth what
        # its best target is worth.
        settings = tool_settings(tool="toolA")
        chains = settings.toolchains(tool_workspace)
        assert [chain.label for chain in chains] == ["toolA"]
        assert not settings.explores_toolchain(tool_workspace)

        architecture = tool_workspace.architectures["Design"]
        space = ArchitectureSpace(architecture, toolchains=chains)
        assert space.size() == ArchitectureSpace(architecture).size()
        # The design still knows what ran it: that is where its results are.
        design = space.design((0, 0))
        assert design.toolchain.tool == "toolA"
        assert design.chose_toolchain is False
        assert design.label == design.entry

    def test_naming_several_targets_makes_them_an_axis(self, tool_workspace):
        settings = tool_settings(tool="toolA", target=["fast", "small"])
        chains = settings.toolchains(tool_workspace)
        assert [chain.label for chain in chains] == ["toolA on fast", "toolA on small"]

        architecture = tool_workspace.architectures["Design"]
        plain = ArchitectureSpace(architecture)
        space = ArchitectureSpace(architecture, toolchains=chains)
        assert space.size() == plain.size() * 2
        # Last, so that the parameters keep the places an earlier archive knows.
        assert space.design((0, 0, 1)).entry == space.design((0, 0, 0)).entry
        assert space.design((0, 0, 1)).toolchain.target == "small"
        assert space.design((0, 0, 1)).chose_toolchain is True

    def test_tools_flows_and_targets_are_one_axis_of_what_can_run(self, tool_workspace):
        # A flow belongs to a tool and so does a target: combining them freely
        # would keep proposing designs no workspace can run.
        settings = tool_settings(
            tool=["toolA", "toolB"], flow=["synthesis", "power_opt"], target=["fast", "tiny"],
        )
        assert [chain.label for chain in settings.toolchains(tool_workspace)] == [
            "toolA@synthesis on fast",
            "toolA@power_opt on fast",
            "toolB@synthesis on tiny",
        ]

    def test_a_toolchain_the_workspace_does_not_hold_is_refused(self, tool_workspace):
        from odatix.dse.space import UnknownToolchainError

        with pytest.raises(UnknownToolchainError):
            tool_settings(tool="no_such_tool").toolchains(tool_workspace)
        with pytest.raises(UnknownToolchainError):
            tool_settings(tool="toolA", flow=["no_such_flow"]).toolchains(tool_workspace)
        # A target the file keeps commented out is not one that can be chosen.
        with pytest.raises(UnknownToolchainError):
            tool_settings(tool="toolA", target=["retired"]).toolchains(tool_workspace)

    def evaluator(self, workspace, settings):
        return Evaluator(workspace, settings, settings.objective_list())

    def test_designs_run_by_different_toolchains_are_run_apart(self, tool_workspace):
        # One run does one thing: it runs with one tool, one of its flows, on
        # the targets it is given.
        settings = tool_settings(tool=["toolA", "toolB"])
        evaluator = self.evaluator(tool_workspace, settings)
        space = ArchitectureSpace(
            tool_workspace.architectures["Design"], toolchains=settings.toolchains(tool_workspace)
        )
        designs = [space.design((0, 0, 0)), space.design((1, 0, 1)), space.design((2, 0, 0))]

        groups = evaluator.groups(designs)
        assert [(chain.label, len(group)) for chain, _frequency, group in groups] == [
            ("toolA", 2), ("toolB", 1),
        ]

    def test_the_same_design_run_by_two_toolchains_is_two_designs(self, tool_workspace):
        # Which is what the search is for here: the records are the same
        # configuration, and only what ran it tells them apart.
        settings = tool_settings(tool="toolA", target=["fast", "small"])
        evaluator = self.evaluator(tool_workspace, settings)
        space = ArchitectureSpace(
            tool_workspace.architectures["Design"], toolchains=settings.toolchains(tool_workspace)
        )
        fast, small = space.design((0, 0, 0)), space.design((0, 0, 1))
        assert evaluator.explores_target is True
        assert evaluator.explores_tool is False
        assert evaluator.design_identity(fast) != evaluator.design_identity(small)

        meta = {
            "type": "custom_freq_synthesis", "tool": "toolA", "target": "fast",
            "architecture": "Design", "configuration": fast.configuration,
            "main": fast.configuration,
        }
        assert evaluator.identity(meta) == evaluator.design_identity(fast)

    def test_a_target_nobody_searched_does_not_tell_two_records_apart(self, tool_workspace):
        # An exploration running every target its tool enables sees one design
        # with several records, and keeps the best of them.
        settings = tool_settings(tool="toolA")
        evaluator = self.evaluator(tool_workspace, settings)
        space = ArchitectureSpace(
            tool_workspace.architectures["Design"], toolchains=settings.toolchains(tool_workspace)
        )
        design = space.design((0, 0))
        common = {"architecture": "Design", "main": design.configuration}
        assert evaluator.identity(dict(common, target="fast")) == evaluator.design_identity(design)
        assert evaluator.identity(dict(common, target="small")) == evaluator.design_identity(design)

    def test_the_search_reads_the_results_file_of_every_tool_it_may_run(self, tool_workspace):
        settings = tool_settings(tool=["toolA", "toolB"])
        evaluator = self.evaluator(tool_workspace, settings)
        assert evaluator.tools == ["toolA", "toolB"]


######################################
# At what frequency
######################################

def freq_settings(**frequencies):
    return campaign_settings(run="custom_freq_synthesis", frequencies=frequencies)


class TestFrequencies:
    def evaluator(self, tmp_path, settings):
        from odatix.workspace import Workspace

        return Evaluator(Workspace(str(tmp_path)), settings, settings.objective_list())

    def test_fixed_frequencies_are_not_an_axis(self, architecture):
        # Every design is run at all of them: what is searched is still the
        # parameters, and a design is worth what its best frequency is worth.
        settings = freq_settings(list=[100, 200])
        assert not settings.explores_frequency()
        assert settings.frequency_values() == [100, 200]
        space = ArchitectureSpace(architecture, frequencies=None)
        assert space.design((0, 0)).frequency is None

    def test_explored_frequencies_are_an_axis_of_their_own(self, architecture):
        settings = freq_settings(explore=True, range={"from": 100, "to": 300, "step": 100})
        assert settings.frequency_values() == [100, 200, 300]

        plain = ArchitectureSpace(architecture)
        space = ArchitectureSpace(architecture, frequencies=settings.frequency_values())
        assert space.size() == plain.size() * 3
        # Last, so that the parameters keep the places an earlier archive knows.
        assert space.design((0, 0, 1)).frequency == 200
        assert space.design((0, 0, 1)).entry == space.design((0, 0, 0)).entry

    def test_the_frequency_is_only_read_for_a_custom_frequency_synthesis(self):
        # An fmax synthesis looks for its frequency; nothing tells it one.
        settings = campaign_settings(run="fmax_synthesis", frequencies={"explore": True})
        assert not settings.explores_frequency()
        assert settings.frequency_values() == []

    def test_a_batch_is_told_the_frequencies_to_run_at(self, tmp_path, architecture):
        from odatix.workspace.jobs import job_config

        settings = freq_settings(list=[100, 200])
        evaluator = self.evaluator(tmp_path, settings)
        design = ArchitectureSpace(architecture).design((0, 0))

        path = evaluator.write_batch_settings([design])
        written = job_config(path, "custom_freq_synthesis").load()
        assert written.frequencies.frequencies == [100, 200]
        # The architectures' own frequencies would be run otherwise.
        assert written.frequencies.override is True
        assert written.frequencies.use_custom_freq_range is False

    def test_designs_the_search_gave_different_frequencies_are_run_apart(self, tmp_path, architecture):
        # A run settings file says one set of frequencies for everything it
        # selects, so a batch that mixes them takes one run each.
        settings = freq_settings(explore=True, range={"from": 100, "to": 200, "step": 100})
        evaluator = self.evaluator(tmp_path, settings)
        space = ArchitectureSpace(architecture, frequencies=settings.frequency_values())
        designs = [space.design((0, 0, 0)), space.design((1, 0, 1)), space.design((2, 0, 0))]

        groups = evaluator.groups(designs)
        assert [(frequency, len(group)) for _chain, frequency, group in groups] == [(100, 2), (200, 1)]

        path = evaluator.write_batch_settings(groups[1][2], groups[1][0], groups[1][1])
        from odatix.workspace.jobs import job_config

        assert job_config(path, "custom_freq_synthesis").load().frequencies.frequencies == [200]

    def test_the_same_design_at_two_frequencies_is_two_designs(self, tmp_path, architecture):
        # Which is what the search is for here: the records are the same
        # configuration, and only the frequency tells them apart.
        settings = freq_settings(explore=True, range={"from": 100, "to": 200, "step": 100})
        evaluator = self.evaluator(tmp_path, settings)
        space = ArchitectureSpace(architecture, frequencies=settings.frequency_values())
        slow, fast = space.design((0, 0, 0)), space.design((0, 0, 1))
        assert evaluator.design_identity(slow) != evaluator.design_identity(fast)

        meta = {
            "type": "custom_freq_synthesis", "tool": "vivado", "architecture": "Design",
            "configuration": slow.configuration, "main": slow.configuration, "frequency": 100.0,
        }
        assert evaluator.identity(meta) == evaluator.design_identity(slow)

        records = {evaluator.design_identity(fast): [{"meta": meta, "metrics": {"area": 44, "speed": 2}}]}
        assert evaluator.measure(fast, records, {}).metrics["area"] == 44
        assert not evaluator.measure(slow, records, {}).measured


######################################
# What else an evaluation runs
######################################

class TestSimulations:
    """
    An objective is not restricted to what a synthesis measures: a batch may
    simulate its designs too, and a derived metric brings what the testbench
    measured onto the record the search reads.
    """

    def evaluator(self, tmp_path, **overrides):
        from odatix.workspace import Workspace

        settings = campaign_settings(**overrides)
        return Evaluator(Workspace(str(tmp_path)), settings, settings.objective_list())

    def test_an_evaluation_simulates_nothing_unless_it_is_asked_to(self, tmp_path, architecture):
        # Which is the ordinary case: an exploration looking for area and
        # frequency has nothing to simulate.
        evaluator = self.evaluator(tmp_path)
        design = ArchitectureSpace(architecture).design((0, 0))
        assert evaluator.simulations == []
        assert evaluator.start_simulations([design]) == (None, None)

    def test_the_simulations_of_a_batch_run_on_the_designs_being_evaluated(self, tmp_path, architecture):
        # And they are written next to the work directory, never over the
        # selection the user keeps in "simulation_settings.yml".
        from odatix.workspace.jobs import job_config

        evaluator = self.evaluator(tmp_path, simulations=["TB_Design"])
        space = ArchitectureSpace(architecture)
        path = evaluator.write_simulation_settings([space.design((0, 0)), space.design((2, 1))])
        assert os.path.realpath(path) != os.path.realpath(
            evaluator.workspace.jobs["simulation"].path
        )

        written = job_config(path, "simulation").load()
        assert written.simulations == {"TB_Design": ["Design/8bits_2deep", "Design/32bits_4deep"]}
        assert written.ask_continue is False

    def test_a_design_evaluated_at_two_frequencies_is_simulated_once(self, tmp_path, architecture):
        # What a testbench measures does not depend on the frequency the search
        # chose to synthesize at.
        from odatix.workspace.jobs import job_config

        from odatix.workspace import Workspace

        settings = freq_settings(explore=True, range={"from": 100, "to": 200, "step": 100})
        settings.simulations = ["TB_Design"]
        evaluator = Evaluator(Workspace(str(tmp_path)), settings, settings.objective_list())
        space = ArchitectureSpace(architecture, frequencies=settings.frequency_values())
        path = evaluator.write_simulation_settings([space.design((0, 0, 0)), space.design((0, 0, 1))])
        assert job_config(path, "simulation").load().simulations == {
            "TB_Design": ["Design/8bits_2deep"]
        }

    def test_a_batch_starts_its_simulations_before_it_waits_for_anything(
        self, tmp_path, architecture, monkeypatch
    ):
        # They run alongside the synthesis rather than after it: neither needs
        # the other's result, only the derived metrics do.
        evaluator = self.evaluator(tmp_path, simulations=["TB_Design"])
        order = []

        def note(step):
            def step_ran(*arguments, **keywords):
                order.append(step)
                return None, None
            return step_ran

        monkeypatch.setattr(evaluator, "start_simulations", note("simulate"))
        monkeypatch.setattr(evaluator, "start_batch", note("synthesize"))
        monkeypatch.setattr(evaluator, "derive", note("derive"))

        evaluator.run_batch([ArchitectureSpace(architecture).design((0, 0))])
        assert order == ["simulate", "synthesize", "derive"]

    def test_a_simulated_metric_is_an_objective_like_any_other(self, tmp_path, architecture):
        # The whole point of simulating: a search cannot synthesize a cycle
        # count, and it never has to know that this one was not synthesized.
        import odatix.lib.results_schema as results_schema
        from odatix.workspace import Workspace

        workspace = Workspace(str(tmp_path))
        design = ArchitectureSpace(architecture).design((0, 0))

        results = workspace.paths.result_path
        os.makedirs(results, exist_ok=True)
        results_schema.dump_results_file(
            os.path.join(results, "results_vivado.yml"), {},
            [results_schema.make_record(
                {
                    results_schema.META_TYPE: results_schema.TYPE_FMAX,
                    results_schema.META_TOOL: "vivado",
                    results_schema.META_ARCHITECTURE: "Design",
                    results_schema.META_CONFIGURATION: design.configuration,
                    results_schema.MAIN_DOMAIN_META_KEY: design.configuration,
                    "frequency": 250,
                },
                {"LUT_count": 40},
            )],
        )
        results_schema.dump_results_file(
            os.path.join(results, "results_simulation.yml"), {},
            [results_schema.make_simulation_record(
                simulation="TB_Design", architecture="Design",
                configuration=design.configuration, arch_full=design.configuration,
                run_dir=None, simulation_definition_dir=None, metrics={"Cycles": 120},
            )],
        )

        derived = workspace.paths.derived_metrics_file
        os.makedirs(os.path.dirname(derived), exist_ok=True)
        with open(derived, "w") as f:
            f.write("derived_metrics:\n  Cycles:\n    from: simulation\n")

        settings = campaign_settings(
            simulations=["TB_Design"],
            objectives=[{"metric": "frequency", "goal": "max"}, "Cycles"],
        )
        evaluator = Evaluator(workspace, settings, settings.objective_list())
        assert evaluator.derive() is True

        result = evaluator.measure(design, evaluator._records(), {})
        assert result.measured
        assert result.metrics["Cycles"] == 120

    def test_a_workspace_that_derives_nothing_does_not_pay_for_it(self, tmp_path, architecture):
        evaluator = self.evaluator(tmp_path)
        assert evaluator.derive() is False

    def test_an_exploration_says_so_when_a_simulation_does_not_exist(self, tmp_path, architecture):
        # Rather than failing every batch the same way, hours in, with the
        # designs coming back unmeasured for want of a metric nothing produced.
        settings = campaign_settings(simulations=["TB_Missing"])
        campaign = Campaign(architecture.workspace, architecture, settings)
        with pytest.raises(CampaignError) as error:
            campaign.check()
        assert "TB_Missing" in str(error.value)


######################################
# What is written down
######################################

class TestArchive:
    def test_the_archive_holds_what_was_run_and_what_the_answer_is(self, tmp_path):
        objectives = Objectives.from_list([{"metric": "speed", "goal": "max"}, "area"])

        class _Design(object):
            def __init__(self, entry, values):
                self.entry = entry
                self.label = entry
                self.values = values
                self.genome = (0,)
                self.frequency = None
                self.toolchain = None
                self.chose_toolchain = False

        def made(entry, speed, area):
            metrics = {"speed": speed, "area": area}
            design = _Design(entry, {})
            return Evaluation(design, metrics=metrics, costs=objectives.costs(metrics))

        archive = Archive(str(tmp_path / "dse" / "Design.yml"), "Design", objectives)
        assert archive.improved_by([made("a", 100, 10), made("b", 50, 20)])
        # "b" is slower *and* bigger: it never was an answer, and dropping it
        # changes nothing.
        assert not archive.improved_by([made("c", 40, 30)])
        assert [evaluation.entry for evaluation in archive.front()] == ["a"]

        archive.save()
        import yaml

        with open(archive.path) as f:
            written = yaml.safe_load(f)
        assert written["evaluated"] == 3
        assert [entry["configuration"] for entry in written["front"]] == ["a"]


######################################
# The axes, under everything else
######################################

class TestAxes:
    def test_paired_variables_share_an_axis(self):
        # A search that moved them apart would break the pairing the sweep
        # honours -- the point of a group is that the values go together.
        space = ParameterSpace(
            {
                "mantissa": {"type": "list", "group": "float", "settings": {"list": [10, 23, 52]}},
                "exponent": {"type": "list", "group": "float", "settings": {"list": [5, 8, 11]}},
            },
            name="${mantissa}_${exponent}",
            template="${mantissa}",
            source="<test>",
        )
        axes = space.axes()
        assert len(axes) == 1
        assert axes[0].variables == ["mantissa", "exponent"]
        assert axes[0].rows[1] == {"mantissa": 23, "exponent": 8}
        assert space.size() == 3

    def test_a_choice_of_one_row_per_axis_is_a_point_of_the_space(self):
        space = ParameterSpace(
            {
                "width": {"type": "list", "settings": {"list": [8, 16]}},
                "depth": {"type": "list", "settings": {"list": [2, 4]}},
            },
            name="${width}x${depth}",
            template="W=${width} D=${depth}",
            source="<test>",
        )
        assert space.size() == len(space.points()) == 4
        assignment = space.assignment((1, 0))
        assert assignment == {"width": 16, "depth": 2}
        assert space.point(assignment).name == "16x2"


######################################
# Running the search as a job of its own
######################################

class TestResume:
    """
    An exploration is long and gets interrupted; what it had done is on disk
    after every batch, and starting again must not spend the budget twice.
    """

    def cost(self, design):
        width = design.values["width"]
        depth = design.values["depth"]
        return {"speed": width * 10, "area": width * depth}

    def _campaign(self, architecture, tmp_path, **overrides):
        from odatix.workspace import Workspace

        settings = campaign_settings(**overrides)
        evaluator = FakeEvaluator(settings.objective_list(), self.cost)
        campaign = Campaign(Workspace(str(tmp_path)), architecture, settings, evaluator=evaluator)
        return campaign, evaluator

    def test_a_campaign_picks_up_where_it_was_interrupted(self, architecture, tmp_path):
        search = {"strategy": "exhaustive", "budget": 4, "batch": 2, "seed": 1}
        first, evaluator = self._campaign(architecture, tmp_path, search=search)
        first.run()
        assert len(evaluator.evaluated) == 4

        # Same campaign, a budget of six: two designs are left to look at, not six.
        search = dict(search, budget=6)
        second, evaluator = self._campaign(architecture, tmp_path, search=search)
        archive = second.run()
        assert len(evaluator.evaluated) == 2
        assert len(archive) == 6
        assert len(set(evaluation.entry for evaluation in archive.evaluations)) == 6

    def test_what_was_evaluated_is_not_proposed_again(self, architecture, tmp_path):
        search = {"strategy": "genetic", "budget": 3, "batch": 3, "seed": 2}
        first, first_evaluator = self._campaign(architecture, tmp_path, search=search)
        first.run()

        second, second_evaluator = self._campaign(architecture, tmp_path, search=dict(search, budget=6))
        second.run()
        assert not set(first_evaluator.evaluated) & set(second_evaluator.evaluated)

    def test_overwrite_starts_the_search_over(self, architecture, tmp_path):
        search = {"strategy": "exhaustive", "budget": 4, "batch": 2, "seed": 1}
        first, _ = self._campaign(architecture, tmp_path, search=search)
        first.run()

        # "Evaluate again what is already done" is what was asked for.
        second, evaluator = self._campaign(architecture, tmp_path, search=search, overwrite=True)
        second.run()
        assert len(evaluator.evaluated) == 4

    def test_an_archive_of_another_space_is_not_picked_up(self, architecture, tmp_path):
        import yaml

        search = {"strategy": "exhaustive", "budget": 4, "batch": 2, "seed": 1}
        first, _ = self._campaign(architecture, tmp_path, search=search)
        archive = first.run()

        # The architecture gained a parameter since: nothing is where it was.
        written = yaml.safe_load(open(archive.path).read())
        for record in written["evaluations"]:
            record["genome"] = list(record["genome"]) + [0]
        with open(archive.path, "w") as f:
            yaml.safe_dump(written, f)

        second, evaluator = self._campaign(architecture, tmp_path, search=search)
        second.run()
        assert len(evaluator.evaluated) == 4


class TestReuse:
    """
    A workspace is rarely empty when an exploration starts, and a design
    something already measured is a design the search is given for free -- when
    the run that measured it recorded where it sits (see
    odatix.workspace.design_point). Nothing is reconstructed for the ones that
    did not.
    """

    def objectives(self):
        return [{"metric": "frequency", "goal": "max"}, {"metric": "LUT_count", "goal": "min"}]

    def write_result(self, tmp_path, meta=None, metrics=None):
        import odatix.lib.results_schema as results_schema
        from odatix.workspace import Workspace

        workspace = Workspace(str(tmp_path))
        results = workspace.paths.result_path
        os.makedirs(results, exist_ok=True)
        record_meta = {
            results_schema.META_TYPE: results_schema.TYPE_FMAX,
            results_schema.META_TOOL: "vivado",
            results_schema.META_ARCHITECTURE: "Design",
            results_schema.META_CONFIGURATION: "8bits_2deep",
            results_schema.MAIN_DOMAIN_META_KEY: "8bits_2deep",
            "frequency": 250,
        }
        record_meta.update(meta or {})
        results_schema.dump_results_file(
            os.path.join(results, "results_vivado.yml"), {},
            [results_schema.make_record(record_meta, dict(metrics or {"LUT_count": 40}))],
        )
        return workspace

    def evaluator(self, workspace, **overrides):
        settings = campaign_settings(objectives=self.objectives(), **overrides)
        return Evaluator(workspace, settings, settings.objective_list())

    def test_a_design_something_already_measured_is_found(self, tmp_path, architecture):
        # The whole point: a single synthesis run months ago is one design of
        # the space evaluated, and the search never has to run it.
        workspace = self.write_result(tmp_path, {"_point.width": "8", "_point.depth": "2"})
        space = ArchitectureSpace(architecture)

        known = self.evaluator(workspace).known(space)
        assert len(known) == 1
        assert known[0].genome == (0, 0)
        assert known[0].metrics["LUT_count"] == 40
        assert known[0].reused

    def test_a_record_without_coordinates_is_left_alone(self, tmp_path, architecture):
        # Written before a run recorded where it sat: it is read for the front,
        # as it always was, and nothing is guessed from its name.
        workspace = self.write_result(tmp_path)
        assert self.evaluator(workspace).known(ArchitectureSpace(architecture)) == []

    def test_a_record_of_another_space_is_left_alone(self, tmp_path, architecture):
        # The value is not on the axis: the architecture has changed since.
        workspace = self.write_result(tmp_path, {"_point.width": "64", "_point.depth": "2"})
        assert self.evaluator(workspace).known(ArchitectureSpace(architecture)) == []

    def test_a_design_measured_for_something_else_is_left_to_be_run(self, tmp_path, architecture):
        # A record with none of the numbers this campaign is looking for teaches
        # the search nothing: it is not taken, and the design is run.
        workspace = self.write_result(
            tmp_path, {"_point.width": "8", "_point.depth": "2"}, metrics={"Cycles": 120}
        )
        settings = campaign_settings(objectives=[{"metric": "LUT_count", "goal": "min"}])
        evaluator = Evaluator(workspace, settings, settings.objective_list())
        assert evaluator.known(ArchitectureSpace(architecture)) == []

    def test_the_best_record_of_a_design_is_the_one_that_is_taken(self, tmp_path, architecture):
        # Measured the way a batch of the campaign is measured: a design is
        # worth what its best record is worth, against these objectives.
        import odatix.lib.results_schema as results_schema
        from odatix.workspace import Workspace

        workspace = Workspace(str(tmp_path))
        results = workspace.paths.result_path
        os.makedirs(results, exist_ok=True)
        records = [
            results_schema.make_record(
                {
                    results_schema.META_TYPE: results_schema.TYPE_FMAX,
                    results_schema.META_TOOL: "vivado",
                    results_schema.META_ARCHITECTURE: "Design",
                    results_schema.META_CONFIGURATION: "8bits_2deep",
                    results_schema.MAIN_DOMAIN_META_KEY: "8bits_2deep",
                    results_schema.META_TARGET: target,
                    "frequency": frequency,
                    "_point.width": "8",
                    "_point.depth": "2",
                },
                {"LUT_count": 40},
            )
            for target, frequency in (("xc7a100t", 180), ("xc7k70t", 320))
        ]
        results_schema.dump_results_file(os.path.join(results, "results_vivado.yml"), {}, records)

        known = self.evaluator(workspace).known(ArchitectureSpace(architecture))
        assert len(known) == 1
        assert known[0].metrics["frequency"] == 320


class _KnowingEvaluator(FakeEvaluator):
    """An evaluator that was handed designs the workspace already measured."""

    def __init__(self, objectives, cost, genomes=()):
        FakeEvaluator.__init__(self, objectives, cost)
        self.genomes = list(genomes)

    def known(self, space):
        found = []
        for genome in self.genomes:
            design = space.design(genome, project=False)
            metrics = self.cost(design)
            found.append(Evaluation(
                design, metrics=metrics, costs=self.objectives.costs(metrics), reused=True,
            ))
        return found


class TestAdopt:
    """What the campaign does with the designs it was given for free."""

    def cost(self, design):
        width = design.values["width"]
        depth = design.values["depth"]
        return {"speed": width * 10, "area": width * depth}

    def _campaign(self, architecture, tmp_path, genomes=((0, 0), (1, 1)), **overrides):
        from odatix.workspace import Workspace

        overrides.setdefault("search", {"strategy": "exhaustive", "budget": 4, "batch": 2, "seed": 1})
        settings = campaign_settings(**overrides)
        evaluator = _KnowingEvaluator(settings.objective_list(), self.cost, genomes)
        campaign = Campaign(Workspace(str(tmp_path)), architecture, settings, evaluator=evaluator)
        return campaign, evaluator

    def test_a_design_already_measured_is_not_run_again(self, architecture, tmp_path):
        campaign, evaluator = self._campaign(architecture, tmp_path)
        archive = campaign.run()
        entries = set(evaluator.evaluated)
        assert "Design/8bits_2deep" not in entries
        assert "Design/16bits_4deep" not in entries
        # Part of the answer all the same.
        assert len(archive) == 6

    def test_they_do_not_count_against_the_budget(self, architecture, tmp_path):
        # The budget says how many designs the exploration evaluates, and it
        # evaluated none of these.
        campaign, evaluator = self._campaign(architecture, tmp_path)
        campaign.run()
        assert len(evaluator.evaluated) == 4

    def test_an_exploration_started_again_does_not_count_them_as_its_own(
        self, architecture, tmp_path
    ):
        search = {"strategy": "exhaustive", "budget": 2, "batch": 2, "seed": 1}
        first, evaluator = self._campaign(architecture, tmp_path, search=search)
        first.run()
        assert len(evaluator.evaluated) == 2

        # Four designs are in the archive, two of which were given for free:
        # a run of four has two left to spend, not none.
        second, evaluator = self._campaign(
            architecture, tmp_path, genomes=(),
            search={"strategy": "exhaustive", "budget": 4, "batch": 2, "seed": 1},
        )
        second.run()
        assert len(evaluator.evaluated) == 2

    def test_a_campaign_can_be_told_to_search_from_nothing(self, architecture, tmp_path):
        campaign, evaluator = self._campaign(architecture, tmp_path, reuse_results=False)
        campaign.run()
        assert len(evaluator.evaluated) == 4
        assert "Design/8bits_2deep" in set(evaluator.evaluated)

    def test_overwrite_evaluates_them_again(self, architecture, tmp_path):
        # "Evaluate again what is already done" is what it asks for.
        campaign, evaluator = self._campaign(architecture, tmp_path, overwrite=True)
        campaign.run()
        assert "Design/8bits_2deep" in set(evaluator.evaluated)


class TestCampaignFiles:
    """
    Campaigns as files of their own: what is searched for is one file, how the
    exploration is run is another, and a campaign is named after its file.
    """

    def _workspace(self, tmp_path, architecture, **campaigns):
        import yaml

        from odatix.workspace import Workspace

        directory = tmp_path / "odatix_userconfig" / "dse_campaigns"
        directory.mkdir(parents=True, exist_ok=True)
        for name, body in campaigns.items():
            (directory / "{0}.yml".format(name)).write_text(yaml.safe_dump(body))
        return Workspace(str(tmp_path))

    def _body(self, **overrides):
        body = {
            "run": "fmax_synthesis",
            "tool": "vivado",
            "objectives": [{"metric": "speed", "goal": "max"}],
            "search": {"strategy": "random", "budget": 4, "batch": 2, "seed": 1},
            "architectures": ["Design"],
        }
        body.update(overrides)
        return body

    def test_a_campaign_is_named_after_its_file(self, architecture, tmp_path):
        from odatix.dse.campaign import Exploration
        from odatix.dse.settings import DseSettings

        workspace = self._workspace(tmp_path, architecture, area=self._body())
        settings = DseSettings.from_dict({"campaigns": ["area"]})
        campaign = Exploration(workspace, settings).campaigns()[0]

        assert campaign.name == "area"
        assert campaign.archive_path.endswith(os.path.join("dse", "area.yml"))

    def test_two_campaigns_on_one_architecture_keep_two_answers(self, architecture, tmp_path):
        # What used to make two searches one campaign was the space they shared:
        # a campaign is what is being looked for, and that is its own file.
        from odatix.dse.campaign import Exploration
        from odatix.dse.settings import DseSettings

        workspace = self._workspace(
            tmp_path, architecture,
            area=self._body(),
            power=self._body(objectives=[{"metric": "power", "goal": "min"}]),
        )
        settings = DseSettings.from_dict({"campaigns": ["area", "power"]})
        campaigns = Exploration(workspace, settings).campaigns()

        assert [campaign.name for campaign in campaigns] == ["area", "power"]
        assert len(set(campaign.archive_path for campaign in campaigns)) == 2

    def test_a_campaign_of_several_architectures_names_each_of_them(
        self, multi_domain_architecture, tmp_path
    ):
        from odatix.dse.campaign import Exploration
        from odatix.dse.settings import DseSettings

        workspace = self._workspace(
            tmp_path, multi_domain_architecture,
            both=self._body(architectures=["Design/*", "Design/* + corner/tt"]),
        )
        settings = DseSettings.from_dict({"campaigns": ["both"]})
        names = [campaign.name for campaign in Exploration(workspace, settings).campaigns()]

        assert names[0].startswith("both_") and names[1].startswith("both_")
        assert names[0] != names[1]

    def test_a_campaign_that_does_not_exist_says_which_ones_do(self, architecture, tmp_path):
        from odatix.dse.campaign import CampaignError, Exploration
        from odatix.dse.settings import DseSettings

        workspace = self._workspace(tmp_path, architecture, area=self._body())
        exploration = Exploration(workspace, DseSettings.from_dict({"campaigns": ["speed"]}))
        with pytest.raises(CampaignError) as error:
            exploration.check()
        assert "speed" in str(error.value) and "area" in str(error.value)

    def test_how_a_run_is_run_is_not_what_it_looks_for(self, architecture, tmp_path):
        # The campaign file says nothing about the daemon, and the settings file
        # says nothing about the objectives: a flag lands on the one it changes.
        from odatix.dse.campaign import Exploration
        from odatix.dse.settings import DseSettings

        workspace = self._workspace(tmp_path, architecture, area=self._body())
        settings = DseSettings.from_dict({"campaigns": ["area"], "nb_jobs": 6, "overwrite": True})
        campaign = Exploration(workspace, settings).campaigns()[0]

        assert campaign.settings.nb_jobs == 6
        assert campaign.settings.overwrite is True
        assert campaign.settings.run == "fmax_synthesis"

    def test_the_worker_is_handed_the_campaigns_the_command_line_resolved(
        self, architecture, tmp_path
    ):
        # The worker reads one file and nothing else: a campaign the command
        # line changed would otherwise be read again, unchanged, from its own.
        from odatix.dse.campaigns import resolve_campaigns
        from odatix.dse.campaign import Exploration
        from odatix.dse.driver import build_driver, driver_paths
        from odatix.dse.settings import DseSettings
        from odatix.workspace.settings import load_settings

        workspace = self._workspace(tmp_path, architecture, area=self._body())
        settings = DseSettings.from_dict({"campaigns": ["area"]})
        campaigns = resolve_campaigns(workspace, settings)
        campaigns[0].search["budget"] = 42

        build_driver(workspace, settings, "dse-test", campaigns=campaigns)
        written = load_settings(DseSettings, driver_paths(workspace, "dse-test")["settings_file"])

        assert written.campaign_names() == ["area"]
        assert written.campaign_entries()[0][1]["search"]["budget"] == 42
        campaign = Exploration(workspace, written).campaigns()[0]
        assert campaign.name == "area"
        # The budget of a campaign is never larger than the space it searches.
        assert campaign.search.budget == 42


class TestDriver:
    """The exploration, handed to the daemon as a job like any other."""

    def _workspace(self, tmp_path):
        from odatix.workspace import Workspace

        return Workspace(str(tmp_path))

    def test_the_driver_is_a_job_that_takes_no_slot_and_stays_in_sight(self, architecture, tmp_path):
        from odatix.dse.driver import build_driver

        settings = campaign_settings()
        handler = build_driver(self._workspace(tmp_path), settings, "dse-test")
        job = handler.job_list[0]

        assert job.is_driver
        assert not job.takes_a_slot
        assert job.pinned
        assert handler.used_slots == 0

    def test_the_driver_runs_the_search_in_the_session_it_lives_in(self, architecture, tmp_path):
        from odatix.dse.driver import build_driver, driver_paths

        settings = campaign_settings()
        workspace = self._workspace(tmp_path)
        handler = build_driver(workspace, settings, "dse-test")
        job = handler.job_list[0]
        paths = driver_paths(workspace, "dse-test")

        assert "--worker" in job.command
        assert "--session" in job.command and "dse-test" in job.command
        # What the command line resolved is what the worker reads back.
        assert os.path.isfile(paths["settings_file"])
        assert job.progress_file == paths["progress_file"]

    def test_the_driver_reports_the_progress_of_the_whole_exploration(self, architecture, tmp_path):
        from odatix.dse.campaign import Exploration
        from odatix.dse.driver import PROGRESS_PATTERN
        from odatix.lib.parallel_job_handler.job import DRIVER_KIND, ParallelJob

        progress_file = str(tmp_path / "progress.txt")
        exploration = Exploration(
            self._workspace(tmp_path), campaign_settings(), progress_file=progress_file
        )
        exploration._total = 20
        exploration.report_progress(5)

        job = ParallelJob(
            process=None, command="", directory=".", generate_rtl=False, generate_command="",
            target="", arch="", display_name="exploration", status_file="",
            progress_file=progress_file, tmp_dir=".", log_size_limit=10,
            kind=DRIVER_KIND, progress_pattern=PROGRESS_PATTERN,
        )
        assert job.get_progress() == 25

    def test_a_job_reads_its_progress_with_its_own_rules(self):
        # A daemon running the jobs of two commands at once must not read the
        # progress of one with the pattern of the other.
        from odatix.lib.parallel_job_handler.job import ParallelJob

        before = (ParallelJob.progress_file_pattern, ParallelJob.status_file_pattern)
        try:
            ParallelJob.set_patterns(re.compile(r"nothing here"))
            job = ParallelJob(
                process=None, command="", directory=".", generate_rtl=False, generate_command="",
                target="", arch="", display_name="job", status_file="", progress_file="",
                tmp_dir=".", log_size_limit=10, progress_pattern=r"^\s*([0-9]+)\s*$",
            )
            assert job.patterns()[0].pattern == r"^\s*([0-9]+)\s*$"
            assert ParallelJob.progress_file_pattern.pattern == "nothing here"
        finally:
            ParallelJob.set_patterns(*before)

    def test_the_log_of_the_driver_starts_with_the_search(self, architecture, tmp_path):
        # The banner belongs to the terminal the command was typed in: the log
        # of the driver is read for what the search learned.
        from odatix.dse.driver import build_driver

        handler = build_driver(self._workspace(tmp_path), campaign_settings(), "dse-test")
        assert "--nobanner" in handler.job_list[0].command

    def test_the_worker_does_not_ask_again_what_the_terminal_asked(
        self, architecture, tmp_path, monkeypatch, capsys
    ):
        # The plan was shown and confirmed where a user could answer. Saying it
        # again in the log, above the same line the campaign prints, is noise.
        from odatix.dse.campaign import Exploration

        settings = campaign_settings()
        exploration = Exploration(self._workspace(tmp_path), settings)
        monkeypatch.setattr(exploration, "check", lambda: [])
        monkeypatch.setattr(
            exploration, "confirm",
            lambda campaigns: pytest.fail("the worker asked again"),
        )
        exploration.run(confirm=False)

    def test_what_a_batch_says_about_itself_stays_out_of_the_search_log(self, capsys):
        # A batch says as much as a whole command does, once per batch, and
        # would bury the only thing the log is read for.
        from odatix.dse.evaluation import _details, _quiet

        with _quiet() as said:
            print("Preparing jobs: 8/8 prepared")
        assert capsys.readouterr().out == ""
        # Unless the batch did not run: then it is the only explanation there is.
        assert "8/8 prepared" in _details(said.getvalue())

    def test_two_explorations_at_once_keep_their_files_apart(self, architecture, tmp_path):
        # A session is what lets two explorations run at the same time; they
        # would otherwise hand each other their settings.
        from odatix.dse.driver import driver_paths

        workspace = self._workspace(tmp_path)
        first = driver_paths(workspace, "dse-1")
        second = driver_paths(workspace, "dse-2")
        assert first["directory"] != second["directory"]
        assert first["progress_file"] != second["progress_file"]


######################################
# What the explorer is given
######################################

class _ExportedDesign(object):
    """A design as the export reads it, without a whole architecture behind it."""

    def __init__(self, configuration, frequency=None, genome=(0,)):
        self.architecture = "Design"
        self.entry = "Design/" + configuration
        self.label = self.entry
        self.configuration = configuration
        self.configurations = {"__main__": configuration, "corner": "tt"}
        self.values = {"width": 8}
        self.genome = tuple(genome)
        self.frequency = frequency
        self.toolchain = None
        self.chose_toolchain = False


def _exported_archive(tmp_path, constraints=None):
    """A campaign of two batches, archived and exported, as a fixture would."""
    objectives = Objectives.from_list(
        [{"metric": "speed", "goal": "max"}, "area"], constraints
    )
    result_path = str(tmp_path / "results")
    archive = Archive(
        os.path.join(result_path, "dse", "Design.yml"), "Design", objectives,
        strategy="genetic", space_size=32,
        results_path=os.path.join(result_path, "results_dse_Design.yml"),
    )

    def made(configuration, speed, area, batch, source=None):
        metrics = {"speed": speed, "area": area}
        # One genome per design, as in a real campaign: the bit width says which.
        genome = (int(configuration[:2]) // 8,)
        return Evaluation(
            _ExportedDesign(configuration, genome=genome), metrics=metrics,
            costs=objectives.costs(metrics),
            batch=batch, source=source,
        )

    source = {"type": "fmax_synthesis", "tool": "vivado", "target": "xc7a100t",
              "architecture": "Design", "configuration": "08bits", "main": "08bits"}
    archive.improved_by([made("08bits", 400, 300, 1, source=source), made("16bits", 300, 500, 1)])

    failed = made("64bits", 0, 0, 2)
    failed.costs, failed.note = None, "the run produced no result for this design"
    archive.improved_by([made("32bits", 500, 900, 2), failed])
    archive.save(units={"speed": "MHz"})
    return archive, result_path


class TestExport:
    def test_the_designs_of_a_campaign_are_exported_as_a_results_source(self, tmp_path):
        # The explorer knows nothing about explorations: what it charts is
        # results files, so a campaign writes one.
        import odatix.lib.results_schema as results_schema

        archive, _ = _exported_archive(tmp_path)
        exported = results_schema.load_results_file(archive.results_path)
        assert exported.schema_detected == results_schema.FORMAT_V2
        assert exported.units == {"speed": "MHz"}
        # The design that produced nothing has nothing to chart, and is left out.
        assert len(exported.records) == 3

    def test_an_exported_record_says_it_is_on_the_front(self, tmp_path):
        # Which is what makes "color the points by whether they are the answer"
        # an ordinary chart rather than a feature.
        import odatix.lib.results_schema as results_schema
        from odatix.dse.export import META_BATCH, META_DSE, META_FRONT

        archive, _ = _exported_archive(tmp_path)
        exported = results_schema.load_results_file(archive.results_path)
        by_configuration = {
            record["meta"]["configuration"]: record["meta"] for record in exported.records
        }
        assert by_configuration["08bits"][META_FRONT] == "yes"
        # Slower *and* bigger: it never was an answer.
        assert by_configuration["16bits"][META_FRONT] == "no"
        assert by_configuration["32bits"][META_BATCH] == 2
        assert by_configuration["08bits"][META_DSE] == "Design"

    def test_the_export_keeps_what_the_design_was_run_as(self, tmp_path):
        # The numbers came out of a run: the record says which one, so that the
        # exported designs sit in the same dimensions as everything else.
        import odatix.lib.results_schema as results_schema

        archive, _ = _exported_archive(tmp_path)
        exported = results_schema.load_results_file(archive.results_path)
        meta = next(record["meta"] for record in exported.records
                    if record["meta"]["configuration"] == "08bits")
        assert meta["tool"] == "vivado"
        assert meta["target"] == "xc7a100t"
        # And a design read from no record at all is still described.
        other = next(record["meta"] for record in exported.records
                     if record["meta"]["configuration"] == "16bits")
        assert other["architecture"] == "Design"
        assert other["main"] == "16bits"
        assert other["corner"] == "tt"

    def test_a_design_pushed_off_the_front_stops_being_marked_as_on_it(self, tmp_path):
        # The file is rewritten whole rather than merged into: which designs are
        # the answer is a property of the campaign as it stands.
        import odatix.lib.results_schema as results_schema
        from odatix.dse.export import META_FRONT

        archive, _ = _exported_archive(tmp_path)
        objectives = archive.objectives
        metrics = {"speed": 600, "area": 100}
        archive.improved_by([Evaluation(
            _ExportedDesign("crusher"), metrics=metrics, costs=objectives.costs(metrics), batch=3,
        )])
        archive.save()

        exported = results_schema.load_results_file(archive.results_path)
        front = {record["meta"]["configuration"]: record["meta"][META_FRONT]
                 for record in exported.records}
        assert front["crusher"] == "yes"
        assert front["08bits"] == "no"
        assert front["32bits"] == "no"

    def test_a_constrained_campaign_exports_whether_a_design_meets_them(self, tmp_path):
        import odatix.lib.results_schema as results_schema
        from odatix.dse.export import META_FEASIBLE

        archive, _ = _exported_archive(tmp_path, Constraints.from_list([{"metric": "area", "max": 400}]))
        exported = results_schema.load_results_file(archive.results_path)
        feasible = {record["meta"]["configuration"]: record["meta"][META_FEASIBLE]
                    for record in exported.records}
        assert feasible["08bits"] == "yes"
        assert feasible["32bits"] == "no"

    def test_the_archive_says_how_the_front_grew_batch_after_batch(self, tmp_path):
        # A front reached in three batches and one reached in thirty are not the
        # same answer, and neither is one that stopped growing ten batches ago.
        import yaml

        archive, _ = _exported_archive(tmp_path)
        with open(archive.path) as f:
            written = yaml.safe_load(f.read())
        history = written["history"]
        assert [entry["batch"] for entry in history] == [1, 2]
        assert [entry["front"] for entry in history] == [1, 2]
        # Measured against one corner, so two batches can be compared at all.
        assert history[1]["hypervolume"] >= history[0]["hypervolume"]
        # A batch counts every design it spent, including the ones that failed.
        assert history[1]["evaluated"] == 4
        assert history[1]["measured"] == 3

    def test_a_campaign_picked_up_again_still_knows_which_batch_found_what(self, tmp_path):
        # The batch is written down, so an exploration that was interrupted does
        # not come back as one big first batch.
        archive, result_path = _exported_archive(tmp_path)

        class _Space(object):
            lengths = (9,)

            def design(self, genome):
                return _ExportedDesign("restored", genome=genome)

        again = Archive(archive.path, "Design", archive.objectives)
        again.restore(_Space())
        assert sorted(evaluation.batch for evaluation in again.evaluations) == [1, 1, 2, 2]

    def test_the_explorer_reads_the_campaigns_of_a_workspace(self, tmp_path):
        from odatix.explorer.core.dse import CampaignStore

        archive, result_path = _exported_archive(tmp_path)
        campaigns = CampaignStore().campaigns(result_path)
        assert [campaign.name for campaign in campaigns] == ["Design"]

        campaign = campaigns[0]
        assert campaign.error is None
        assert campaign.strategy == "genetic"
        assert campaign.objectives == [
            {"metric": "speed", "goal": "max"}, {"metric": "area", "goal": "min"}
        ]
        counts = campaign.counts()
        assert counts["front"] == 2
        assert counts["evaluated"] == 4
        assert counts["failed"] == 1
        assert counts["batches"] == 2

    def test_an_archive_that_cannot_be_read_comes_back_carrying_its_error(self, tmp_path):
        # "Being written right now" and "broken" look the same for a moment, and
        # a page that made the campaign vanish would flicker it away on saves.
        from odatix.explorer.core.dse import CampaignStore

        _, result_path = _exported_archive(tmp_path)
        with open(os.path.join(result_path, "dse", "Broken.yml"), "w") as f:
            f.write("architecture: [unclosed\n")

        campaigns = {campaign.name: campaign for campaign in CampaignStore().campaigns(result_path)}
        assert campaigns["Broken"].error
        assert campaigns["Design"].error is None


######################################
# Exploring a workflow
######################################

WORKFLOW = """\
    sources:
      path: examples/codec
    use_parameters: No

    tasks:
      - name: main
        commands:
          - python3 encode.py --quality ${quality} --block_size ${block_size}

    variables:
      quality:
        type: list
        settings:
          list: [10, 50, 90]
      block_size:
        type: list
        settings:
          list: [4, 8]
"""


@pytest.fixture
def workflow(tmp_path):
    """A workflow whose two knobs describe six designs."""
    from odatix.workspace import Workspace

    root = tmp_path / "odatix_userconfig" / "workflows"
    root.mkdir(parents=True)
    write_architecture(root, "Codec", WORKFLOW)
    (tmp_path / "odatix.yml").write_text("workflow_path: odatix_userconfig/workflows\n")
    return Workspace(str(tmp_path)).workflows["Codec"]


class TestWorkflows:
    """
    An exploration whose evaluations are "odatix workflow" runs.

    A workflow is swept exactly like an architecture, so nothing about the
    search changes: what changes is where a name is looked up, which results
    file the numbers come from, and that no eda tool runs anything.
    """

    def settings(self, **overrides):
        arguments = {
            "run": "workflow",
            "tool": "",
            "objectives": [{"metric": "bitrate", "goal": "min"}, {"metric": "psnr", "goal": "max"}],
            "architectures": ["Codec"],
        }
        arguments.update(overrides)
        return campaign_settings(**arguments)

    def test_the_domains_of_a_workflow_are_axes_although_they_write_no_file(self, workflow):
        # A workflow substitutes its knobs into its commands, not into its
        # sources: "use_parameters: no" says where they go, not that there is
        # nothing to search.
        space = ArchitectureSpace(workflow)
        assert sorted(axis.label for axis in space.axes) == ["block_size", "quality"]
        assert space.size() == 6

    def test_a_workflow_exploration_reads_the_workflow_results_file(self):
        assert self.settings().result_tools() == ["workflow"]
        assert self.settings(run="fmax_synthesis", tool="vivado").result_tools() == ["vivado"]

    def test_the_names_of_a_workflow_campaign_are_workflows(self, tmp_path, workflow):
        from odatix.workspace import Workspace

        workspace = Workspace(str(tmp_path))
        assert self.settings().designs(workspace)["Codec"].kind == "workflow"
        assert self.settings(run="fmax_synthesis").designs(workspace).entry_class.kind == "architecture"

    def test_a_workflow_record_is_the_design_it_measured(self, tmp_path, workflow):
        # A synthesis record names what it ran under "architecture" and a
        # workflow record under "workflow". The evaluator has to read both as
        # the same thing, or a campaign never finds what its own runs produced.
        import odatix.lib.results_schema as results_schema
        from odatix.workspace import Workspace

        workspace = Workspace(str(tmp_path))
        results = workspace.paths.result_path
        os.makedirs(results, exist_ok=True)
        results_schema.dump_results_file(
            os.path.join(results, "results_workflow.yml"), {},
            [results_schema.make_record(
                {
                    results_schema.META_TYPE: results_schema.TYPE_WORKFLOW,
                    results_schema.META_WORKFLOW: "Codec",
                    results_schema.META_CONFIGURATION: "quality/50+block_size/8",
                    results_schema.MAIN_DOMAIN_META_KEY: "Codec",
                    "quality": "50",
                    "block_size": "8",
                    "_point.quality": "50",
                    "_point.block_size": "8",
                },
                {"bitrate": 1.2, "psnr": 38.0},
            )],
        )

        settings = self.settings()
        evaluator = Evaluator(workspace, settings, settings.objective_list())
        known = evaluator.known(ArchitectureSpace(workflow))
        assert len(known) == 1
        assert known[0].reused
        assert known[0].metrics["psnr"] == 38.0
        assert known[0].design.values == {"quality": 50, "block_size": 8}
