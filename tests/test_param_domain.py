"""Tests for odatix.lib.param_domain (parameter domain resolution)."""

import pytest

from odatix.lib.param_domain import ParamDomain


class TestGetParamDelimiters:
    def test_full_definition(self):
        settings = {
            "use_parameters": True,
            "start_delimiter": "#(",
            "stop_delimiter": ")(",
            "param_target_file": "rtl/top.v",
        }
        use, start, stop, target = ParamDomain.get_param_delimiters(settings, "f.yml", top_level_file="top.v")
        assert (use, start, stop, target) == (True, "#(", ")(", "rtl/top.v")

    def test_target_file_defaults_to_top_level(self):
        settings = {"use_parameters": True, "start_delimiter": "a", "stop_delimiter": "b"}
        _, _, _, target = ParamDomain.get_param_delimiters(settings, "f.yml", top_level_file="top.v")
        assert target == "top.v"

    def test_empty_target_file_defaults_to_top_level(self):
        settings = {
            "use_parameters": True,
            "start_delimiter": "a",
            "stop_delimiter": "b",
            "param_target_file": "",
        }
        _, _, _, target = ParamDomain.get_param_delimiters(settings, "f.yml", top_level_file="top.v")
        assert target == "top.v"

    def test_use_parameters_false(self):
        use, start, stop, target = ParamDomain.get_param_delimiters({"use_parameters": False}, "f.yml")
        assert (use, start, stop, target) == (False, "", "", "")

    def test_missing_start_delimiter(self):
        settings = {"use_parameters": True, "stop_delimiter": "b"}
        assert ParamDomain.get_param_delimiters(settings, "f.yml") == (None, None, None, None)

    def test_missing_stop_delimiter(self):
        settings = {"use_parameters": True, "start_delimiter": "a"}
        assert ParamDomain.get_param_delimiters(settings, "f.yml") == (None, None, None, None)


class TestGetParamDomain:
    def test_resolves_domain(self, arch_dir):
        domain = ParamDomain.get_param_domain(
            request="main/default",
            architecture="my_arch",
            arch_path=str(arch_dir),
        )
        assert domain is not None
        assert domain.domain == "main"
        assert domain.domain_value == "default"
        assert domain.use_parameters is True
        assert domain.start_delimiter == "#("
        assert domain.stop_delimiter == ")("
        assert domain.param_target_file == "rtl/top.v"
        assert domain.param_file.endswith("default.txt")

    def test_missing_settings_file(self, arch_dir):
        domain = ParamDomain.get_param_domain(
            request="nonexistent_domain/default",
            architecture="my_arch",
            arch_path=str(arch_dir),
        )
        assert domain is None

    def test_missing_parameter_file(self, arch_dir):
        domain = ParamDomain.get_param_domain(
            request="main/nonexistent_config",
            architecture="my_arch",
            arch_path=str(arch_dir),
        )
        assert domain is None

    def test_get_param_domains_list(self, arch_dir):
        domains = ParamDomain.get_param_domains(
            requested_param_domains=["main/default"],
            architecture="my_arch",
            arch_path=str(arch_dir),
        )
        assert domains is not None
        assert len(domains) == 1
        assert domains[0].domain == "main"

    def test_get_param_domains_not_a_list(self, arch_dir):
        assert ParamDomain.get_param_domains("main/default", "my_arch", str(arch_dir)) is None

    def test_get_param_domains_propagates_failure(self, arch_dir):
        domains = ParamDomain.get_param_domains(
            requested_param_domains=["main/default", "bad/missing"],
            architecture="my_arch",
            arch_path=str(arch_dir),
        )
        assert domains is None


class TestFileChecks:
    def test_check_parameter_file(self, tmp_path):
        target = tmp_path / "p.txt"
        target.write_text("x")
        assert ParamDomain.check_parameter_file(str(target), str(tmp_path))
        assert not ParamDomain.check_parameter_file(str(tmp_path / "missing.txt"), str(tmp_path))

    def test_check_settings_file(self, tmp_path):
        target = tmp_path / "_settings.yml"
        target.write_text("use_parameters: false")
        assert ParamDomain.check_settings_file(str(target), str(tmp_path))
        assert not ParamDomain.check_settings_file(str(tmp_path / "missing.yml"), str(tmp_path))
