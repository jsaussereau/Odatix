"""Robustness tests for every YAML input file Odatix consumes.

Each class covers one kind of YAML input, in its possible variations:
valid, missing, empty, syntactically invalid, wrong types, YAML quirks
(Yes/No booleans, quoted strings containing '#', anchors, duplicate keys),
and target-specific overrides.
"""

import os
import textwrap

import pytest
import yaml

from odatix.lib.config_generator import ConfigGenerator
from odatix.lib.param_domain import ParamDomain
from odatix.lib.run_settings import get_synth_settings, get_sim_settings, get_workflow_settings
from odatix.lib.settings import OdatixSettings
import odatix.lib.results_schema as schema
import odatix.components.workspace as ws


######################################
# Job settings files (fmax/sim/workflow *_settings.yml)
######################################

VALID_SYNTH = "overwrite: no\nask_continue: yes\nnb_jobs: 4\narchitectures: [a/b]\n"


class TestJobSettingsFiles:
    @pytest.mark.parametrize("getter,key", [
        (get_synth_settings, "architectures"),
        (get_sim_settings, "simulations"),
        (get_workflow_settings, "workflows"),
    ])
    def test_empty_file_exits_cleanly(self, tmp_path, getter, key):
        f = tmp_path / "s.yml"
        f.write_text("")
        with pytest.raises(SystemExit):
            getter(str(f))

    @pytest.mark.parametrize("getter", [get_synth_settings, get_sim_settings, get_workflow_settings])
    def test_invalid_yaml_exits_cleanly(self, tmp_path, getter):
        f = tmp_path / "s.yml"
        f.write_text("key: [unclosed\n  bad indent: ][")
        with pytest.raises(SystemExit):
            getter(str(f))

    @pytest.mark.parametrize("getter", [get_synth_settings, get_sim_settings, get_workflow_settings])
    def test_scalar_document_exits_cleanly(self, tmp_path, getter):
        f = tmp_path / "s.yml"
        f.write_text("just a string\n")
        with pytest.raises(SystemExit):
            getter(str(f))

    def test_yaml_boolean_variants(self, tmp_path):
        # YAML 1.1 booleans: yes/no/on/off/true/false are all valid
        f = tmp_path / "s.yml"
        f.write_text("overwrite: On\nask_continue: off\nnb_jobs: 4\narchitectures: [a/b]\n")
        overwrite, ask, _, _, _, _ = get_synth_settings(str(f))
        assert overwrite is True
        assert ask is False

    def test_architectures_null_is_accepted(self, tmp_path):
        # 'architectures:' with no entries loads as None (no type constraint)
        f = tmp_path / "s.yml"
        f.write_text("overwrite: no\nask_continue: no\nnb_jobs: 1\narchitectures:\n")
        *_, archs = get_synth_settings(str(f))
        assert archs is None

    def test_nb_jobs_as_string_exits(self, tmp_path):
        f = tmp_path / "s.yml"
        f.write_text('overwrite: no\nask_continue: no\nnb_jobs: "8"\narchitectures: []\n')
        with pytest.raises(SystemExit):
            get_synth_settings(str(f))


######################################
# ConfigGenerator loading _settings.yml from disk
######################################

GEN_YAML = textwrap.dedent(
    """\
    generate_configurations: true
    generate_configurations_settings:
      name: "w$WIDTH"
      template: "parameter WIDTH = $WIDTH"
      variables:
        WIDTH:
          type: list
          settings:
            list: [8, 16]
    """
)


