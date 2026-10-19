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
The combinations a design space does not hold.

A parameter domain could already rule out its own combinations. What is tested
here is everything the domains cannot say alone: one domain against another, a
domain against the topology it runs in, and what a search does with a rule that
says which of two identical designs is the one to run.
"""

import os
import textwrap

import pytest

from odatix.lib.expressions import ExpressionError, Ref, evaluate, evaluate_bool, normalize
from odatix.workspace.attributes import Attributes, parse_attributes, read_value
from odatix.workspace.exclusions import (
    DEFAULT_APPLIED,
    DOMINATED,
    DUPLICATE,
    ILLEGAL,
    ExclusionSet,
    context,
    parse_exclusions,
)
from odatix.workspace.selection import ExclusionFilter, expand, filter_excluded
from odatix.dse.space import ArchitectureSpace, DomainSelection


######################################
# The expression language
######################################

class TestExpressions:
    def test_a_name_is_written_with_a_dollar(self):
        assert evaluate("$width * 2", {"width": 8}) == 16
        assert evaluate("${width} * 2", {"width": 8}) == 16

    def test_a_power_is_written_the_way_a_settings_file_writes_it(self):
        assert evaluate("2^$n", {"n": 5}) == 32
        assert normalize("2^$n") == "2**n"

    def test_a_domain_is_a_name_and_a_record_at_once(self):
        values = {"Overlap": Ref("On", {"p_overlap": 1})}
        assert evaluate_bool("$Overlap == 'On'", values)
        assert evaluate_bool("$Overlap.p_overlap == 1", values)

    def test_a_name_nothing_defines_is_false_rather_than_broken(self):
        # One exclusion is written for a family of architectures that do not all
        # have the same domains. The ones that do not have it are not rejected.
        assert not evaluate_bool("$Fwd.p_fwd_pw == 0", {})
        assert not evaluate_bool("$Fwd == 'anything'", {})
        assert evaluate_bool("not defined($Fwd)", {})

    def test_a_domain_whose_name_python_cannot_spell_is_still_readable(self):
        values = {"my-domain": Ref("On", {"x": 3})}
        assert evaluate_bool("$my-domain.x == 3", values)

    def test_a_broken_expression_says_so(self):
        with pytest.raises(ExpressionError):
            evaluate("$width +", {"width": 8})

    def test_a_name_is_matched_against_a_pattern(self):
        values = {"config": Ref("P-IF1RF1MA1", {})}
        assert evaluate_bool("match($config, 'P-*RF1*')", values)
        assert not evaluate_bool("match($config, 'P-*WB1*')", values)
        assert evaluate_bool("matches($config, 'RF[0-9]')", values)


######################################
# What is known about a configuration
######################################

class TestAttributes:
    def test_values_are_read_off_the_name(self):
        attributes = Attributes(
            defaults={"stage_EX": 0, "stage_RF": 0},
            from_name=[r"EX(?P<stage_EX>\d+)", r"RF(?P<stage_RF>\d+)"],
        )
        assert attributes.of("P-IF1ID1EX2MA1WB1")["stage_EX"] == 2
        # What no group matched stays at its default: a topology without an RF
        # barrier does not have a missing attribute, it has a zero.
        assert attributes.of("P-IF1ID1EX2MA1WB1")["stage_RF"] == 0

    def test_values_are_read_off_the_content(self):
        attributes = Attributes(from_content=[r"p_stage_EX\s*=\s*(?P<stage_EX>\d+)"])
        assert attributes.of("anything", "p_stage_EX = 3\n")["stage_EX"] == 3

    def test_the_variables_of_the_rules_have_the_last_word(self):
        attributes = Attributes(defaults={"width": 0}, from_name=[r"(?P<width>\d+)bits"])
        assert attributes.of("8bits", None, {"width": 32})["width"] == 32

    def test_a_configuration_a_pattern_cannot_reach_is_written_out(self):
        attributes = parse_attributes({"attributes": {"values": {"P-IF1MA1": {"legacy": 1}}}})
        assert attributes.of("P-IF1MA1")["legacy"] == 1
        assert "legacy" not in attributes.of("P-IF1EX1MA1")

    def test_what_reads_as_a_number_is_compared_as_one(self):
        assert read_value("12") == 12
        assert read_value("Yes") is True
        assert read_value("P-IF1") == "P-IF1"


######################################
# Reading a block
######################################

class TestParsing:
    def test_a_list_declares_the_rules_themselves(self):
        exclusions = parse_exclusions({"exclusions": [
            {"when": "$a == 1", "kind": "illegal"},
            {"when": "$b == 1", "kind": "dominated"},
        ]})
        assert len(exclusions.rules) == 2
        # A dominated design is dominated for a question: it takes a campaign to
        # rule it out, so it is not applied by default.
        assert exclusions.applied == DEFAULT_APPLIED
        assert len(exclusions) == 1

    def test_a_mapping_also_says_what_to_apply(self):
        exclusions = parse_exclusions({"exclusions": {
            "apply": ["illegal", "duplicate", "dominated"],
            "ignore": ["late-idea"],
            "rules": [
                {"id": "late-idea", "when": "$a == 1", "kind": "dominated"},
                {"id": "kept", "when": "$b == 1", "kind": "dominated"},
            ],
        }})
        assert [rule.id for rule in exclusions] == ["kept"]

    def test_a_bare_expression_says_what_has_to_be_true(self):
        # Written the way a domain writes its own constraints.
        exclusions = parse_exclusions({"exclusions": ["$a <= $b"]})
        assert exclusions.check(context("A", {}, {"a": 2, "b": 1})) is not None
        assert exclusions.check(context("A", {}, {"a": 1, "b": 2})) is None

    def test_a_campaign_decides_what_is_applied_and_the_architecture_what_exists(self):
        architecture = parse_exclusions({"exclusions": [
            {"id": "broken", "when": "$a == 1", "kind": "illegal"},
            {"id": "slow", "when": "$b == 1", "kind": "dominated"},
        ]})
        campaign = parse_exclusions({"apply": ["illegal", "duplicate", "dominated"]})
        merged = architecture.merge(campaign)
        assert sorted(rule.id for rule in merged) == ["broken", "slow"]
        # And a campaign that says nothing leaves the choice where it was.
        assert sorted(rule.id for rule in architecture.merge(parse_exclusions({}))) == ["broken"]

    def test_a_rule_that_cannot_be_evaluated_is_reported_and_rejects_nothing(self):
        exclusions = parse_exclusions({"exclusions": [{"when": "$a +", "kind": "illegal"}]})
        assert exclusions.check(context("A", {}, {"a": 1})) is None
        errors = exclusions.take_errors()
        assert len(errors) == 1 and "could not be evaluated" in errors[0]
        # Reported once, not once per point.
        assert exclusions.check(context("A", {}, {"a": 1})) is None
        assert exclusions.take_errors() == []


######################################
# What an exclusion reads
######################################

class TestContext:
    def test_a_domain_is_read_by_its_name_and_by_its_values(self):
        values = context(
            "AsteRISC-P",
            {"__main__": "P-IF1MA1", "Overlap": "On"},
            {"p_rf_sp": 1, "Overlap.p_overlap": 1},
        )
        assert evaluate_bool("$architecture == 'AsteRISC-P'", values)
        assert evaluate_bool("$config == 'P-IF1MA1'", values)
        assert evaluate_bool("$Overlap == 'On' and $Overlap.p_overlap == 1", values)
        # A variable of the main domain is written without saying so.
        assert evaluate_bool("$p_rf_sp == 1", values)
        assert evaluate_bool("$main.p_rf_sp == 1", values)

    def test_the_attributes_of_a_hand_written_configuration_are_read(self):
        attributes = {"__main__": Attributes(defaults={"stage_RF": 0}, from_name=[r"RF(?P<stage_RF>\d+)"])}
        values = context("A", {"__main__": "P-IF1RF1MA1"}, {}, attributes=attributes)
        assert evaluate_bool("$config.stage_RF == 1", values)


######################################
# What a search does with them
######################################

ARCHITECTURE = """\
    rtl_path: "rtl"
    top_level_file: "top.v"
    top_level_module: "top"
    clock_signal: "clk"
    use_parameters: Yes
    start_delimiter: "#("
    stop_delimiter: ")("
    param_target_file: "rtl/top.v"

    configurations:
      name: "${width}bits"
      template: "parameter WIDTH = ${width};"

    variables:
      width:
        type: list
        settings:
          list: [8, 16, 32]
