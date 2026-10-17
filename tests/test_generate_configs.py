"""Tests for odatix.components.generate_configs (configuration file generation)."""

import os
import textwrap

import pytest

from odatix.components.generate_configs import collect_configs, write_configs
from odatix.components.motd import read_version


LEGACY_SETTINGS = textwrap.dedent(
    """\
    use_parameters: true
    start_delimiter: "#("
    stop_delimiter: ")("

    generate_configurations: true
    generate_configurations_settings:
      name: "${WIDTH}bits"
      template: |
        parameter WIDTH = $WIDTH
      variables:
        WIDTH:
          type: power_of_two
          settings:
            from: 8
            to: 32
          format: "%02d"
    """
)

GEN_SETTINGS = textwrap.dedent(
    """\
    use_parameters: true
    start_delimiter: "#("
    stop_delimiter: ")("

    configurations:
      name: "${WIDTH}bits"
      template: |
        parameter WIDTH = $WIDTH

    variables:
      WIDTH:
        type: power_of_two
        settings:
          from: 8
          to: 32
        format: "%02d"
    """
)


@pytest.fixture(params=[GEN_SETTINGS, LEGACY_SETTINGS], ids=["configurations", "legacy"])
def generation_tree(request, tmp_path):
    """A workspace describing the same three configurations, in each form."""
    domain = tmp_path / "arch" / "main"
    domain.mkdir(parents=True)
    (domain / "_settings.yml").write_text(request.param)
    return tmp_path


def basenames(paths):
    return sorted(os.path.basename(path) for path in paths)


class TestCollectConfigs:
    def test_collects_new_configs(self, generation_tree):
        plan = collect_configs(str(generation_tree), overwrite=False)
        assert basenames(plan.new) == ["08bits.txt", "16bits.txt", "32bits.txt"]
        assert plan.existing == []
        assert plan.errors == []
        assert plan.valid == plan.new

    def test_an_up_to_date_file_is_not_new(self, generation_tree):
        domain = generation_tree / "arch" / "main"
        write_configs(collect_configs(str(generation_tree), overwrite=False).valid)

        plan = collect_configs(str(generation_tree), overwrite=False)
        assert plan.new == []
        assert basenames(plan.existing) == ["08bits.txt", "16bits.txt", "32bits.txt"]
        assert plan.edited == []
        assert (domain / "08bits.txt").exists()

    def test_an_edited_file_is_kept_without_overwrite(self, generation_tree):
        domain = generation_tree / "arch" / "main"
        (domain / "08bits.txt").write_text("old content")
        plan = collect_configs(str(generation_tree), overwrite=False)
        assert basenames(plan.edited) == ["08bits.txt"]
        assert plan.overwrite == []
        assert basenames(plan.new) == ["16bits.txt", "32bits.txt"]

    def test_an_edited_file_is_replaced_with_the_flag(self, generation_tree):
        domain = generation_tree / "arch" / "main"
        (domain / "08bits.txt").write_text("old content")
        plan = collect_configs(str(generation_tree), overwrite=True)
        assert basenames(plan.overwrite) == ["08bits.txt"]
        assert plan.edited == []
        assert len(plan.valid) == 3

    def test_a_domain_describing_nothing_is_ignored(self, tmp_path):
        domain = tmp_path / "arch" / "main"
        domain.mkdir(parents=True)
        (domain / "_settings.yml").write_text("use_parameters: false\n")
        plan = collect_configs(str(tmp_path), overwrite=False)
        assert (plan.existing, plan.overwrite, plan.new, plan.errors, plan.valid) == ([], [], [], [], [])

    def test_missing_path_exits(self, tmp_path):
        with pytest.raises(SystemExit):
            collect_configs(str(tmp_path / "nope"), overwrite=False)


class TestWriteConfigs:
    def test_writes_generated_files(self, generation_tree):
        write_configs(collect_configs(str(generation_tree), overwrite=False).valid)
        domain = generation_tree / "arch" / "main"
        assert (domain / "08bits.txt").read_text().strip() == "parameter WIDTH = 08"
        assert (domain / "16bits.txt").read_text().strip() == "parameter WIDTH = 16"
        assert (domain / "32bits.txt").read_text().strip() == "parameter WIDTH = 32"

    def test_an_edit_survives_a_second_generation(self, generation_tree):
        domain = generation_tree / "arch" / "main"
        write_configs(collect_configs(str(generation_tree), overwrite=False).valid)
        (domain / "08bits.txt").write_text("edited by hand")

        write_configs(collect_configs(str(generation_tree), overwrite=False).valid)
        assert (domain / "08bits.txt").read_text() == "edited by hand"

    def test_overwrite_replaces_content(self, generation_tree):
        domain = generation_tree / "arch" / "main"
        (domain / "08bits.txt").write_text("old content")
        write_configs(collect_configs(str(generation_tree), overwrite=True).valid, overwrite=True)
        assert "old content" not in (domain / "08bits.txt").read_text()

    def test_clean_removes_only_what_generation_left_behind(self, generation_tree):
        domain = generation_tree / "arch" / "main"
        write_configs(collect_configs(str(generation_tree), overwrite=False).valid)
        (domain / "by_hand.txt").write_text("mine")

        # The rules no longer describe 32 bits.
        settings = (domain / "_settings.yml").read_text().replace("to: 32", "to: 16")
        (domain / "_settings.yml").write_text(settings)

        plan = collect_configs(str(generation_tree), overwrite=False, clean=True)
        assert basenames(plan.leftovers) == ["32bits.txt"]

        write_configs(plan.valid, clean=True)
        assert not (domain / "32bits.txt").exists()
        assert (domain / "by_hand.txt").read_text() == "mine"


class TestMotd:
    def test_read_version(self):
        version = read_version()
        assert isinstance(version, str)
        assert version != ""