class TestConfigGeneratorFiles:
    def write_settings(self, tmp_path, content):
        (tmp_path / "_settings.yml").write_text(content)
        return str(tmp_path)

    def test_valid_file(self, tmp_path):
        gen = ConfigGenerator(path=self.write_settings(tmp_path, GEN_YAML), silent=True)
        configs, _ = gen.generate()
        assert set(configs) == {"w8", "w16"}

    def test_missing_file_exits(self, tmp_path):
        with pytest.raises(SystemExit):
            ConfigGenerator(path=str(tmp_path / "nope"), silent=True)

    def test_empty_file_exits(self, tmp_path):
        with pytest.raises(SystemExit):
            ConfigGenerator(path=self.write_settings(tmp_path, ""), silent=True)

    def test_invalid_yaml_exits(self, tmp_path):
        with pytest.raises(SystemExit):
            ConfigGenerator(path=self.write_settings(tmp_path, "a: [unclosed"), silent=True)

    def test_generation_key_absent(self, tmp_path):
        gen = ConfigGenerator(path=self.write_settings(tmp_path, "use_parameters: false\n"), silent=True)
        assert not gen.enabled
        assert gen.generate() == ({}, {})

    def test_yaml_anchors_and_aliases(self, tmp_path):
        content = textwrap.dedent(
            """\
            generate_configurations: true
            generate_configurations_settings:
              name: "a${A}b${B}"
              template: "$A $B"
              variables:
                A: &int_list
                  type: list
                  settings:
                    list: [1, 2]
                B: *int_list
            """
        )
        gen = ConfigGenerator(path=self.write_settings(tmp_path, content), silent=True)
        configs, values = gen.generate()
        assert values["A"] == [1, 2]
        assert values["B"] == [1, 2]
        assert len(configs) == 4

    def test_duplicate_keys_last_wins(self, tmp_path):
        # PyYAML resolves duplicate keys silently: the last one wins
        content = GEN_YAML + "generate_configurations: false\n"
        gen = ConfigGenerator(path=self.write_settings(tmp_path, content), silent=True)
        assert not gen.enabled

    def test_multiline_template_block(self, tmp_path):
        content = textwrap.dedent(
            """\
            generate_configurations: true
            generate_configurations_settings:
              name: "w$W"
              template: |
                line1 = $W
                line2 = $W
              variables:
                W:
                  type: list
                  settings:
                    list: [1]
            """
        )
        gen = ConfigGenerator(path=self.write_settings(tmp_path, content), silent=True)
        configs, _ = gen.generate()
        assert configs["w1"] == "line1 = 1\nline2 = 1\n"

    def test_template_as_yaml_list(self, tmp_path):
        content = textwrap.dedent(
            """\
            generate_configurations: true
            generate_configurations_settings:
              name: "w$W"
              template:
                - "line1 = $W"
                - "line2"
              variables:
                W:
                  type: list
                  settings:
                    list: [1]
            """
        )
        gen = ConfigGenerator(path=self.write_settings(tmp_path, content), silent=True)
        configs, _ = gen.generate()
        assert configs["w1"] == "line1 = 1\nline2"

    def test_unicode_values(self, tmp_path):
        content = textwrap.dedent(
            """\
            generate_configurations: true
            generate_configurations_settings:
              name: "cfg_$W"
              template: "// généré ← $W étape"
              variables:
                W:
                  type: list
                  settings:
                    list: ["éà"]
            """
        )
        gen = ConfigGenerator(path=self.write_settings(tmp_path, content), silent=True)
        configs, _ = gen.generate()
        assert configs == {"cfg_éà": "// généré ← éà étape"}

    def test_string_list_values_keep_leading_zeros(self, tmp_path):
        content = textwrap.dedent(
            """\
            generate_configurations: true
            generate_configurations_settings:
              name: "$W"
              template: "$W"
              variables:
                W:
                  type: list
                  settings:
                    list: ["08", "16"]
            """
        )
        gen = ConfigGenerator(path=self.write_settings(tmp_path, content), silent=True)
        configs, _ = gen.generate()
        assert set(configs) == {"08", "16"}


######################################
# Workspace settings file (odatix.yml)
######################################

class TestOdatixSettingsFiles:
    def test_all_paths_overridden(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "odatix.yml").write_text(
            textwrap.dedent(
                """\
                work_path: custom_work
                arch_path: my/archs
                sim_path: my/sims
                result_path: my_results
                use_benchmark: yes
                """
            )
        )
        settings = OdatixSettings(silent=True)
        assert settings.valid
        assert settings.work_path == "custom_work"
        assert settings.arch_path == "my/archs"
        assert settings.sim_path == "my/sims"
        assert settings.result_path == "my_results"
        assert settings.use_benchmark is True

    def test_invalid_yaml_is_invalid(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "odatix.yml").write_text("a: [unclosed")
        settings = OdatixSettings(silent=True)
        assert not settings.valid

    def test_empty_file_uses_defaults(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "odatix.yml").write_text("")
        settings = OdatixSettings(silent=True)
        assert settings.valid
        assert settings.work_path == OdatixSettings.DEFAULT_WORK_PATH
        assert settings.arch_path == OdatixSettings.DEFAULT_ARCH_PATH

    def test_deprecated_keys_still_valid(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "odatix.yml").write_text("sim_work_path: old\nfmax_work_path: old\n")
        settings = OdatixSettings(silent=True)
        assert settings.valid  # only a deprecation warning

    def test_wrong_type_falls_back_to_default(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "odatix.yml").write_text("use_benchmark: 42\n")
        settings = OdatixSettings(silent=True)
        assert settings.valid
        assert settings.use_benchmark == OdatixSettings.DEFAULT_USE_BENCHMARK