"""

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


def write_architecture(root, name, settings, domains=None):
    path = os.path.join(str(root), name)
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, "_settings.yml"), "w", encoding="utf-8") as f:
        f.write(textwrap.dedent(settings))
    for domain, content in (domains or {}).items():
        domain_path = os.path.join(path, domain)
        os.makedirs(domain_path, exist_ok=True)
        with open(os.path.join(domain_path, "_settings.yml"), "w", encoding="utf-8") as f:
            f.write(textwrap.dedent(content))
    return path


def workspace_with(tmp_path, settings, domains=None):
    from odatix.workspace import Workspace

    root = tmp_path / "odatix_userconfig" / "architectures"
    root.mkdir(parents=True, exist_ok=True)
    write_architecture(root, "Design", settings, domains=domains)
    (tmp_path / "odatix.yml").write_text("arch_path: odatix_userconfig/architectures\n", encoding="utf-8")
    return Workspace(str(tmp_path))


ONE_CORNER_ONLY = ARCHITECTURE + """
    exclusions:
      - id: only-the-typical-corner-is-characterized
        when: "$corner != 'tt'"
        kind: illegal
"""

CROSS_DOMAIN = ARCHITECTURE + """
    exclusions:
      - id: wide-is-not-worth-a-slow-corner
        when: "$width == 32 and $corner == 'ss'"
        kind: illegal
        message: "it does not close timing"
