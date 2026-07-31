"""Tests for odatix.components.workspace (workspace management API used by the GUI)."""

import os

import pytest

import odatix.components.workspace as ws
import odatix.lib.hard_settings as hard_settings

MAIN = hard_settings.main_parameter_domain


@pytest.fixture
def arch_root(tmp_path):
    root = tmp_path / "architectures"
    root.mkdir()
    return str(root)


@pytest.fixture
def workflow_root(tmp_path):
    root = tmp_path / "workflows"
    root.mkdir()
    return str(root)


######################################
# Architectures / instances
######################################

class TestArchitectureLifecycle:
    def test_create_and_list(self, arch_root):
        ws.create_architecture(arch_root, "archA")
        assert ws.architecture_exists(arch_root, "archA")
        assert ws.get_architectures(arch_root) == ["archA"]

    def test_duplicate(self, arch_root):
        ws.create_architecture(arch_root, "archA")
        ws.duplicate_instance(arch_root, "archA", "archB")
        assert sorted(ws.get_architectures(arch_root)) == ["archA", "archB"]

    def test_rename(self, arch_root):
        ws.create_architecture(arch_root, "archA")
        ws.rename_architecture(arch_root, "archA", "archZ")
        assert ws.get_architectures(arch_root) == ["archZ"]

    def test_delete(self, arch_root):
        ws.create_architecture(arch_root, "archA")
        ws.delete_instance(arch_root, "archA")
        assert ws.get_architectures(arch_root) == []

    def test_duplicate_missing_source_raises(self, arch_root):
        with pytest.raises(ValueError):
            ws.duplicate_instance(arch_root, "nope", "copy")

    def test_duplicate_existing_target_raises(self, arch_root):
        ws.create_architecture(arch_root, "a")
        ws.create_architecture(arch_root, "b")
        with pytest.raises(ValueError):
            ws.duplicate_instance(arch_root, "a", "b")


######################################
# Parameter domains
######################################

class TestParameterDomains:
    def test_create_architecture_creates_main_domain(self, arch_root):
        ws.create_architecture(arch_root, "archA")
        assert ws.parameter_domain_exists(arch_root, "archA", MAIN)

    def test_create_additional_domain(self, arch_root):
        ws.create_architecture(arch_root, "archA")
        ws.create_parameter_domain(arch_root, "archA", "voltage")
        domains = ws.get_param_domains(arch_root, "archA")
        assert "voltage" in domains

    def test_rename_domain(self, arch_root):
        ws.create_architecture(arch_root, "archA")
        ws.create_parameter_domain(arch_root, "archA", "old")
        ws.rename_parameter_domain(arch_root, "archA", "old", "new")
        domains = ws.get_param_domains(arch_root, "archA")
        assert "new" in domains
        assert "old" not in domains

    def test_delete_domain(self, arch_root):
        ws.create_architecture(arch_root, "archA")
        ws.create_parameter_domain(arch_root, "archA", "tmp")
        ws.delete_parameter_domain(arch_root, "archA", "tmp")
        assert "tmp" not in ws.get_param_domains(arch_root, "archA")


######################################
# Configuration files
######################################

class TestConfigFiles:
    def test_save_load_delete(self, arch_root):
        ws.create_architecture(arch_root, "archA")
        ws.save_config_file(arch_root, "archA", MAIN, "08bits.txt", "parameter WIDTH = 8")
        assert "08bits.txt" in ws.get_config_files(arch_root, "archA", MAIN)
        assert ws.load_config_file(arch_root, "archA", MAIN, "08bits.txt") == "parameter WIDTH = 8"
        ws.delete_config_file(arch_root, "archA", MAIN, "08bits.txt")
        assert "08bits.txt" not in ws.get_config_files(arch_root, "archA", MAIN)

    def test_delete_all(self, arch_root):
        ws.create_architecture(arch_root, "archA")
        for name in ("a.txt", "b.txt"):
            ws.save_config_file(arch_root, "archA", MAIN, name, "x")
        ws.delete_all_config_files(arch_root, "archA", MAIN)
        assert ws.get_config_files(arch_root, "archA", MAIN) == []