######################################
# Parameter domain _settings.yml
######################################

class TestParamDomainSettingsFiles:
    def write_domain(self, tmp_path, settings_content, config_name="default"):
        domain_dir = tmp_path / "archs" / "arch" / "dom"
        domain_dir.mkdir(parents=True)
        (domain_dir / "_settings.yml").write_text(settings_content)
        (domain_dir / f"{config_name}.txt").write_text("params")
        return str(tmp_path / "archs")

    def get(self, arch_path):
        return ParamDomain.get_param_domain(request="dom/default", architecture="arch", arch_path=arch_path)

    def test_invalid_yaml_returns_none(self, tmp_path):
        arch_path = self.write_domain(tmp_path, "a: [unclosed")
        assert self.get(arch_path) is None

    def test_empty_settings_disables_parameters(self, tmp_path):
        arch_path = self.write_domain(tmp_path, "")
        domain = self.get(arch_path)
        assert domain is not None
        assert domain.use_parameters is False

    def test_yaml_booleans_for_use_parameters(self, tmp_path):
        arch_path = self.write_domain(tmp_path, 'use_parameters: Yes\nstart_delimiter: "a"\nstop_delimiter: "b"\n')
        domain = self.get(arch_path)
        assert domain.use_parameters is True

    def test_hash_inside_quoted_delimiter(self, tmp_path):
        # '#' inside a quoted string is not a comment
        arch_path = self.write_domain(
            tmp_path, 'use_parameters: yes\nstart_delimiter: "counter #("\nstop_delimiter: ")("\n'
        )
        domain = self.get(arch_path)
        assert domain.start_delimiter == "counter #("
        assert domain.stop_delimiter == ")("

    def test_unquoted_delimiter_with_hash_is_truncated(self, tmp_path):
        # documents the YAML pitfall: unquoted '#' starts a comment
        arch_path = self.write_domain(
            tmp_path, "use_parameters: yes\nstart_delimiter: counter #(\nstop_delimiter: hop\n"
        )
        domain = self.get(arch_path)
        assert domain.start_delimiter == "counter"


######################################
# Results files
######################################

class TestResultsFiles:
    def test_empty_file(self, tmp_path):
        f = tmp_path / "results.yml"
        f.write_text("")
        loaded = schema.load_results_file(str(f))
        assert loaded.schema_detected == schema.FORMAT_UNKNOWN
        assert loaded.records == []

    def test_invalid_yaml_raises(self, tmp_path):
        f = tmp_path / "results.yml"
        f.write_text("a: [unclosed")
        with pytest.raises(yaml.YAMLError):
            schema.load_results_file(str(f))

    def test_missing_file_raises_oserror(self, tmp_path):
        with pytest.raises(OSError):
            schema.load_results_file(str(tmp_path / "missing.yml"))

    def test_scalar_document(self, tmp_path):
        f = tmp_path / "results.yml"
        f.write_text("42\n")
        loaded = schema.load_results_file(str(f))
        assert loaded.schema_detected == schema.FORMAT_UNKNOWN

    def test_v2_with_extra_toplevel_keys(self, tmp_path):
        f = tmp_path / "results.yml"
        f.write_text(
            textwrap.dedent(
                """\
                schema: 2
                some_future_key: whatever
                units: {Fmax: MHz}
                results:
                  - meta: {type: fmax_synthesis, target: t}
                    metrics: {Fmax: 100}
                """
            )
        )
        loaded = schema.load_results_file(str(f))
        assert loaded.schema_detected == schema.FORMAT_V2
        assert len(loaded.records) == 1

    def test_v2_with_null_metrics(self, tmp_path):
        f = tmp_path / "results.yml"
        f.write_text("schema: 2\nresults:\n  - meta: {type: x}\n    metrics:\n")
        loaded = schema.load_results_file(str(f))
        assert loaded.records[0]["metrics"] == {}


######################################
# Architecture _settings.yml variations (integration, example workspace)
######################################

ARCH_SETTINGS = "odatix_userconfig/architectures/Example_Counter_verilog/_settings.yml"
ARCH_REQUEST = ["Example_Counter_verilog/04bits"]
TARGET = "xc7a100t-csg324-1"


def load_arch_yaml():
    with open(ARCH_SETTINGS) as f:
        return yaml.safe_load(f)


def save_arch_yaml(data):
    with open(ARCH_SETTINGS, "w") as f:
        yaml.dump(data, f)