"""


class TestSearchedSpace:
    def test_a_cross_domain_exclusion_names_no_design(self, tmp_path):
        architecture = workspace_with(tmp_path, CROSS_DOMAIN, {"corner": CORNERS}).architectures["Design"]
        space = ArchitectureSpace(architecture, selection=DomainSelection.parse("Design+corner/*"))
        assert space.size() == 9
        designs = [space.design(genome) for genome in space.genomes()]
        kept = sorted(design.entry for design in designs if design is not None)
        assert "Design/32bits+corner/ss" not in kept
        assert len(kept) == 8
        assert space.feasible_size() == (8, True)

    def test_a_duplicate_folds_the_space_instead_of_emptying_it(self, tmp_path):
        # Below 32 bits the corner is not wired at all: every corner describes
        # the same hardware, so one of them is the one to run.
        settings = ARCHITECTURE + """
    exclusions:
      - id: corner-is-ignored-when-narrow
        when: "$width < 32"
        require: "$corner == 'tt'"
        kind: duplicate
"""
        architecture = workspace_with(tmp_path, settings, {"corner": CORNERS}).architectures["Design"]
        space = ArchitectureSpace(architecture, selection=DomainSelection.parse("Design+corner/*"))
        designs = [space.design(genome) for genome in space.genomes()]
        assert all(design is not None for design in designs)
        # Nothing was thrown away: the points that named the same hardware were
        # moved onto the one configuration that stands for it.
        kept = sorted(set(design.entry for design in designs))
        assert kept == [
            "Design/16bits+corner/tt",
            "Design/32bits+corner/ff",
            "Design/32bits+corner/ss",
            "Design/32bits+corner/tt",
            "Design/8bits+corner/tt",
        ]

    def test_a_dominated_exclusion_waits_for_a_campaign_to_ask(self, tmp_path):
        settings = ARCHITECTURE + """
    exclusions:
      - id: narrow-and-slow
        when: "$width == 8 and $corner == 'ss'"
        kind: dominated
"""
        architecture = workspace_with(tmp_path, settings, {"corner": CORNERS}).architectures["Design"]
        selection = DomainSelection.parse("Design+corner/*")
        space = ArchitectureSpace(architecture, selection=selection)
        assert space.feasible_size() == (9, True)

        asked = ArchitectureSpace(
            architecture, selection=selection,
            exclusions=parse_exclusions({"apply": ["illegal", "duplicate", "dominated"]}),
        )
        assert asked.feasible_size() == (8, True)

    def test_an_exclusion_reads_the_attributes_of_a_hand_written_domain(self, tmp_path):
        topologies = """\
            use_parameters: Yes
            start_delimiter: "// topo"
            stop_delimiter: "// end"
            param_target_file: "rtl/top.v"

            attributes:
              defaults: {stage_EX: 0}
              from_name: "EX(?P<stage_EX>[0-9]+)"
        """
        settings = ARCHITECTURE + """
    exclusions:
      - id: sequential-shifter-in-a-deep-pipeline
        when: "$topo.stage_EX >= 2 and $width == 8"
        kind: dominated
        message: "the shifter already pays in cycles what the stages buy in period"