######################################
# Workflows
######################################

class TestWorkflows:
    def test_create_and_list(self, workflow_root):
        ws.create_workflow(workflow_root, "wf1")
        assert ws.workflow_exists(workflow_root, "wf1")
        assert ws.get_workflows(workflow_root) == ["wf1"]

    def test_rename_and_delete(self, workflow_root):
        ws.create_workflow(workflow_root, "wf1")
        ws.rename_workflow(workflow_root, "wf1", "wf2")
        assert ws.get_workflows(workflow_root) == ["wf2"]
        ws.delete_workflow(workflow_root, "wf2")
        assert ws.get_workflows(workflow_root) == []

    def test_settings_roundtrip(self, workflow_root):
        ws.create_workflow(workflow_root, "wf1")
        ws.update_workflow_settings(workflow_root, "wf1", {"key1": "value1"})
        settings = ws.load_workflow_settings(workflow_root, "wf1")
        assert settings.get("key1") == "value1"


######################################
# Selection settings (run_jobs page)
######################################

class TestSaveSelection:
    def test_save_workflow_selection_uses_workflows_key(self, tmp_path):
        path = str(tmp_path / "workflow_settings.yml")
        ws.save_architecture_selection(
            path,
            {"workflows": ["wf1/default", "wf2 + d/v"]},
            run_mode="workflow",
        )
        data = ws.load_arch_selection_settings(path)
        assert data["workflows"] == ["wf1/default", "wf2 + d/v"]
        # arch-only keys must not leak into a workflow settings file
        assert "architectures" not in data
        assert "frequencies" not in data
        # force_single_thread is written for every run mode, workflows included,
        # so the GUI's "Force single threading" toggle is persisted
        assert "force_single_thread" in data

    def test_workflow_selection_is_read_by_run_workflow(self, tmp_path):
        from odatix.lib.run_settings import get_workflow_settings

        path = str(tmp_path / "workflow_settings.yml")
        ws.save_architecture_selection(path, {"workflows": ["wf1"]}, run_mode="workflow")
        *_, workflows = get_workflow_settings(path)
        assert workflows == ["wf1"]

    def test_save_fmax_selection_uses_architectures_key(self, tmp_path):
        path = str(tmp_path / "fmax_settings.yml")
        ws.save_architecture_selection(
            path,
            {"architectures": ["arch1/08bits"]},
            run_mode="fmax_synthesis",
        )
        data = ws.load_arch_selection_settings(path)
        assert data["architectures"] == ["arch1/08bits"]
        assert "workflows" not in data
        # fmax keeps force_single_thread
        assert "force_single_thread" in data

    def test_save_analysis_selection_writes_tools(self, tmp_path):
        path = str(tmp_path / "analysis_settings.yml")
        ws.save_architecture_selection(
            path,
            {"tools": ["vivado", "verilator"], "architectures": ["arch1/08bits"]},
            run_mode="analyze",
        )
        data = ws.load_arch_selection_settings(path)
        assert data["tools"] == ["vivado", "verilator"]
        assert data["architectures"] == ["arch1/08bits"]
        # the tools list round-trips through the dedicated reader
        assert ws.load_analysis_tools(path) == ["vivado", "verilator"]

    def test_tools_key_only_written_for_analyze(self, tmp_path):
        path = str(tmp_path / "fmax_settings.yml")
        ws.save_architecture_selection(
            path,
            {"tools": ["vivado"], "architectures": ["arch1/08bits"]},
            run_mode="fmax_synthesis",
        )
        data = ws.load_arch_selection_settings(path)
        assert "tools" not in data


class TestAnalysisTools:
    def test_load_analysis_tools_list(self, tmp_path):
        path = tmp_path / "analysis_settings.yml"
        path.write_text("tools:\n  - vivado\n  - design_compiler\n")
        assert ws.load_analysis_tools(str(path)) == ["vivado", "design_compiler"]

    def test_load_analysis_tools_scalar(self, tmp_path):
        path = tmp_path / "analysis_settings.yml"
        path.write_text("tools: verilator\n")
        assert ws.load_analysis_tools(str(path)) == ["verilator"]

    def test_load_analysis_tools_missing_key(self, tmp_path):
        path = tmp_path / "analysis_settings.yml"
        path.write_text("architectures:\n  - Foo/8bits\n")
        assert ws.load_analysis_tools(str(path)) == []

    def test_load_analysis_tools_missing_file(self, tmp_path):
        assert ws.load_analysis_tools(str(tmp_path / "nope.yml")) == []


