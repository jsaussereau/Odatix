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
Saving a settings file rewrites how it describes its configurations. What it
describes must come out of that untouched.

Every settings file shipped with Odatix is put through the round trip: read it,
save it -- which drops "generate_configurations" and writes a "configurations"
block instead -- and check that it still resolves to exactly the same
configurations. A settings file nobody edited must never start meaning
something else because Odatix rewrote it.
"""

import os
import shutil

import pytest
import yaml

import odatix.lib.hard_settings as hard_settings
from odatix.lib.config_generator import ConfigGenerator
from odatix.workspace.architectures import ArchitectureSettings
from odatix.workspace.settings import save_settings
from odatix.workspace.space import ConfigSet, config_set_rules

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLES = os.path.join(REPO_ROOT, "sources", "odatix_examples", "odatix_userconfig")


def example_settings_files():
    """Every settings file of the examples, by path."""
    found = []
    for root in ("architectures", "workflows"):
        base = os.path.join(EXAMPLES, root)
        if not os.path.isdir(base):
            continue
        for directory, _subdirs, files in os.walk(base):
            if hard_settings.param_settings_filename in files:
                found.append(os.path.join(directory, hard_settings.param_settings_filename))
    return sorted(found)


def describing_examples():
    """The example settings files that actually describe configurations."""
    describing = []
    for path in example_settings_files():
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        if config_set_rules(data).generates:
            describing.append(path)
    return describing


DESCRIBING = describing_examples()


def label(path):
    return os.path.relpath(path, EXAMPLES)


def test_the_examples_cover_the_migration():
    """A silently empty list would make the round trip test pass for nothing."""
    assert len(DESCRIBING) >= 5


@pytest.mark.parametrize("path", DESCRIBING, ids=label)
class TestRoundTrip:
    def resolved(self, path):
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        space = config_set_rules(data, source=path)
        return {point.name: point.content for point in space.points()}

    def saved_copy(self, path, tmpdir):
        """The same settings file, read and saved back by Odatix."""
        target = os.path.join(str(tmpdir), hard_settings.param_settings_filename)
        shutil.copyfile(path, target)
        with open(target) as f:
            data = yaml.safe_load(f) or {}
        settings = ArchitectureSettings.from_dict(data)
        save_settings(settings, target)
        return target

    def test_the_new_path_reads_what_the_old_one_read(self, path):
        """
        The rules, read the new way, describe what the generator has always
        produced from the same file.
        """
        generator = ConfigGenerator(path=os.path.dirname(path), silent=True)
        expected, _values = generator.generate()
        assert self.resolved(path) == expected

    def test_saving_keeps_what_the_file_describes(self, path, tmpdir):
        before = self.resolved(path)
        after = self.resolved(self.saved_copy(path, tmpdir))
        assert after == before
        assert before  # and it described something in the first place

    def test_saving_drops_the_keys_that_no_longer_say_anything(self, path, tmpdir):
        with open(self.saved_copy(path, tmpdir)) as f:
            written = f.read()
        assert "generate_configurations" not in written
        assert "configurations:" in written

    def test_saving_twice_changes_nothing_more(self, path, tmpdir):
        """The rewrite happens once: a converted file is left alone from then on."""
        once = self.saved_copy(path, tmpdir)
        with open(once) as f:
            after_first = f.read()

        with open(once) as f:
            data = yaml.safe_load(f) or {}
        save_settings(ArchitectureSettings.from_dict(data), once)
        with open(once) as f:
            after_second = f.read()

        assert after_second == after_first


class TestTheNewFormIsWritten:
    def test_a_converted_file_reads_the_way_it_should(self, tmpdir):
        """
        What the rewrite is for: the block that says how configurations are
        built is one block, and it says so plainly.
        """
        source = os.path.join(
            EXAMPLES, "architectures", "Example_Config_Generation", "01_Range",
            hard_settings.param_settings_filename,
        )
        target = os.path.join(str(tmpdir), hard_settings.param_settings_filename)
        shutil.copyfile(source, target)
        with open(target) as f:
            settings = ArchitectureSettings.from_dict(yaml.safe_load(f))
        save_settings(settings, target)

        with open(target) as f:
            written = f.read()

        assert "configurations:" in written
        assert "name:" in written
        assert "template:" in written
        assert "variables:" in written

    def test_configurations_can_be_described_from_scratch_in_yaml(self, tmpdir):
        """
        The whole thing has to be usable with nothing but an editor: a settings
        file written by hand, and configurations that resolve from it.
        """
        directory = str(tmpdir)
        with open(os.path.join(directory, hard_settings.param_settings_filename), "w") as f:
            f.write(
                "top_level_file: alu.sv\n"
                "\n"
                "configurations:\n"
                "  name: \"${width}bits\"\n"
                "  template: \"parameter WIDTH = ${width};\"\n"
                "\n"
                "variables:\n"
                "  width:\n"
                "    type: range\n"
                "    settings:\n"
                "      from: 8\n"
                "      to: 32\n"
                "      step: 8\n"
            )

        with open(os.path.join(directory, hard_settings.param_settings_filename)) as f:
            data = yaml.safe_load(f)

        config_set = ConfigSet(directory, config_set_rules(data, source=directory))
        assert config_set.names() == ["8bits", "16bits", "24bits", "32bits"]
        assert config_set.resolve()[0].content == "parameter WIDTH = 8;"


class TestLegacyRulesAreCarriedOver:
    """
    Everything the former block said has to survive the rewrite, not only its
    name and its template: a blacklist or a constraint left behind would make
    the saved file describe configurations it used to exclude.
    """

    LEGACY = (
        "top_level_file: alu.sv\n"
        "generate_configurations: Yes\n"
        "generate_configurations_settings:\n"
        "  name: \"${width}bits\"\n"
        "  template: \"parameter WIDTH = ${width};\"\n"
        "  blacklist: [16bits]\n"
        "  constraints:\n"
        "    - \"${width} <= 24\"\n"
        "    - expr: \"${width} >= 8\"\n"
        "      message: too narrow\n"
        "  variables:\n"
        "    width:\n"
        "      type: list\n"
        "      settings:\n"
        "        list: [4, 8, 16, 24, 32]\n"
    )

    def points(self, path):
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        space = config_set_rules(data, source=path)
        return {point.name: point.content for point in space.points()}

    def test_saving_keeps_the_blacklist_and_the_constraints(self, tmpdir):
        target = os.path.join(str(tmpdir), hard_settings.param_settings_filename)
        with open(target, "w") as f:
            f.write(self.LEGACY)
        before = self.points(target)
        assert sorted(before) == ["24bits", "8bits"]

        with open(target) as f:
            save_settings(ArchitectureSettings.from_dict(yaml.safe_load(f)), target)

        with open(target) as f:
            written = f.read()
        assert "generate_configurations" not in written
        assert "blacklist" in written and "too narrow" in written
        assert self.points(target) == before