"""
        workspace = workspace_with(tmp_path, settings, {"topo": topologies})
        domain = tmp_path / "odatix_userconfig" / "architectures" / "Design" / "topo"
        (domain / "P-EX1MA1.txt").write_text("stage = 1\n", encoding="utf-8")
        (domain / "P-EX2MA1.txt").write_text("stage = 2\n", encoding="utf-8")

        architecture = workspace.architectures["Design"]
        space = ArchitectureSpace(
            architecture, selection=DomainSelection.parse("Design+topo/*"),
            exclusions=parse_exclusions({"apply": ["illegal", "duplicate", "dominated"]}),
        )
        kept = sorted(
            design.entry for design in (space.design(genome) for genome in space.genomes())
            if design is not None
        )
        assert "Design/8bits+topo/P-EX2MA1" not in kept
        assert "Design/8bits+topo/P-EX1MA1" in kept


######################################
# What a sweep does with them
######################################

class TestSweptSpace:
    def test_a_wildcard_does_not_expand_to_a_combination_that_does_not_exist(self, tmp_path):
        workspace_with(tmp_path, CROSS_DOMAIN, {"corner": CORNERS})
        root = str(tmp_path / "odatix_userconfig" / "architectures")
        messages = []
        expanded = expand(["Design/*+corner/*"], root, messages)
        assert "Design/32bits+corner/ss" not in expanded
        assert len(expanded) == 8
        assert any("not part of the design space" in message.text for message in messages)
        assert all(message.level == "note" for message in messages)

    def test_what_a_rule_left_out_is_said_once_rather_than_once_per_point(self, tmp_path):
        # A rule may take tens of thousands of combinations out of a sweep at
        # once. Saying so per combination buries what the run is about under its
        # own explanation, so each rule is worth one note and a count.
        workspace_with(tmp_path, ONE_CORNER_ONLY, {"corner": CORNERS})
        root = str(tmp_path / "odatix_userconfig" / "architectures")
        messages = []
        expanded = expand(["Design/*+corner/*"], root, messages)
        assert len(expanded) == 3
        assert len(messages) == 1
        assert "6 combinations are not part of the design space" in messages[0].text
        assert messages[0].hints and "For example" in messages[0].hints[0]

    def test_a_single_left_out_point_is_still_named(self, tmp_path):
        workspace_with(tmp_path, CROSS_DOMAIN, {"corner": CORNERS})
        root = str(tmp_path / "odatix_userconfig" / "architectures")
        messages = []
        expand(["Design/*+corner/*"], root, messages)
        assert len(messages) == 1
        assert '"Design/32bits+corner/ss"' in messages[0].text

    def test_a_design_space_is_left_in_the_order_its_wildcards_produced_it(self, tmp_path):
        # Sorting a quarter of a million entries by natural order costs more
        # than working out which of them exist, and the product already comes
        # out in that order.
        from odatix.workspace import selection

        workspace_with(tmp_path, ARCHITECTURE, {"corner": CORNERS})
        root = str(tmp_path / "odatix_userconfig" / "architectures")
        entries = expand(["Design/*+corner/*"], root, [])
        assert len(entries) == 9

        limit = selection.NATURAL_ORDER_LIMIT
        selection.NATURAL_ORDER_LIMIT = 2
        try:
            unsorted = expand(["Design/*+corner/*"], root, [])
        finally:
            selection.NATURAL_ORDER_LIMIT = limit
        assert sorted(unsorted) == sorted(entries)
        # Each wildcard is resolved in natural order and the product preserves
        # it, which is what makes leaving the whole out of a sort harmless.
        assert unsorted == entries

    def test_asking_for_one_by_name_is_an_error_rather_than_a_silence(self, tmp_path):
        workspace_with(tmp_path, CROSS_DOMAIN, {"corner": CORNERS})
        root = str(tmp_path / "odatix_userconfig" / "architectures")
        messages = []
        expanded = expand(["Design/32bits+corner/ss"], root, messages)
        assert expanded == []
        assert [message.level for message in messages] == ["error"]

    def test_an_architecture_without_exclusions_is_swept_as_it_always_was(self, tmp_path):
        workspace_with(tmp_path, ARCHITECTURE, {"corner": CORNERS})
        root = str(tmp_path / "odatix_userconfig" / "architectures")
        messages = []
        assert len(expand(["Design/*+corner/*"], root, messages)) == 9
        assert messages == []

    def test_a_selection_is_filtered_on_its_own_too(self, tmp_path):
        workspace_with(tmp_path, CROSS_DOMAIN, {"corner": CORNERS})
        root = str(tmp_path / "odatix_userconfig" / "architectures")
        kept = filter_excluded(["Design/8bits+corner/ss", "Design/32bits+corner/ss"], root)
        assert kept == ["Design/8bits+corner/ss"]

    def test_the_filter_of_an_architecture_that_declares_nothing_costs_nothing(self, tmp_path):
        workspace_with(tmp_path, ARCHITECTURE)
        root = str(tmp_path / "odatix_userconfig" / "architectures")
        assert ExclusionFilter(root, "Design").empty