######################################
# Combination helpers
######################################

class TestCombinations:
    def test_count_combinations(self):
        assert ws.count_combinations({"a": [1, 2], "b": [1, 2, 3]}) == 6

    def test_count_combinations_empty(self):
        assert ws.count_combinations({}) == 0

    def test_generate_config_combinations_main_domain(self):
        combos = ws.generate_config_combinations({MAIN: ["c1", "c2"]}, "arch")
        assert combos == [["arch/c1"], ["arch/c2"]]

    def test_generate_config_combinations_with_extra_domain(self):
        combos = ws.generate_config_combinations({MAIN: ["c1"], "corner": ["tt", "ss"]}, "arch")
        assert combos == [["arch/c1", "corner/tt"], ["arch/c1", "corner/ss"]]

    def test_generate_config_combinations_empty(self):
        assert ws.generate_config_combinations({}, "arch") == []


######################################
# Config generation dict builders
######################################

class TestConfigGenDicts:
    def test_create_config_gen_dict(self):
        d = ws.create_config_gen_dict("n$X", "v=$X", {"X": {"type": "bool"}})
        assert d["generate_configurations"] is True
        assert d["generate_configurations_settings"]["name"] == "n$X"

    def test_create_config_gen_variable_dict(self):
        v = ws.create_config_gen_variable_dict("X", "range", {"from": 1, "to": 4})
        assert v == {"X": {"type": "range", "settings": {"from": 1, "to": 4}}}

    def test_variable_dict_with_format(self):
        v = ws.create_config_gen_variable_dict("X", "range", {}, format="%02d")
        assert v["X"]["format"] == "%02d"


######################################
# EDA target files
######################################

TARGET_FILE_CONTENT = """\
##############################################
# Target settings for vivado
##############################################

constraint_file: constraints.xdc
tool_install_path: ""

# FPGA target
targets:
  - xc7a100t-csg324-1
  - xc7k70t-fbg676-2
"""

COMMENTED_TARGET_FILE_CONTENT = """\
constraint_file: constraints.xdc

# FPGA target
targets:
  # - xc7s6-cpga196-1
  # - xc7s25-csga225-1
  - xc7a100t-csg324-1
  # - xc7k70t-fbg676-2
"""


@pytest.fixture
def target_dir(tmp_path):
    (tmp_path / "target_vivado.yml").write_text(TARGET_FILE_CONTENT)
    return str(tmp_path)


