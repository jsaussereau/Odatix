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

"""How a parameter domain resolves the rules and the files it holds together."""

import os

import pytest

from odatix.workspace.space import (
    ORIGIN_EDITED,
    ORIGIN_GENERATED,
    ORIGIN_MANUAL,
    ORIGIN_BLACKLISTED,
    ConfigSet,
    DuplicateNameError,
    Manifest,
    ParameterSpace,
    config_set_rules,
)

WIDTH_RANGE = {
    "width": {"type": "range", "settings": {"from": 8, "to": 32, "step": 8}},
}


def width_space(name="${width}bits", template="parameter WIDTH = ${width};"):
    return ParameterSpace(WIDTH_RANGE, name=name, template=template, source="<test>")


def write(directory, name, content):
    path = os.path.join(str(directory), name + ".txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def read(directory, name):
    with open(os.path.join(str(directory), name + ".txt"), "r", encoding="utf-8") as f:
        return f.read()


def origins(config_set):
    return {config.name: config.origin for config in config_set.resolve()}


######################################
# Rules
######################################

class TestParameterSpace:
    def test_points_carry_their_values(self):
        points = width_space().points()
        assert [point.name for point in points] == ["8bits", "16bits", "24bits", "32bits"]
        assert points[0].values == {"width": 8}
        assert points[0].content == "parameter WIDTH = 8;"

    def test_a_point_can_be_picked_without_enumerating(self):
        point = width_space().point({"width": 24})
        assert point.name == "24bits"
        assert point.content == "parameter WIDTH = 24;"

    def test_a_point_outside_the_declared_values_still_renders(self):
        """
        What a search needs: the rules say how a point is named and rendered,
        not which points may be asked for.
        """
        point = width_space().point({"width": 12})
        assert point.name == "12bits"
        assert point.content == "parameter WIDTH = 12;"

    def test_derived_variables_are_computed_for_a_single_point(self):
        space = ParameterSpace(
            {
                "width": {"type": "range", "settings": {"from": 8, "to": 32, "step": 8}},
                "bytes": {"type": "function", "settings": {"op": "${width} / 8"}},
            },
            name="${width}b_${bytes}B",
            template="parameter WIDTH = ${width};",
            source="<test>",
        )
        assert space.point({"width": 16}).name == space.points()[1].name

    def test_a_name_that_hides_a_variable_is_refused(self):
        space = ParameterSpace(
            {
                "width": {"type": "range", "settings": {"from": 8, "to": 16, "step": 8}},
                "depth": {"type": "range", "settings": {"from": 1, "to": 2, "step": 1}},
            },
            name="${width}bits",  # says nothing about depth
            template="parameter WIDTH = ${width};",
            source="alu/_settings.yml",
        )
        with pytest.raises(DuplicateNameError) as error:
            space.points()
        message = str(error.value)
        assert "8bits" in message
        assert "alu/_settings.yml" in message
        assert "depth" in message

    def test_a_constraint_removes_the_combinations_it_rejects(self):
        space = ParameterSpace(
            {
                "sp": {"type": "bool"},
                "buf": {"type": "bool"},
            },
            name="sp${sp}_buf${buf}",
            template="parameter SP = ${sp};",
            source="<test>",
            constraints=["${sp} <= ${buf}"],
        )
        assert [point.name for point in space.points()] == ["sp0_buf0", "sp0_buf1", "sp1_buf1"]
        # The rejected combination is not part of the space at all: asking for
        # it by hand does not name a configuration either.
        assert space.point({"sp": 1, "buf": 0}) is None
        assert space.point({"sp": 1, "buf": 1}).name == "sp1_buf1"
        # Nothing hides it the way the blacklist hides a configuration.
        assert space.blacklisted_points() == []
        assert space.count() == 3

    def test_a_constraint_may_read_a_derived_variable(self):
        space = ParameterSpace(
            {
                "width": {"type": "range", "settings": {"from": 8, "to": 32, "step": 8}},
                "bytes": {"type": "function", "settings": {"op": "${width} / 8"}},
            },
            name="${width}bits",
            template="parameter WIDTH = ${width};",
            source="<test>",
            constraints=[{"expr": "${bytes} >= 2", "message": "at least two bytes"}],
        )
        assert [point.name for point in space.points()] == ["16bits", "24bits", "32bits"]

    def test_a_value_only_a_rejected_point_takes_is_not_a_value_of_the_space(self):
        space = ParameterSpace(
            {
                "width": {"type": "range", "settings": {"from": 8, "to": 32, "step": 8}},
                "bytes": {"type": "function", "settings": {"op": "${width} / 8"}},
            },
            name="${width}bits",
            template="parameter WIDTH = ${width};",
            source="<test>",
            constraints=["${bytes} >= 2"],
        )
        assert space.values()["bytes"] == [2, 3, 4]

    def test_a_constraint_that_cannot_be_evaluated_rejects_everything(self):
        space = ParameterSpace(
            WIDTH_RANGE,
            name="${width}bits",
            template="parameter WIDTH = ${width};",
            source="<test>",
            constraints=["${typo} > 0"],
        )
        assert space.points() == []

    def test_a_domain_without_variables_generates_nothing(self):
        assert not ParameterSpace({}, name="x").generates
        assert ParameterSpace({}, name="x").points() == []


######################################
# Reading the rules out of a settings file
######################################

class TestConfigSetRules:
    def test_the_new_form_is_read(self):
        space = config_set_rules({
            "configurations": {"name": "${width}bits", "template": "W = ${width};"},
            "variables": WIDTH_RANGE,
        })
        assert space.generates
        assert space.name == "${width}bits"
        assert space.count() == 4

    @pytest.mark.parametrize(
        "rules, expected_name, expected_content",
        [
            ({"enabled": True}, "8", "8"),
            ({"name": "w${width}"}, "w8", "8"),
            ({"template": "W = ${width};"}, "8", "W = 8;"),
            ({"name": "w${width}", "template": "W = ${width};"}, "w8", "W = 8;"),
        ],
        ids=["defaults", "name-only", "template-only", "both"],
    )
    def test_explicit_rules_fill_each_missing_template(self, rules, expected_name, expected_content):
        space = config_set_rules({"configurations": rules, "variables": WIDTH_RANGE})

        assert space.generates
        assert (space.points()[0].name, space.points()[0].content) == (expected_name, expected_content)

    def test_constraints_are_read_next_to_the_templates(self):
        space = config_set_rules({
            "configurations": {
                "name": "${width}bits",
                "template": "W = ${width};",
                "constraints": ["${width} >= 16"],
            },
            "variables": WIDTH_RANGE,
        })
        assert [point.name for point in space.points()] == ["16bits", "24bits", "32bits"]

    def test_constraints_alone_are_enough_to_describe_a_single_variable_domain(self):
        space = config_set_rules(
            {"configurations": {"constraints": ["${width} >= 16"]}, "variables": WIDTH_RANGE},
            implicit=True,
        )
        assert space.generates
        assert [point.name for point in space.points()] == ["16", "24", "32"]

    def test_the_form_with_the_flag_is_read(self):
        space = config_set_rules({
            "generate_configurations": True,
            "generate_configurations_settings": {"name": "${width}bits", "template": "W = ${width};"},
            "variables": WIDTH_RANGE,
        })
        assert space.generates
        assert space.count() == 4

    def test_the_flag_left_off_means_no_generation(self):
        space = config_set_rules({
            "generate_configurations": False,
            "generate_configurations_settings": {"name": "${width}bits", "template": "W = ${width};"},
            "variables": WIDTH_RANGE,
        })
        assert not space.generates

    def test_variables_alone_declare_a_domain_with_no_template(self):
        space = config_set_rules({"variables": WIDTH_RANGE})
        assert space.template is None
        assert not space.generates  # nothing names them here

    def test_a_single_variable_describes_a_parameter_domain_on_its_own(self):
        # Both templates would say "${width}" and nothing else: a domain
        # sweeping one variable is named after its values, and holds them.
        space = config_set_rules({"variables": WIDTH_RANGE}, implicit=True)
        assert space.generates
        assert space.implicit_name and space.implicit_template
        assert [(point.name, point.content) for point in space.points()] == [
            ("8", "8"), ("16", "16"), ("24", "24"), ("32", "32"),
        ]

    def test_what_a_single_variable_domain_says_is_kept(self):
        space = config_set_rules(
            {"configurations": {"name": "${width}bits"}, "variables": WIDTH_RANGE},
            implicit=True,
        )
        assert space.name == "${width}bits"
        assert not space.implicit_name
        # Only the template was left out, and only it is filled in.
        assert space.implicit_template
        assert space.points()[0].content == "8"

    def test_several_variables_describe_a_domain_on_their_own(self):
        # Nothing has to be written down either: the configurations are named
        # after their values, joined by an underscore, and hold them one per
        # line -- which is what a list of parameters looks like.
        space = config_set_rules({
            "variables": {
                "depth": {"type": "list", "settings": {"list": [1, 2]}},
                "width": {"type": "list", "settings": {"list": [8, 16]}},
            },
        }, implicit=True)
        assert space.generates
        assert space.implicit_name and space.implicit_template
        assert space.name == "${depth}_${width}"
        assert space.template == "${depth}\n${width}"
        assert [(point.name, point.content) for point in space.points()] == [
            ("1_8", "1\n8"), ("1_16", "1\n16"), ("2_8", "2\n8"), ("2_16", "2\n16"),
        ]

    def test_variables_substituted_into_commands_imply_nothing(self):
        # A virtual parameter domain reads the same variables without asking
        # for the default: its values go into commands, not into a design.
        assert not config_set_rules({"variables": WIDTH_RANGE}).generates

    def test_variables_are_still_read_from_their_former_place(self):
        space = config_set_rules({
            "configurations": {"name": "${width}bits", "template": "W = ${width};"},
            "generate_configurations_settings": {"variables": WIDTH_RANGE},
        })
        assert space.count() == 4

    def test_a_template_written_as_lines_is_joined(self):
        space = config_set_rules({
            "configurations": {"name": "c${width}", "template": ["a = ${width};", "b = 1;"]},
            "variables": WIDTH_RANGE,
        })
        assert space.points()[0].content == "a = 8;\nb = 1;"

    def test_a_configuration_blacklist_excludes_only_its_name(self):
        space = config_set_rules({
            "configurations": {
                "name": "${width}bits",
                "template": "W = ${width};",
                "blacklist": ["16bits"],
            },
            "variables": WIDTH_RANGE,
        })

        assert [point.name for point in space.points()] == ["8bits", "24bits", "32bits"]
        assert [point.name for point in space.blacklisted_points()] == ["16bits"]

    def test_blacklist_preserves_implicit_named_domain_rules(self):
        space = config_set_rules({
            "configurations": {"blacklist": ["16"]},
            "variables": WIDTH_RANGE,
        }, implicit=True)

        assert [point.name for point in space.points()] == ["8", "24", "32"]
        assert [point.name for point in space.blacklisted_points()] == ["16"]


######################################
# Resolution
######################################

class TestResolve:
    def test_rules_alone_resolve_without_anything_on_disk(self, tmpdir):
        config_set = ConfigSet(str(tmpdir.join("nowhere")), width_space())
        assert config_set.names() == ["8bits", "16bits", "24bits", "32bits"]
        assert all(config.origin == ORIGIN_GENERATED for config in config_set.resolve())

    def test_blacklisted_rule_configuration_is_not_resolved_but_can_be_restored(self, tmpdir):
        space = ParameterSpace(
            WIDTH_RANGE,
            name="${width}bits",
            template="parameter WIDTH = ${width};",
            blacklist=["16bits"],
        )
        config_set = ConfigSet(str(tmpdir), space)

        assert config_set.names() == ["8bits", "24bits", "32bits"]
        blacklisted = config_set.blacklisted()
        assert [(config.name, config.origin) for config in blacklisted] == [
            ("16bits", ORIGIN_BLACKLISTED),
        ]

    def test_blacklist_hides_a_materialized_generated_configuration(self, tmpdir):
        ConfigSet(str(tmpdir), width_space()).materialize()
        filtered_space = ParameterSpace(
            WIDTH_RANGE,
            name="${width}bits",
            template="parameter WIDTH = ${width};",
            blacklist=["16bits"],
        )
        config_set = ConfigSet(str(tmpdir), filtered_space)

        assert "16bits" not in config_set.names()
        assert [config.name for config in config_set.blacklisted()] == ["16bits"]
        assert config_set.resolve_point({"width": 16}) is None

    def test_blacklist_hides_a_matching_generated_file_without_a_manifest(self, tmpdir):
        write(tmpdir, "16bits", "parameter WIDTH = 16;")
        filtered_space = ParameterSpace(
            WIDTH_RANGE,
            name="${width}bits",
            template="parameter WIDTH = ${width};",
            blacklist=["16bits"],
        )
        config_set = ConfigSet(str(tmpdir), filtered_space)

        assert "16bits" not in config_set.names()
        assert [config.name for config in config_set.blacklisted()] == ["16bits"]

    def test_a_directory_of_files_resolves_the_way_it_always_did(self, tmpdir):
        write(tmpdir, "04bits", "parameter WIDTH = 4;")
        write(tmpdir, "08bits", "parameter WIDTH = 8;")
        config_set = ConfigSet(str(tmpdir))
        assert config_set.names() == ["04bits", "08bits"]
        assert origins(config_set) == {"04bits": ORIGIN_MANUAL, "08bits": ORIGIN_MANUAL}

    def test_a_file_replaces_what_the_rule_produces(self, tmpdir):
        write(tmpdir, "16bits", "parameter WIDTH = 15; // hand-tuned")
        config_set = ConfigSet(str(tmpdir), width_space())
        resolved = {config.name: config for config in config_set.resolve()}
        assert resolved["16bits"].origin == ORIGIN_EDITED
        assert resolved["16bits"].content == "parameter WIDTH = 15; // hand-tuned"
        assert resolved["16bits"].generated_content == "parameter WIDTH = 16;"
        assert resolved["8bits"].origin == ORIGIN_GENERATED

    def test_a_file_the_rules_ignore_is_a_configuration_of_its_own(self, tmpdir):
        write(tmpdir, "special", "parameter WIDTH = 3;")
        config_set = ConfigSet(str(tmpdir), width_space())
        assert "special" in config_set.names()
        assert origins(config_set)["special"] == ORIGIN_MANUAL

    def test_an_edited_configuration_keeps_the_values_of_its_point(self, tmpdir):
        write(tmpdir, "16bits", "something else")
        resolved = {config.name: config for config in ConfigSet(str(tmpdir), width_space()).resolve()}
        assert resolved["16bits"].values == {"width": 16}

    def test_resolving_one_point_honours_an_edited_file(self, tmpdir):
        write(tmpdir, "16bits", "hand-tuned")
        config = ConfigSet(str(tmpdir), width_space()).resolve_point({"width": 16})
        assert config.origin == ORIGIN_EDITED
        assert config.content == "hand-tuned"


######################################
# Manifest
######################################

class TestManifest:
    def test_no_manifest_until_something_is_generated(self, tmpdir):
        write(tmpdir, "04bits", "parameter WIDTH = 4;")
        ConfigSet(str(tmpdir), width_space()).resolve()
        assert not Manifest(str(tmpdir)).exists

    def test_generating_records_what_was_written(self, tmpdir):
        config_set = ConfigSet(str(tmpdir), width_space())
        assert config_set.materialize() == ["8bits", "16bits", "24bits", "32bits"]
        assert sorted(Manifest(str(tmpdir)).generated) == ["16bits", "24bits", "32bits", "8bits"]

    def test_generating_twice_changes_nothing(self, tmpdir):
        config_set = ConfigSet(str(tmpdir), width_space())
        config_set.materialize()
        before = origins(config_set)
        config_set.materialize()
        assert origins(config_set) == before
        assert all(origin == ORIGIN_GENERATED for origin in before.values())

    def test_an_edit_survives_a_regeneration(self, tmpdir):
        config_set = ConfigSet(str(tmpdir), width_space())
        config_set.materialize()
        write(tmpdir, "16bits", "hand-tuned")
        config_set.materialize()
        assert read(tmpdir, "16bits") == "hand-tuned"
        assert origins(config_set)["16bits"] == ORIGIN_EDITED

    def test_an_edit_is_dropped_only_when_asked_for(self, tmpdir):
        config_set = ConfigSet(str(tmpdir), width_space())
        config_set.materialize()
        write(tmpdir, "16bits", "hand-tuned")
        config_set.materialize(overwrite=True)
        assert read(tmpdir, "16bits") == "parameter WIDTH = 16;"
        assert origins(config_set)["16bits"] == ORIGIN_GENERATED

    def test_files_written_before_any_manifest_are_never_overwritten(self, tmpdir):
        """
        The workspaces that already exist: files on disk, no manifest. Nothing
        of theirs may be taken for a generated file.
        """
        write(tmpdir, "8bits", "parameter WIDTH = 8; // mine")
        write(tmpdir, "16bits", "parameter WIDTH = 16; // mine")
        config_set = ConfigSet(str(tmpdir), width_space())
        config_set.materialize()
        assert read(tmpdir, "8bits") == "parameter WIDTH = 8; // mine"
        assert read(tmpdir, "16bits") == "parameter WIDTH = 16; // mine"

    def test_deleting_the_manifest_only_makes_odatix_more_careful(self, tmpdir):
        config_set = ConfigSet(str(tmpdir), width_space())
        config_set.materialize()
        Manifest(str(tmpdir)).delete()
        assert set(origins(config_set).values()) == {ORIGIN_GENERATED}
        config_set.materialize()
        assert read(tmpdir, "8bits") == "parameter WIDTH = 8;"

    def test_a_manifest_is_not_left_behind_when_it_records_nothing(self, tmpdir):
        write(tmpdir, "04bits", "parameter WIDTH = 4;")
        ConfigSet(str(tmpdir)).materialize()
        assert not Manifest(str(tmpdir)).exists

    def test_the_manifest_explains_itself(self, tmpdir):
        ConfigSet(str(tmpdir), width_space()).materialize()
        with open(Manifest(str(tmpdir)).file, encoding="utf-8") as f:
            content = f.read()
        assert "odatix generate" in content
        assert "Deleting it is safe" in content
        assert "You never have to write or read this file" in content


######################################
# Leftovers
######################################

class TestLeftovers:
    def narrowed(self, tmpdir):
        """A domain whose rules stopped producing what they used to."""
        ConfigSet(str(tmpdir), width_space()).materialize()
        narrowed = ParameterSpace(
            {"width": {"type": "range", "settings": {"from": 8, "to": 16, "step": 8}}},
            name="${width}bits", template="parameter WIDTH = ${width};", source="<test>",
        )
        return ConfigSet(str(tmpdir), narrowed)

    def test_a_leftover_is_not_part_of_the_space(self, tmpdir):
        config_set = self.narrowed(tmpdir)
        assert config_set.names() == ["8bits", "16bits"]
        assert config_set.leftovers() == ["24bits", "32bits"]

    def test_a_leftover_is_removed_only_when_pruning(self, tmpdir):
        config_set = self.narrowed(tmpdir)
        config_set.materialize()
        assert os.path.isfile(os.path.join(str(tmpdir), "24bits.txt"))
        config_set.materialize(prune=True)
        assert not os.path.isfile(os.path.join(str(tmpdir), "24bits.txt"))
        assert config_set.leftovers() == []

    def test_an_edited_leftover_is_kept_and_stays_a_configuration(self, tmpdir):
        """Pruning must never throw away something the user wrote."""
        config_set = self.narrowed(tmpdir)
        write(tmpdir, "24bits", "hand-tuned, still wanted")
        assert "24bits" not in config_set.leftovers()
        config_set.materialize(prune=True)
        assert read(tmpdir, "24bits") == "hand-tuned, still wanted"
        assert origins(config_set)["24bits"] == ORIGIN_MANUAL

    def test_a_hand_written_file_is_never_a_leftover(self, tmpdir):
        config_set = ConfigSet(str(tmpdir), width_space())
        config_set.materialize()
        write(tmpdir, "notes", "not a generated thing")
        assert config_set.leftovers() == []
        config_set.materialize(prune=True)
        assert read(tmpdir, "notes") == "not a generated thing"


######################################
# Materializing for a run
######################################

class TestMaterializeElsewhere:
    def test_a_run_gets_every_configuration_without_touching_the_workspace(self, tmpdir):
        domain = tmpdir.mkdir("domain")
        work = tmpdir.mkdir("work")
        write(domain, "special", "parameter WIDTH = 3;")
        config_set = ConfigSet(str(domain), width_space())

        written = config_set.materialize(str(work))

        assert sorted(written) == ["16bits", "24bits", "32bits", "8bits", "special"]
        assert read(work, "8bits") == "parameter WIDTH = 8;"
        assert read(work, "special") == "parameter WIDTH = 3;"
        assert not Manifest(str(domain)).exists
        assert not Manifest(str(work)).exists
        assert sorted(os.listdir(str(domain))) == ["special.txt"]

    def test_an_edited_configuration_is_what_the_run_gets(self, tmpdir):
        domain = tmpdir.mkdir("domain")
        work = tmpdir.mkdir("work")
        write(domain, "16bits", "parameter WIDTH = 15; // hand-tuned")
        ConfigSet(str(domain), width_space()).materialize(str(work))
        assert read(work, "16bits") == "parameter WIDTH = 15; // hand-tuned"


def test_a_trailing_newline_does_not_make_a_configuration_edited():
    from odatix.workspace.space import _differs

    assert not _differs("WIDTH = 8;\n", "WIDTH = 8;")
    assert not _differs("WIDTH = 8;", "WIDTH = 8;\r\n")
    assert _differs("WIDTH = 16;\n", "WIDTH = 8;")
