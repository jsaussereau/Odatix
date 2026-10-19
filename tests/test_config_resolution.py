"""
Resolving configurations at run time.

What these check is the promise of the unified design space: a configuration
described by a rule is one of the domain's configurations, whether or not
"odatix generate" has ever been run. Nothing here generates anything first.
"""

import os
import textwrap

import pytest

import odatix.workspace.space as space
import odatix.workspace.selection as selection
from odatix.lib.param_domain import ParamDomain


RULES = textwrap.dedent(
    """\
    use_parameters: true
    param_target_file: "top.v"
    start_delimiter: "#("
    stop_delimiter: ")("

    configurations:
      name: "${width}bits"
      template: "parameter WIDTH = ${width};"

    variables:
      width:
        type: list
        settings:
          list: [8, 16, 32]
    """
)


@pytest.fixture
def domain(tmp_path):
    """An architecture whose configurations are described, and never generated."""
    path = tmp_path / "arch" / "counter"
    path.mkdir(parents=True)
    (path / "_settings.yml").write_text(RULES, encoding="utf-8")
    return path


class TestNamesWithoutGenerating:
    def test_the_domain_holds_what_its_rules_describe(self, domain):
        assert space.resolved_names(str(domain)) == ["8bits", "16bits", "32bits"]

    def test_no_file_is_written_just_by_asking(self, domain):
        space.resolved_names(str(domain))
        assert sorted(os.listdir(str(domain))) == ["_settings.yml"]

    def test_a_hand_written_file_is_held_too(self, domain):
        (domain / "64bits.txt").write_text("parameter WIDTH = 64;", encoding="utf-8")
        assert "64bits" in space.resolved_names(str(domain))


class TestFileOnDemand:
    def test_a_described_configuration_resolves_to_a_file(self, domain):
        path = space.config_file(str(domain), "16bits")
        assert path is not None
        with open(path, encoding="utf-8") as f:
            assert f.read() == "parameter WIDTH = 16;"

    def test_it_is_written_outside_of_what_the_user_keeps(self, domain):
        path = space.config_file(str(domain), "16bits")
        assert os.path.basename(os.path.dirname(path)) == space.CACHE_DIRNAME
        assert not (domain / "16bits.txt").exists()

    def test_a_file_of_the_domain_always_wins(self, domain):
        (domain / "16bits.txt").write_text("edited by hand", encoding="utf-8")
        path = space.config_file(str(domain), "16bits")
        assert path == str(domain / "16bits.txt")
        with open(path, encoding="utf-8") as f:
            assert f.read() == "edited by hand"

    def test_a_configuration_nothing_describes_has_no_file(self, domain):
        assert space.config_file(str(domain), "64bits") is None

    def test_the_cache_follows_a_change_of_the_rules(self, domain):
        first = space.config_file(str(domain), "16bits")
        settings = (domain / "_settings.yml").read_text(encoding="utf-8")
        (domain / "_settings.yml").write_text(settings.replace("WIDTH = ", "W = "), encoding="utf-8")

        second = space.config_file(str(domain), "16bits")
        assert second == first
        with open(second, encoding="utf-8") as f:
            assert f.read() == "parameter W = 16;"


class TestSelection:
    def test_a_wildcard_matches_what_the_rules_describe(self, domain):
        expanded = selection.expand(["counter/*"], root=str(domain.parent))
        assert expanded == ["counter/8bits", "counter/16bits", "counter/32bits"]


class TestParamDomain:
    def test_a_parameter_domain_needs_nothing_generated(self, tmp_path):
        instance = tmp_path / "arch" / "counter"
        (instance / "corner").mkdir(parents=True)
        (instance / "corner" / "_settings.yml").write_text(RULES, encoding="utf-8")

        resolved = ParamDomain.get_param_domain(
            "corner/16bits", "counter", arch_path=str(tmp_path / "arch"), param_domain_def=True,
        )
        assert resolved is not None
        with open(resolved.param_file, encoding="utf-8") as f:
            assert f.read() == "parameter WIDTH = 16;"

    def test_a_configuration_that_does_not_exist_is_reported(self, tmp_path):
        instance = tmp_path / "arch" / "counter"
        (instance / "corner").mkdir(parents=True)
        (instance / "corner" / "_settings.yml").write_text(RULES, encoding="utf-8")

        assert ParamDomain.get_param_domain(
            "corner/64bits", "counter", arch_path=str(tmp_path / "arch"), param_domain_def=True,
        ) is None