class TestTargets:
    def test_get_targets(self, target_dir):
        targets = ws.get_targets(target_dir, "vivado")
        assert [t["name"] for t in targets] == ["xc7a100t-csg324-1", "xc7k70t-fbg676-2"]
        assert all(t["enabled"] for t in targets)
        assert all(not t["script_copy_enable"] for t in targets)

    def test_get_targets_missing_file(self, target_dir):
        assert ws.get_targets(target_dir, "unknown_tool") == []

    def test_target_exists(self, target_dir):
        assert ws.target_exists(target_dir, "vivado", "xc7a100t-csg324-1")
        assert not ws.target_exists(target_dir, "vivado", "nope")

    def test_commented_entries_are_disabled_targets(self, tmp_path):
        (tmp_path / "target_vivado.yml").write_text(COMMENTED_TARGET_FILE_CONTENT)
        targets = ws.get_targets(str(tmp_path), "vivado")
        assert [(t["name"], t["enabled"]) for t in targets] == [
            ("xc7s6-cpga196-1", False),
            ("xc7s25-csga225-1", False),
            ("xc7a100t-csg324-1", True),
            ("xc7k70t-fbg676-2", False),
        ]

    def test_disable_target_keeps_it_in_file_as_comment(self, target_dir):
        targets = ws.get_targets(target_dir, "vivado")
        targets[1]["enabled"] = False
        ws.save_target_selection(target_dir, "vivado", targets)

        # the run flow only sees the enabled target...
        data = ws.load_yaml_file(ws.get_target_file_path(target_dir, "vivado"))
        assert data["targets"] == ["xc7a100t-csg324-1"]
        # ...but the disabled one stays as a commented-out entry
        content = open(ws.get_target_file_path(target_dir, "vivado")).read()
        assert "# - xc7k70t-fbg676-2" in content

        # and it can be re-enabled
        targets = ws.get_targets(target_dir, "vivado")
        assert [t["enabled"] for t in targets] == [True, False]
        targets[1]["enabled"] = True
        ws.save_target_selection(target_dir, "vivado", targets)
        data = ws.load_yaml_file(ws.get_target_file_path(target_dir, "vivado"))
        assert data["targets"] == ["xc7a100t-csg324-1", "xc7k70t-fbg676-2"]
        content = open(ws.get_target_file_path(target_dir, "vivado")).read()
        assert "# - xc7k70t-fbg676-2" not in content

    def test_disable_enable_roundtrip_is_stable(self, tmp_path):
        (tmp_path / "target_vivado.yml").write_text(COMMENTED_TARGET_FILE_CONTENT)
        # save without any change: same targets, same states, no duplicates
        targets = ws.get_targets(str(tmp_path), "vivado")
        ws.save_target_selection(str(tmp_path), "vivado", targets)
        assert ws.get_targets(str(tmp_path), "vivado") == targets
        # non-target comments are preserved
        content = (tmp_path / "target_vivado.yml").read_text()
        assert "# FPGA target" in content
        assert content.count("# - xc7s6-cpga196-1") == 1

    def test_legacy_disabled_targets_key_is_read(self, tmp_path):
        (tmp_path / "target_vivado.yml").write_text(
            "targets:\n  - a\ndisabled_targets:\n  - b\n"
        )
        targets = ws.get_targets(str(tmp_path), "vivado")
        assert [(t["name"], t["enabled"]) for t in targets] == [("a", True), ("b", False)]

        # saving migrates to the commented-out representation
        ws.save_target_selection(str(tmp_path), "vivado", targets)
        data = ws.load_yaml_file(ws.get_target_file_path(str(tmp_path), "vivado"))
        assert "disabled_targets" not in data
        content = (tmp_path / "target_vivado.yml").read_text()
        assert "# - b" in content

    def test_save_preserves_other_keys_and_comments(self, target_dir):
        targets = ws.get_targets(target_dir, "vivado")
        ws.save_target_selection(target_dir, "vivado", targets)

        content = open(ws.get_target_file_path(target_dir, "vivado")).read()
        assert "constraint_file: constraints.xdc" in content
        assert "# Target settings for vivado" in content  # comments preserved

    def test_script_copy_settings_roundtrip(self, target_dir):
        targets = ws.get_targets(target_dir, "vivado")
        targets[0]["script_copy_enable"] = True
        targets[0]["script_copy_source"] = "/path/to/script.tcl"
        ws.save_target_selection(target_dir, "vivado", targets)

        data = ws.load_yaml_file(ws.get_target_file_path(target_dir, "vivado"))
        assert data["target_settings"]["xc7a100t-csg324-1"]["script_copy_enable"] is True
        assert data["target_settings"]["xc7a100t-csg324-1"]["script_copy_source"] == "/path/to/script.tcl"

        targets = ws.get_targets(target_dir, "vivado")
        assert targets[0]["script_copy_enable"] is True
        assert targets[0]["script_copy_source"] == "/path/to/script.tcl"

        # disabling script copy removes the keys
        targets[0]["script_copy_enable"] = False
        ws.save_target_selection(target_dir, "vivado", targets)
        data = ws.load_yaml_file(ws.get_target_file_path(target_dir, "vivado"))
        assert "target_settings" not in data

    def test_rename_carries_per_target_settings(self, target_dir):
        targets = ws.get_targets(target_dir, "vivado")
        targets[0]["script_copy_enable"] = True
        targets[0]["script_copy_source"] = "/s.tcl"
        ws.save_target_selection(target_dir, "vivado", targets)

        targets = ws.get_targets(target_dir, "vivado")
        targets[0] = dict(targets[0], name="renamed-target", original_name="xc7a100t-csg324-1")
        ws.save_target_selection(target_dir, "vivado", targets)

        data = ws.load_yaml_file(ws.get_target_file_path(target_dir, "vivado"))
        assert "renamed-target" in data["targets"]
        assert data["target_settings"]["renamed-target"]["script_copy_source"] == "/s.tcl"
        assert "xc7a100t-csg324-1" not in data.get("target_settings", {})

    def test_add_target(self, target_dir):
        ws.add_target(target_dir, "vivado", "new-target")
        assert ws.target_exists(target_dir, "vivado", "new-target")

    def test_add_existing_target_raises(self, target_dir):
        with pytest.raises(ValueError):
            ws.add_target(target_dir, "vivado", "xc7a100t-csg324-1")

    def test_add_target_creates_file(self, tmp_path):
        ws.add_target(str(tmp_path), "genus", "asap7")
        assert ws.get_targets(str(tmp_path), "genus")[0]["name"] == "asap7"

    def test_duplicate_target(self, target_dir):
        targets = ws.get_targets(target_dir, "vivado")
        targets[0]["script_copy_enable"] = True
        targets[0]["script_copy_source"] = "/s.tcl"
        ws.save_target_selection(target_dir, "vivado", targets)

        ws.duplicate_target(target_dir, "vivado", "xc7a100t-csg324-1", "copy-1")
        copied = [t for t in ws.get_targets(target_dir, "vivado") if t["name"] == "copy-1"][0]
        assert copied["script_copy_source"] == "/s.tcl"

    def test_duplicate_missing_source_raises(self, target_dir):
        with pytest.raises(ValueError):
            ws.duplicate_target(target_dir, "vivado", "nope", "copy")

    def test_remove_target(self, target_dir):
        ws.remove_target(target_dir, "vivado", "xc7a100t-csg324-1")
        assert not ws.target_exists(target_dir, "vivado", "xc7a100t-csg324-1")
        assert ws.target_exists(target_dir, "vivado", "xc7k70t-fbg676-2")

    def test_empty_and_duplicate_names_are_skipped_on_save(self, target_dir):
        targets = [
            {"name": "", "enabled": True},
            {"name": "a", "enabled": True},
            {"name": "a", "enabled": False},
        ]
        ws.save_target_selection(target_dir, "vivado", targets)
        result = ws.get_targets(target_dir, "vivado")
        assert [t["name"] for t in result] == ["a"]
        assert result[0]["enabled"] is True

    def test_empty_name_falls_back_to_original(self, target_dir):
        targets = [{"name": "", "original_name": "kept", "enabled": True}]
        ws.save_target_selection(target_dir, "vivado", targets)
        assert ws.target_exists(target_dir, "vivado", "kept")


######################################
# YAML + parsing helpers
######################################

class TestYamlHelpers:
    def test_load_yaml_missing_returns_default(self, tmp_path):
        assert ws.load_yaml_file(str(tmp_path / "missing.yml"), default={"d": 1}) == {"d": 1}

    def test_save_load_roundtrip(self, tmp_path):
        path = str(tmp_path / "sub" / "f.yml")
        ws.save_yaml_file(path, {"a": [1, 2]})
        assert ws.load_yaml_file(path) == {"a": [1, 2]}

    def test_parse_bool(self):
        assert ws._parse_bool(True) is True
        assert ws._parse_bool("yes") is True
        assert ws._parse_bool("false") is False
        assert ws._parse_bool(None, default=True) is True

    def test_parse_int(self):
        assert ws._parse_int("5") == 5
        assert ws._parse_int("abc", default=9) == 9

    def test_parse_int_list(self):
        assert ws._parse_int_list("10, 20; 30") == [10, 20, 30]
        assert ws._parse_int_list([1, "2"]) == [1, 2]
        assert ws._parse_int_list("10, abc, 30") == [10, 30]
        assert ws._parse_int_list(None) == []
