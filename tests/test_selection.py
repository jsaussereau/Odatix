"""
Tests for odatix.workspace.selection: how a run selection is written, and what
its wildcards match on disk.

This is the grammar every run goes through (architectures, workflows, and the
configurations a simulation runs on), so what it accepts is a contract.
"""

import pytest

from odatix.workspace import selection


######################################
# Reading one entry
######################################

class TestParse:
    def test_architecture_and_configuration(self):
        request = selection.parse("counter/08bits")
        assert request.entry == "counter"
        assert request.configuration == "08bits"
        assert request.path == "counter/08bits"
        assert request.domains == []
        assert request.has_configuration

    def test_architecture_alone_selects_no_configuration(self):
        request = selection.parse("counter")
        assert request.entry == "counter"
        assert request.configuration == "counter"
        assert not request.has_configuration
        assert str(request) == "counter"

    def test_parameter_domains(self):
        request = selection.parse("counter/08bits+corner/tt+voltage/high")
        assert request.path == "counter/08bits"
        assert request.domains == ["corner/tt", "voltage/high"]

    def test_spaces_are_ignored(self):
        request = selection.parse("counter/08bits + corner/tt")
        assert request.path == "counter/08bits"
        assert request.domains == ["corner/tt"]

    def test_extension_is_dropped_and_reported(self):
        request = selection.parse("counter/08bits.txt")
        assert request.path == "counter/08bits"
        assert [message.level for message in request.notes] == ["note"]

    def test_trailing_slash_is_dropped(self):
        assert selection.parse("counter/08bits/").path == "counter/08bits"

    def test_round_trip(self):
        for text in ("counter/08bits", "counter", "counter/08bits+corner/tt"):
            assert str(selection.parse(text)) == text


class TestNaming:
    def test_display_name_without_domains(self):
        assert selection.parse("counter/08bits").display_name() == "counter/08bits"

    def test_display_name_lists_the_domains(self):
        request = selection.parse("counter/08bits+corner/tt")
        assert request.display_name() == "counter/08bits [corner:tt]"

    def test_display_name_names_the_target_when_there_are_several(self):
        request = selection.parse("counter/08bits")
        assert request.display_name("fpga1", only_one_target=False) == "counter/08bits (fpga1)"

    def test_work_dirname_without_domains(self):
        assert selection.parse("counter/08bits").work_dirname == "08bits"

    def test_work_dirname_tells_the_domains_apart(self):
        assert selection.parse("counter/08bits+corner/tt").work_dirname == "08bits+corner_tt"


######################################
# Wildcards
######################################

@pytest.fixture
def architectures(tmp_path):
    """An architecture with three configurations and one parameter domain."""
    counter = tmp_path / "counter"
    (counter / "corner").mkdir(parents=True)
    for name in ("04bits", "08bits", "16bits"):
        (counter / (name + ".txt")).write_text("WIDTH = 8")
    for name in ("tt", "ff"):
        (counter / "corner" / (name + ".txt")).write_text("CORNER")
    (tmp_path / "adder").mkdir()
    (tmp_path / "adder" / "08bits.txt").write_text("WIDTH = 8")
    return tmp_path


class TestExpand:
    def test_entries_without_wildcard_are_kept(self, architectures):
        assert selection.expand(["counter/08bits", "adder/08bits"], str(architectures)) == [
            "adder/08bits", "counter/08bits",
        ]

    def test_configuration_wildcard(self, architectures):
        assert selection.expand(["counter/*"], str(architectures)) == [
            "counter/04bits", "counter/08bits", "counter/16bits",
        ]

    def test_natural_order(self, architectures):
        for name in ("2bits", "10bits"):
            (architectures / "counter" / (name + ".txt")).write_text("")
        expanded = selection.expand(["counter/*"], str(architectures))
        assert expanded == [
            "counter/2bits", "counter/04bits", "counter/08bits", "counter/10bits", "counter/16bits",
        ]

    def test_domain_wildcard_is_crossed_with_the_configurations(self, architectures):
        assert selection.expand(["counter/*+corner/*"], str(architectures)) == [
            "counter/04bits+corner/ff", "counter/04bits+corner/tt",
            "counter/08bits+corner/ff", "counter/08bits+corner/tt",
            "counter/16bits+corner/ff", "counter/16bits+corner/tt",
        ]

    def test_explicit_domain_value_is_kept(self, architectures):
        assert selection.expand(["counter/*+corner/tt"], str(architectures)) == [
            "counter/04bits+corner/tt", "counter/08bits+corner/tt", "counter/16bits+corner/tt",
        ]

    def test_duplicates_are_removed(self, architectures):
        assert selection.expand(["counter/08bits", "counter/*"], str(architectures)) == [
            "counter/04bits", "counter/08bits", "counter/16bits",
        ]

    def test_missing_architecture_is_reported(self, architectures):
        messages = []
        assert selection.expand(["nope/*"], str(architectures), messages=messages) == []
        assert [message.level for message in messages] == ["error", "warning"]

    def test_missing_domain_is_reported_with_the_ones_that_exist(self, architectures):
        messages = []
        selection.expand(["counter/08bits+nope/*"], str(architectures), messages=messages)
        assert messages[0].level == "error"
        assert "corner" in messages[0].hints[0]

    def test_architecture_without_configuration_is_reported(self, architectures):
        (architectures / "empty").mkdir()
        messages = []
        assert selection.expand(["empty/*"], str(architectures), messages=messages) == []
        assert [message.level for message in messages] == ["warning", "warning"]

    def test_an_unreadable_entry_does_not_stop_the_others(self, architectures):
        messages = []
        expanded = selection.expand(["nope/*", "counter/08bits"], str(architectures), messages=messages)
        assert expanded == ["counter/08bits"]
