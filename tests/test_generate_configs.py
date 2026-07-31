"""Tests for odatix.components.generate_configs (configuration file generation)."""

import os
import textwrap

import pytest

from odatix.components.generate_configs import collect_configs, write_configs
from odatix.components.motd import read_version


GEN_SETTINGS = textwrap.dedent(
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


@pytest.fixture
def generation_tree(tmp_path):
    domain = tmp_path / "arch" / "main"
    domain.mkdir(parents=True)
    (domain / "_settings.yml").write_text(GEN_SETTINGS)
    return tmp_path


class TestCollectConfigs:
    def test_collects_new_configs(self, generation_tree):
        existing, overwrite, new, errors, valid = collect_configs(str(generation_tree), overwrite=False)
        names = sorted(os.path.basename(p) for p in new)
        assert names == ["08bits.txt", "16bits.txt", "32bits.txt"]
        assert existing == []
        assert errors == []
        assert valid == new

    def test_existing_configs_skipped_without_overwrite(self, generation_tree):
        domain = generation_tree / "arch" / "main"
        (domain / "08bits.txt").write_text("old content")
        existing, overwrite, new, _, valid = collect_configs(str(generation_tree), overwrite=False)
        assert [os.path.basename(p) for p in existing] == ["08bits.txt"]
        assert len(new) == 2
        assert len(valid) == 2

    def test_existing_configs_overwritten_with_flag(self, generation_tree):
        domain = generation_tree / "arch" / "main"
        (domain / "08bits.txt").write_text("old content")
        _, overwrite, new, _, valid = collect_configs(str(generation_tree), overwrite=True)
        assert [os.path.basename(p) for p in overwrite] == ["08bits.txt"]
        assert len(valid) == 3

    def test_generation_disabled_is_ignored(self, tmp_path):
        domain = tmp_path / "arch" / "main"
        domain.mkdir(parents=True)
        (domain / "_settings.yml").write_text("use_parameters: false\n")
        existing, overwrite, new, errors, valid = collect_configs(str(tmp_path), overwrite=False)
        assert (existing, overwrite, new, errors, valid) == ([], [], [], [], [])

    def test_missing_path_exits(self, tmp_path):
        with pytest.raises(SystemExit):
            collect_configs(str(tmp_path / "nope"), overwrite=False)


class TestWriteConfigs:
    def test_writes_generated_files(self, generation_tree):
        _, _, new, _, valid = collect_configs(str(generation_tree), overwrite=False)
        write_configs(valid)
        domain = generation_tree / "arch" / "main"
        assert (domain / "08bits.txt").read_text().strip() == "parameter WIDTH = 08"
        assert (domain / "16bits.txt").read_text().strip() == "parameter WIDTH = 16"
        assert (domain / "32bits.txt").read_text().strip() == "parameter WIDTH = 32"

    def test_overwrite_replaces_content(self, generation_tree):
        domain = generation_tree / "arch" / "main"
        (domain / "08bits.txt").write_text("old content")
        _, _, _, _, valid = collect_configs(str(generation_tree), overwrite=True)
        write_configs(valid)
        assert "old content" not in (domain / "08bits.txt").read_text()


class TestMotd:
    def test_read_version(self):
        version = read_version()
        assert isinstance(version, str)
        assert version != ""