@pytest.mark.integration
class TestArchitectureSettingsVariations:
    def resolve(self):
        from test_handlers import make_arch_handler

        handler = make_arch_handler()
        instances = handler.get_architectures(ARCH_REQUEST, [TARGET], run_mode="fmax", timestamp="ts")
        return handler, instances

    def test_empty_settings_rejects_architecture(self, example_workspace):
        open(ARCH_SETTINGS, "w").close()
        _, instances = self.resolve()
        assert instances == []

    def test_invalid_yaml_rejects_architecture(self, example_workspace):
        with open(ARCH_SETTINGS, "w") as f:
            f.write("a: [unclosed")
        _, instances = self.resolve()
        assert instances == []

    def test_missing_rtl_path_rejects_architecture(self, example_workspace):
        data = load_arch_yaml()
        del data["rtl_path"]
        save_arch_yaml(data)
        _, instances = self.resolve()
        assert instances == []

    def test_missing_mandatory_key_rejects_architecture(self, example_workspace):
        data = load_arch_yaml()
        del data["top_level_module"]
        save_arch_yaml(data)
        _, instances = self.resolve()
        assert instances == []

    def test_use_parameters_false_accepts_without_delimiters(self, example_workspace):
        data = load_arch_yaml()
        data["use_parameters"] = False
        data.pop("start_delimiter", None)
        data.pop("stop_delimiter", None)
        save_arch_yaml(data)
        _, instances = self.resolve()
        assert len(instances) == 1
        assert instances[0].use_parameters is False

    def test_missing_delimiter_with_use_parameters_rejects(self, example_workspace):
        data = load_arch_yaml()
        data["use_parameters"] = True
        data.pop("start_delimiter", None)
        save_arch_yaml(data)
        _, instances = self.resolve()
        assert instances == []

    def test_global_frequency_bounds_fallback(self, example_workspace):
        # remove the target-specific override: global bounds must apply
        data = load_arch_yaml()
        del data[TARGET]
        save_arch_yaml(data)
        _, instances = self.resolve()
        assert len(instances) == 1
        assert int(instances[0].fmax_lower_bound) == 50
        assert int(instances[0].fmax_upper_bound) == 1500

    def test_wrong_type_for_bounds_rejects(self, example_workspace):
        data = load_arch_yaml()
        del data[TARGET]
        data["fmax_synthesis"] = {"lower_bound": "not_a_number", "upper_bound": 900}
        save_arch_yaml(data)
        handler, instances = self.resolve()
        # either rejected or fell back: it must not crash, and never keep the bogus value
        for arch in instances:
            assert str(arch.fmax_lower_bound) != "not_a_number"


######################################
# EDA target file variations (integration, example workspace)
######################################

TARGET_FILE = "odatix_userconfig/target_vivado.yml"


@pytest.mark.integration
class TestTargetFileVariations:
    def resolve(self):
        from test_handlers import make_arch_handler

        handler = make_arch_handler()
        return handler.get_architectures(ARCH_REQUEST, [TARGET], run_mode="fmax", timestamp="ts")

    def test_script_copy_missing_source_is_disabled(self, example_workspace):
        with open(TARGET_FILE, "w") as f:
            f.write("script_copy_enable: yes\nscript_copy_source: /does/not/exist\ntargets: [%s]\n" % TARGET)
        instances = self.resolve()
        assert len(instances) == 1
        assert instances[0].script_copy_enable is False

    def test_minimal_target_file(self, example_workspace):
        with open(TARGET_FILE, "w") as f:
            f.write("targets: [%s]\n" % TARGET)
        instances = self.resolve()
        assert len(instances) == 1


######################################
# Generic workspace YAML helpers
######################################

class TestWorkspaceYamlFiles:
    def test_load_yaml_invalid_returns_default(self, tmp_path):
        f = tmp_path / "f.yml"
        f.write_text("a: [unclosed")
        assert ws.load_yaml_file(str(f), default={"fallback": True}) == {"fallback": True}

    def test_load_yaml_empty_returns_default(self, tmp_path):
        f = tmp_path / "f.yml"
        f.write_text("")
        assert ws.load_yaml_file(str(f), default={"d": 1}) == {"d": 1}

    def test_load_architecture_settings_empty_file(self, tmp_path):
        arch_root = tmp_path / "archs"
        (arch_root / "archA").mkdir(parents=True)
        (arch_root / "archA" / "_settings.yml").write_text("")
        assert ws.load_architecture_settings(str(arch_root), "archA") == {}

    def test_load_architecture_settings_missing_file(self, tmp_path):
        arch_root = tmp_path / "archs"
        (arch_root / "archA").mkdir(parents=True)
        assert ws.load_architecture_settings(str(arch_root), "archA") == {}
