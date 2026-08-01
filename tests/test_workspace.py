"""Tests for odatix.workspace: the workspace configuration API."""

import os

import pytest

import odatix.lib.hard_settings as hard_settings
from odatix.workspace import (
    AlreadyExistsError,
    ArchitectureCollection,
    ArchitectureSettings,
    InvalidNameError,
    NotFoundError,
    SimulationCollection,
    Workspace,
    WorkflowCollection,
    combinations,
    count_combinations,
)
from odatix.workspace.configs import variable_definition
from odatix.workspace.jobs import (
    FmaxBoundsSettings,
    FrequenciesSettings,
    JobConfig,
    job_config,
)
from odatix.workspace.settings import Setting, Settings
from odatix.workspace.targets import TargetFile
from odatix.workspace.tools import ToolSettings
from odatix.workspace.yaml_io import read_yaml

MAIN = hard_settings.main_parameter_domain


@pytest.fixture
def architectures(tmp_path):
    root = tmp_path / "architectures"
    root.mkdir()
    return ArchitectureCollection(None, str(root))


@pytest.fixture
def workflows(tmp_path):
    root = tmp_path / "workflows"
    root.mkdir()
    return WorkflowCollection(None, str(root))


@pytest.fixture
def simulations(tmp_path):
    root = tmp_path / "simulations"
    root.mkdir()
    return SimulationCollection(None, str(root))


######################################
# Collections
######################################

class TestCollections:
    def test_create_and_list(self, architectures):
        architectures.create("archA")
        assert "archA" in architectures
        assert architectures.names() == ["archA"]

    def test_iterating_yields_entries(self, architectures):
        architectures.create("archA")
        architectures.create("archB")
        assert [entry.name for entry in architectures] == ["archA", "archB"]
        assert len(architectures) == 2

    def test_getitem_raises_when_missing(self, architectures):
        with pytest.raises(NotFoundError):
            architectures["nope"]

    def test_get_returns_none_when_missing(self, architectures):
        assert architectures.get("nope") is None

    def test_entry_works_before_creation(self, architectures):
        entry = architectures.entry("not_yet")
        assert not entry.exists
        assert entry.settings == ArchitectureSettings()

    def test_duplicate(self, architectures):
        architectures.create("archA")
        architectures.duplicate("archA", "archB")
        assert architectures.names() == ["archA", "archB"]

    def test_rename(self, architectures):
        architectures.create("archA")
        architectures.rename("archA", "archZ")
        assert architectures.names() == ["archZ"]

    def test_delete(self, architectures):
        architectures.create("archA")
        architectures.delete("archA")
        assert architectures.names() == []

    def test_duplicate_missing_source_raises(self, architectures):
        with pytest.raises(NotFoundError):
            architectures.duplicate("nope", "copy")

    def test_duplicate_existing_target_raises(self, architectures):
        architectures.create("a")
        architectures.create("b")
        with pytest.raises(AlreadyExistsError):
            architectures.duplicate("a", "b")

    def test_create_existing_raises(self, architectures):
        architectures.create("a")
        with pytest.raises(AlreadyExistsError):
            architectures.create("a")

    def test_invalid_name_is_refused(self, architectures):
        with pytest.raises(InvalidNameError):
            architectures.create("with space")
        with pytest.raises(InvalidNameError):
            architectures.create("")


######################################
# Architecture settings
######################################

class TestArchitectureSettings:
    def test_settings_round_trip(self, architectures):
        architecture = architectures.create("archA")
        architecture.settings.rtl_path = "rtl/archA"
        architecture.settings.top_level_module = "top"
        architecture.settings.use_parameters = True
        architecture.save()

        reloaded = architectures["archA"]
        assert reloaded.settings.rtl_path == "rtl/archA"
        assert reloaded.settings.top_level_module == "top"
        assert reloaded.settings.use_parameters is True

    def test_values_are_coerced_to_their_type(self, architectures):
        architecture = architectures.entry("archA")
        architecture.settings.use_parameters = "Yes"
        architecture.settings.fmax_synthesis.lower_bound = "50"
        assert architecture.settings.use_parameters is True
        assert architecture.settings.fmax_synthesis.lower_bound == 50

    def test_settings_are_also_a_mapping(self, architectures):
        architecture = architectures.entry("archA")
        architecture.settings["top_level_module"] = "top"
        assert architecture.settings.top_level_module == "top"
        assert dict(architecture.settings.items())["top_level_module"] == "top"

    def test_unknown_keys_are_kept(self, architectures):
        architecture = architectures.create("archA")
        with open(architecture.settings_path, "w") as f:
            f.write("rtl_path: rtl\nxc7a100t:\n  fmax_synthesis:\n    lower_bound: 100\n")

        architecture = architectures["archA"]
        assert "xc7a100t" in architecture.settings.extra
        architecture.settings.top_level_module = "top"
        architecture.save()

        written = read_yaml(architecture.settings_path)
        assert written["xc7a100t"] == {"fmax_synthesis": {"lower_bound": 100}}
        assert written["top_level_module"] == "top"

    def test_saving_keeps_comments_and_untouched_values(self, architectures):
        architecture = architectures.create("archA")
        with open(architecture.settings_path, "w") as f:
            f.write("# my own comment\nrtl_path: \"rtl/archA\"\ntop_level_module: top\n")

        architecture = architectures["archA"]
        architecture.settings.top_level_module = "other"
        architecture.save()

        content = open(architecture.settings_path).read()
        assert "# my own comment" in content
        assert 'rtl_path: "rtl/archA"' in content  # untouched, quoting included
        assert "top_level_module: other" in content

    def test_a_generated_file_carries_its_sections(self, architectures):
        architecture = architectures.create("archA")
        architecture.settings.rtl_path = "rtl"
        architecture.save()
        content = open(architecture.settings_path).read()
        assert "# Settings for archA" in content
        assert "# Source files" in content
        assert "# Signals" in content

    def test_mutually_exclusive_settings_never_coexist(self, architectures):
        architecture = architectures.create("archA")
        architecture.settings.rtl_path = "rtl"
        architecture.save()
        assert "rtl_path" in read_yaml(architecture.settings_path)

        architecture.settings.generate_rtl = True
        architecture.settings.generate_command = "make rtl"
        architecture.settings.design_path = "src"
        architecture.save()

        written = read_yaml(architecture.settings_path)
        assert "rtl_path" not in written
        assert written["generate_command"] == "make rtl"

    def test_unset_bounds_are_not_written(self, architectures):
        architecture = architectures.create("archA")
        architecture.settings.fmax_synthesis.lower_bound = 50
        architecture.save()
        written = read_yaml(architecture.settings_path)
        assert written["fmax_synthesis"] == {"lower_bound": 50}

    def test_update_saves_in_one_call(self, architectures):
        architectures.create("archA").update(top_level_module="top")
        assert architectures["archA"].settings.top_level_module == "top"


######################################
# Parameter domains
######################################

class TestParameterDomains:
    def test_an_architecture_always_has_a_main_domain(self, architectures):
        architecture = architectures.create("archA")
        assert architecture.domains.main.exists
        assert architecture.domains.names() == [MAIN]

    def test_create_domain(self, architectures):
        architecture = architectures.create("archA")
        architecture.domains.create("voltage")
        assert architecture.domains.sub_names() == ["voltage"]
        assert architecture.domains.names() == [MAIN, "voltage"]

    def test_domain_settings_are_their_own_kind(self, architectures):
        architecture = architectures.create("archA")
        domain = architecture.domains.create("voltage", param_target_file="rtl/top.v")
        assert domain.settings.use_parameters is True  # a domain substitutes by default
        assert read_yaml(domain.settings_path)["param_target_file"] == "rtl/top.v"

    def test_rename_domain(self, architectures):
        architecture = architectures.create("archA")
        architecture.domains.create("old")
        architecture.domains.rename("old", "new")
        assert architecture.domains.sub_names() == ["new"]

    def test_delete_domain(self, architectures):
        architecture = architectures.create("archA")
        architecture.domains.create("tmp")
        architecture.domains.delete("tmp")
        assert architecture.domains.sub_names() == []

    def test_the_main_domain_cannot_be_deleted_or_renamed(self, architectures):
        architecture = architectures.create("archA")
        with pytest.raises(InvalidNameError):
            architecture.domains.main.delete()
        with pytest.raises(InvalidNameError):
            architecture.domains.main.rename("other")

    def test_duplicating_the_main_domain_keeps_only_domain_settings(self, architectures):
        architecture = architectures.create("archA")
        architecture.settings.rtl_path = "rtl"
        architecture.settings.use_parameters = True
        architecture.settings.start_delimiter = "("
        architecture.save()
        architecture.configs.write("08bits", "WIDTH = 8")

        copy = architecture.domains.duplicate(MAIN, "copy")
        assert copy.configs.names() == ["08bits"]
        written = read_yaml(copy.settings_path)
        assert written["start_delimiter"] == "("
        assert "rtl_path" not in written  # not something a domain owns

    def test_duplicate_to_main_is_refused(self, architectures):
        architecture = architectures.create("archA")
        architecture.domains.create("d")
        with pytest.raises(InvalidNameError):
            architecture.domains.duplicate("d", MAIN)

    def test_a_domain_without_settings_substitutes_nothing(self, architectures):
        architecture = architectures.create("archA")
        domain = architecture.domains.create("empty")
        assert domain.use_parameters is False


######################################
# Configurations
######################################

class TestConfigurations:
    def test_write_read_delete(self, architectures):
        architecture = architectures.create("archA")
        architecture.configs.write("08bits", "parameter WIDTH = 8")
        assert architecture.configs.names() == ["08bits"]
        assert architecture.configs["08bits"].read() == "parameter WIDTH = 8"
        architecture.configs.delete("08bits")
        assert architecture.configs.names() == []

    def test_the_extension_is_not_part_of_the_name(self, architectures):
        architecture = architectures.create("archA")
        architecture.configs.write("08bits.txt", "x")
        assert architecture.configs.names() == ["08bits"]
        assert architecture.configs.filenames() == ["08bits.txt"]
        assert os.path.isfile(os.path.join(architecture.path, "08bits.txt"))

    def test_clear(self, architectures):
        architecture = architectures.create("archA")
        for name in ("a", "b"):
            architecture.configs.write(name, "x")
        architecture.configs.clear()
        assert architecture.configs.names() == []

    def test_rename_and_duplicate(self, architectures):
        architecture = architectures.create("archA")
        architecture.configs.write("a", "content")
        architecture.configs.duplicate("a", "b")
        assert architecture.configs["b"].read() == "content"
        architecture.configs.rename("a", "c")
        assert architecture.configs.names() == ["b", "c"]

    def test_create_existing_raises(self, architectures):
        architecture = architectures.create("archA")
        architecture.configs.write("a", "x")
        with pytest.raises(AlreadyExistsError):
            architecture.configs.create("a")


######################################
# Configuration generation
######################################

class TestConfigurationGeneration:
    def test_generate_writes_the_configurations(self, architectures):
        architecture = architectures.create("archA")
        architecture.settings.generate_configurations = True
        architecture.settings.generate_configurations_settings.name = "${width}bits"
        architecture.settings.generate_configurations_settings.template = "WIDTH = ${width}"
        architecture.settings.generate_configurations_settings.set_variable(
            "width", "range", {"from": 8, "to": 16, "step": 8}
        )
        architecture.save()

        written = architecture.domains.main.generate_configurations()
        assert written == ["8bits", "16bits"]
        assert architecture.configs["8bits"].read() == "WIDTH = 8"

    def test_preview_writes_nothing(self, architectures):
        architecture = architectures.entry("archA")
        architecture.settings.generate_configurations = True
        architecture.settings.generate_configurations_settings.name = "${w}"
        architecture.settings.generate_configurations_settings.template = "W = ${w}"
        architecture.settings.generate_configurations_settings.set_variable(
            "w", "list", {"list": [1, 2]}
        )
        preview = architecture.domains.main.preview_configurations()
        assert sorted(preview) == ["1", "2"]
        assert not architecture.exists

    def test_existing_configurations_are_kept_without_overwrite(self, architectures):
        architecture = architectures.create("archA")
        architecture.settings.generate_configurations = True
        architecture.settings.generate_configurations_settings.name = "${w}"
        architecture.settings.generate_configurations_settings.template = "W = ${w}"
        architecture.settings.generate_configurations_settings.set_variable("w", "list", {"list": [1]})
        architecture.save()
        architecture.configs.write("1", "hand written")

        assert architecture.domains.main.generate_configurations() == []
        assert architecture.configs["1"].read() == "hand written"
        architecture.domains.main.generate_configurations(overwrite=True)
        assert architecture.configs["1"].read() == "W = 1"

    def test_list_variables_stay_inline(self, architectures):
        architecture = architectures.create("archA")
        architecture.settings.generate_configurations = True
        architecture.settings.generate_configurations_settings.name = "${w}"
        architecture.settings.generate_configurations_settings.template = "W = ${w}"
        architecture.settings.generate_configurations_settings.set_variable("w", "list", {"list": [1, 2]})
        architecture.save()
        assert "list: [1, 2]" in open(architecture.settings_path).read()

    def test_variable_definition_helper(self):
        assert variable_definition("X", "range", {"from": 1, "to": 4}) == {
            "X": {"type": "range", "settings": {"from": 1, "to": 4}}
        }
        assert variable_definition("X", "range", {}, format="%02d")["X"]["format"] == "%02d"


######################################
# Combinations
######################################

class TestCombinations:
    def test_count(self):
        assert count_combinations({"a": [1, 2], "b": [1, 2, 3]}) == 6

    def test_count_empty(self):
        assert count_combinations({}) == 0

    def test_main_domain(self):
        assert combinations({MAIN: ["c1", "c2"]}, "arch") == [["arch/c1"], ["arch/c2"]]

    def test_extra_domain(self):
        assert combinations({MAIN: ["c1"], "corner": ["tt", "ss"]}, "arch") == [
            ["arch/c1", "corner/tt"],
            ["arch/c1", "corner/ss"],
        ]

    def test_empty(self):
        assert combinations({}, "arch") == []

    def test_an_architecture_knows_its_own(self, architectures):
        architecture = architectures.create("archA")
        architecture.update(use_parameters=True)
        architecture.configs.write("c1", "x")
        domain = architecture.domains.create("corner", use_parameters=True)
        domain.configs.write("tt", "x")
        assert architecture.count_combinations() == 1
        assert architecture.combinations() == [["archA/c1", "corner/tt"]]


######################################
# Simulations and workflows
######################################

class TestSimulations:
    def test_settings_round_trip(self, simulations):
        simulation = simulations.create("TB_X")
        simulation.update(param_target_file="tb/tb.vhdl", use_parameters=True)
        assert simulations["TB_X"].settings.param_target_file == "tb/tb.vhdl"

    def test_metrics_round_trip(self, simulations):
        simulation = simulations.create("TB_X")
        metrics = simulation.metrics
        metrics.set("cycles", {"type": "csv"})
        metrics.metadata = {"run": {"type": "csv"}}
        metrics.save()

        reloaded = simulations["TB_X"].metrics
        assert reloaded.metrics == {"cycles": {"type": "csv"}}
        assert reloaded.metadata == {"run": {"type": "csv"}}

    def test_legacy_metrics_layout_is_migrated_on_write(self, simulations):
        simulation = simulations.create("TB_X")
        with open(simulation.metrics_path, "w") as f:
            f.write("cycles:\n  type: csv\n")
        metrics = simulation.metrics
        assert metrics.metrics == {"cycles": {"type": "csv"}}
        metrics.save()
        assert read_yaml(simulation.metrics_path)["metrics"] == {"cycles": {"type": "csv"}}


class TestWorkflows:
    def test_create_and_list(self, workflows):
        workflows.create("wf1")
        assert "wf1" in workflows
        assert workflows.names() == ["wf1"]

    def test_rename_and_delete(self, workflows):
        workflows.create("wf1")
        workflows.rename("wf1", "wf2")
        assert workflows.names() == ["wf2"]
        workflows.delete("wf2")
        assert workflows.names() == []

    def test_settings_round_trip(self, workflows):
        workflow = workflows.create("wf1")
        workflow.settings.sources.path = "examples/wf"
        workflow.settings.tasks = [{"name": "main", "commands": ["make"]}]
        workflow.save()

        reloaded = workflows["wf1"]
        assert reloaded.settings.sources.path == "examples/wf"
        assert reloaded.settings.tasks[0]["name"] == "main"

    def test_unknown_keys_are_kept(self, workflows):
        workflow = workflows.create("wf1")
        workflow.settings["custom_key"] = "value1"
        workflow.save()
        assert workflows["wf1"].settings["custom_key"] == "value1"

    def test_a_workflow_sweeps_like_an_architecture(self, workflows):
        workflow = workflows.create("wf1")
        workflow.update(use_parameters=True)
        workflow.configs.write("small", "x")
        assert workflow.combinations() == [["wf1/small"]]


######################################
# Run settings files
######################################

class TestJobConfigs:
    def test_workflow_selection_uses_the_workflows_key(self, tmp_path):
        path = str(tmp_path / "workflow_settings.yml")
        config = job_config(path, "workflow")
        config.settings.workflows = ["wf1/default", "wf2 + d/v"]
        config.save()

        data = read_yaml(path)
        assert data["workflows"] == ["wf1/default", "wf2 + d/v"]
        assert "architectures" not in data
        assert "frequencies" not in data
        assert "force_single_thread" in data

    def test_workflow_selection_is_read_by_run_workflow(self, tmp_path):
        from odatix.lib.run_settings import get_workflow_settings

        path = str(tmp_path / "workflow_settings.yml")
        config = job_config(path, "workflow")
        config.settings.workflows = ["wf1"]
        config.save()
        *_, workflows = get_workflow_settings(path)
        assert workflows == ["wf1"]

    def test_fmax_selection_uses_the_architectures_key(self, tmp_path):
        path = str(tmp_path / "fmax_settings.yml")
        config = job_config(path, "fmax_synthesis")
        config.settings.architectures = ["arch1/08bits"]
        config.settings.fmax_synthesis.lower_bound = 50
        config.save()

        data = read_yaml(path)
        assert data["architectures"] == ["arch1/08bits"]
        assert data["fmax_synthesis"]["lower_bound"] == 50
        assert "workflows" not in data
        assert "tools" not in data

    def test_analysis_writes_its_tools(self, tmp_path):
        path = str(tmp_path / "analysis_settings.yml")
        config = job_config(path, "analysis")
        config.settings.tools = ["vivado", "verilator"]
        config.settings.architectures = ["arch1/08bits"]
        config.save()

        assert read_yaml(path)["tools"] == ["vivado", "verilator"]
        assert job_config(path, "analysis").settings.tools == ["vivado", "verilator"]

    def test_a_scalar_tools_key_is_read_as_a_list(self, tmp_path):
        path = tmp_path / "analysis_settings.yml"
        path.write_text("tools: verilator\n")
        assert job_config(str(path), "analysis").settings.tools == ["verilator"]

    def test_a_missing_file_reads_as_defaults(self, tmp_path):
        config = job_config(str(tmp_path / "nope.yml"), "analysis")
        assert config.settings.tools == []
        assert config.settings.nb_jobs == 8

    def test_simulation_selection_round_trip(self, tmp_path):
        path = str(tmp_path / "simulations_settings.yml")
        config = job_config(path, "simulation")
        config.settings.simulations = {"TB_X": ["Arch/04bits"]}
        config.save()

        assert read_yaml(path)["simulations"] == [{"TB_X": ["Arch/04bits"]}]
        assert job_config(path, "simulation").settings.simulations == {"TB_X": ["Arch/04bits"]}

    def test_the_selection_is_reachable_whatever_the_run_calls_it(self, tmp_path):
        config = job_config(str(tmp_path / "pnr.yml"), "pnr")
        config.selection = ["fmax_synthesis/vivado/target/arch/config"]
        assert config.settings.sources == ["fmax_synthesis/vivado/target/arch/config"]

    def test_disabled_frequencies_are_remembered(self, tmp_path):
        path = str(tmp_path / "custom_freq.yml")
        config = job_config(path, "custom_freq_synthesis")
        config.settings.frequencies.frequencies = [50, 100]
        config.settings.frequencies.use_custom_freq_list = False
        config.save()

        data = read_yaml(path)
        assert "list" not in data["frequencies"]
        assert data["frequencies"]["disabled_list"] == [50, 100]

        reloaded = job_config(path, "custom_freq_synthesis").settings.frequencies
        assert reloaded.frequencies == [50, 100]
        assert reloaded.use_custom_freq_list is False

    def test_frequencies_form_values(self):
        frequencies = FrequenciesSettings.from_dict({"list": [50], "range": {"from": 1, "to": 2, "step": 1}})
        assert frequencies.to_dict()["list"] == [50]
        assert frequencies.to_dict()["range"] == {"from": 1, "to": 2, "step": 1}
        assert frequencies.use_custom_freq_list is True

    def test_fmax_bounds_are_written_empty_when_unset(self, tmp_path):
        path = str(tmp_path / "fmax.yml")
        config = job_config(path, "fmax_synthesis")
        config.settings.fmax_synthesis = FmaxBoundsSettings(override=True)
        config.save()
        data = read_yaml(path)
        assert data["fmax_synthesis"]["lower_bound"] == ""
        assert "override: Yes" in open(path).read()

    def test_an_unknown_mode_still_selects_architectures(self, tmp_path):
        config = JobConfig(None, "something_else", str(tmp_path / "x.yml"))
        config.settings.architectures = ["a"]
        config.save()
        assert read_yaml(str(tmp_path / "x.yml"))["architectures"] == ["a"]


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
def target_file(tmp_path):
    (tmp_path / "target_vivado.yml").write_text(TARGET_FILE_CONTENT)
    return TargetFile(None, "vivado", target_path=str(tmp_path))


class TestTargets:
    def test_list(self, target_file):
        assert target_file.names() == ["xc7a100t-csg324-1", "xc7k70t-fbg676-2"]
        assert target_file.enabled_names() == target_file.names()
        assert all(not target.script_copy_enable for target in target_file)

    def test_missing_file(self, tmp_path):
        assert TargetFile(None, "unknown_tool", target_path=str(tmp_path)).names() == []

    def test_contains(self, target_file):
        assert "xc7a100t-csg324-1" in target_file
        assert "nope" not in target_file
        with pytest.raises(NotFoundError):
            target_file["nope"]

    def test_commented_entries_are_disabled_targets(self, tmp_path):
        (tmp_path / "target_vivado.yml").write_text(COMMENTED_TARGET_FILE_CONTENT)
        targets = TargetFile(None, "vivado", target_path=str(tmp_path))
        assert [(target.name, target.enabled) for target in targets] == [
            ("xc7s6-cpga196-1", False),
            ("xc7s25-csga225-1", False),
            ("xc7a100t-csg324-1", True),
            ("xc7k70t-fbg676-2", False),
        ]

    def test_disabling_keeps_the_target_as_a_comment(self, target_file):
        target_file.disable("xc7k70t-fbg676-2")

        # the run flow only sees the enabled target...
        assert read_yaml(target_file.path)["targets"] == ["xc7a100t-csg324-1"]
        # ...but the disabled one stays as a commented-out entry
        assert "# - xc7k70t-fbg676-2" in open(target_file.path).read()

        target_file.reload().enable("xc7k70t-fbg676-2")
        assert read_yaml(target_file.path)["targets"] == ["xc7a100t-csg324-1", "xc7k70t-fbg676-2"]
        assert "# - xc7k70t-fbg676-2" not in open(target_file.path).read()

    def test_saving_without_a_change_is_stable(self, tmp_path):
        (tmp_path / "target_vivado.yml").write_text(COMMENTED_TARGET_FILE_CONTENT)
        target_file = TargetFile(None, "vivado", target_path=str(tmp_path))
        before = [target.to_dict() for target in target_file]
        target_file.save()
        assert [target.to_dict() for target in target_file.reload()] == before

        content = (tmp_path / "target_vivado.yml").read_text()
        assert "# FPGA target" in content
        assert content.count("# - xc7s6-cpga196-1") == 1

    def test_legacy_disabled_targets_key_is_read_and_migrated(self, tmp_path):
        (tmp_path / "target_vivado.yml").write_text("targets:\n  - a\ndisabled_targets:\n  - b\n")
        target_file = TargetFile(None, "vivado", target_path=str(tmp_path))
        assert [(target.name, target.enabled) for target in target_file] == [("a", True), ("b", False)]

        target_file.save()
        assert "disabled_targets" not in read_yaml(target_file.path)
        assert "# - b" in (tmp_path / "target_vivado.yml").read_text()

    def test_saving_preserves_the_rest_of_the_file(self, target_file):
        target_file.save()
        content = open(target_file.path).read()
        assert "constraint_file: constraints.xdc" in content
        assert "# Target settings for vivado" in content
        assert 'tool_install_path: ""' in content

    def test_script_copy_settings_round_trip(self, target_file):
        target = target_file["xc7a100t-csg324-1"]
        target.script_copy_enable = True
        target.script_copy_source = "/path/to/script.tcl"
        target_file.save()

        settings = read_yaml(target_file.path)["target_settings"]["xc7a100t-csg324-1"]
        assert settings["script_copy_enable"] is True
        assert settings["script_copy_source"] == "/path/to/script.tcl"

        target = target_file.reload()["xc7a100t-csg324-1"]
        assert target.script_copy_enable is True
        target.script_copy_enable = False
        target_file.save()
        assert "target_settings" not in read_yaml(target_file.path)

    def test_rename_carries_per_target_settings(self, target_file):
        target = target_file["xc7a100t-csg324-1"]
        target.script_copy_enable = True
        target.script_copy_source = "/s.tcl"
        target_file.save()

        target_file.reload().rename("xc7a100t-csg324-1", "renamed-target")
        data = read_yaml(target_file.path)
        assert "renamed-target" in data["targets"]
        assert data["target_settings"]["renamed-target"]["script_copy_source"] == "/s.tcl"
        assert "xc7a100t-csg324-1" not in data["target_settings"]

    def test_add(self, target_file):
        target_file.add("new-target")
        assert "new-target" in target_file.reload()

    def test_add_existing_raises(self, target_file):
        with pytest.raises(AlreadyExistsError):
            target_file.add("xc7a100t-csg324-1")

    def test_add_creates_the_file(self, tmp_path):
        target_file = TargetFile(None, "genus", target_path=str(tmp_path))
        target_file.add("asap7")
        assert TargetFile(None, "genus", target_path=str(tmp_path)).names() == ["asap7"]

    def test_duplicate(self, target_file):
        target = target_file["xc7a100t-csg324-1"]
        target.script_copy_enable = True
        target.script_copy_source = "/s.tcl"
        target_file.save()

        target_file.duplicate("xc7a100t-csg324-1", "copy-1")
        assert target_file.reload()["copy-1"].script_copy_source == "/s.tcl"

    def test_duplicate_missing_source_raises(self, target_file):
        with pytest.raises(NotFoundError):
            target_file.duplicate("nope", "copy")

    def test_remove(self, target_file):
        target_file.remove("xc7a100t-csg324-1")
        target_file.reload()
        assert "xc7a100t-csg324-1" not in target_file
        assert "xc7k70t-fbg676-2" in target_file

    def test_empty_and_duplicate_names_are_skipped_on_save(self, target_file):
        target_file.targets = [
            {"name": "", "enabled": True},
            {"name": "a", "enabled": True},
            {"name": "a", "enabled": False},
        ]
        target_file.save()
        targets = list(target_file.reload())
        assert [target.name for target in targets] == ["a"]
        assert targets[0].enabled is True

    def test_an_empty_name_falls_back_to_the_original(self, target_file):
        target_file.targets = [{"name": "", "original_name": "kept", "enabled": True}]
        target_file.save()
        assert "kept" in target_file.reload()


######################################
# Tools
######################################

class TestTools:
    def test_a_workspace_tool_round_trips(self, tmp_path):
        workspace = Workspace.from_dict({"tools_path": "tools"}, root=str(tmp_path))
        tool = workspace.tools.create("my_tool", label="My Tool")
        tool.settings.report_path = "reports"
        flow = tool.settings.default_flow
        flow.set_command("fmax_synthesis", ["make fmax"])
        tool.save()

        reloaded = workspace.tools["my_tool"]
        assert reloaded.settings.label == "My Tool"
        assert reloaded.settings.report_path == "reports"
        assert reloaded.settings.default_flow.command("fmax_synthesis") == ["make fmax"]
        assert not reloaded.is_builtin

    def test_a_builtin_name_cannot_be_taken(self, tmp_path):
        workspace = Workspace.from_dict({"tools_path": "tools"}, root=str(tmp_path))
        with pytest.raises(AlreadyExistsError):
            workspace.tools.create("vivado")

    def test_builtin_tools_are_listed_apart(self, tmp_path):
        workspace = Workspace.from_dict({"tools_path": "tools"}, root=str(tmp_path))
        assert "vivado" in workspace.tools.builtin_names()
        assert "vivado" not in workspace.tools.names()
        assert "vivado" in workspace.tools.all_names()

    def test_an_overlay_only_holds_what_it_overrides(self, tmp_path):
        workspace = Workspace.from_dict({"tools_path": "tools"}, root=str(tmp_path))
        tool = workspace.tools["vivado"]
        assert tool.is_builtin
        assert not tool.has_overlay

        tool.settings.label = "My Vivado"
        tool.save()

        assert tool.has_overlay
        written = read_yaml(tool.settings_path)
        assert written["label"] == "My Vivado"
        assert "unix" not in written  # the built-in commands stay Odatix's
        assert workspace.tools["vivado"].effective_settings.label == "My Vivado"

    def test_an_overlay_with_nothing_left_is_removed(self, tmp_path):
        workspace = Workspace.from_dict({"tools_path": "tools"}, root=str(tmp_path))
        tool = workspace.tools["vivado"]
        tool.settings.label = "My Vivado"
        tool.save()
        assert tool.has_overlay

        tool.settings.label = tool.builtin_settings.label
        tool.save()
        assert not tool.has_overlay

    def test_steps_and_commands_round_trip(self, tmp_path):
        workspace = Workspace.from_dict({"tools_path": "tools"}, root=str(tmp_path))
        tool = workspace.tools.create("my_tool")
        flow = tool.settings.default_flow
        flow.set_steps("fmax_synthesis", [
            {"name": "synth", "command": ["make synth"], "default": True},
            {"name": "route", "command": ["make route"]},
        ])
        tool.save()

        steps = workspace.tools["my_tool"].settings.default_flow.steps("fmax_synthesis")
        assert [step.name for step in steps] == ["synth", "route"]
        assert steps[0].default is True

    def test_settings_read_back_from_their_own_shape(self):
        settings = ToolSettings(label="X")
        settings.add_flow("other")
        assert ToolSettings.from_dict(settings.to_dict()).flow_names() == settings.flow_names()

    def test_tool_metrics_round_trip(self, tmp_path):
        workspace = Workspace.from_dict({"tools_path": "tools"}, root=str(tmp_path))
        tool = workspace.tools.create("my_tool")
        metrics = tool.metrics
        metrics.set("area", {"type": "regex"}, "fmax_synthesis_metrics")
        metrics.save()
        assert workspace.tools["my_tool"].metrics.sections["fmax_synthesis_metrics"] == {
            "area": {"type": "regex"}
        }


######################################
# Workspace
######################################

class TestWorkspace:
    def test_paths_fall_back_to_the_odatix_defaults(self, tmp_path):
        workspace = Workspace.open(str(tmp_path))
        assert not workspace.exists
        assert workspace.paths.arch_path == os.path.join(str(tmp_path), "odatix_userconfig", "architectures")

    def test_open_can_require_a_workspace(self, tmp_path):
        from odatix.workspace import NotAWorkspaceError

        with pytest.raises(NotAWorkspaceError):
            Workspace.open(str(tmp_path), required=True)

    def test_settings_win_over_the_defaults(self, tmp_path):
        workspace = Workspace.from_dict({"arch_path": "my_archs"}, root=str(tmp_path))
        assert workspace.paths.arch_path == os.path.join(str(tmp_path), "my_archs")

    def test_absolute_paths_are_left_alone(self, tmp_path):
        workspace = Workspace.from_dict({"arch_path": "/somewhere/archs"}, root=str(tmp_path))
        assert workspace.paths.arch_path == "/somewhere/archs"

    def test_everything_hangs_off_the_workspace(self, tmp_path):
        workspace = Workspace.open(str(tmp_path))
        architecture = workspace.architectures.create("archA")
        assert architecture.path.startswith(str(tmp_path))
        assert workspace.architectures.names() == ["archA"]
        assert workspace.simulations.names() == []
        assert workspace.workflows.names() == []
        assert workspace.jobs.fmax_synthesis.path.startswith(str(tmp_path))

    def test_save_settings(self, tmp_path):
        workspace = Workspace.open(str(tmp_path))
        workspace.save_settings(arch_path="my_archs")
        assert Workspace.open(str(tmp_path)).paths.arch_path == os.path.join(str(tmp_path), "my_archs")

    def test_derived_metrics_round_trip(self, tmp_path):
        workspace = Workspace.open(str(tmp_path))
        derived = workspace.derived_metrics
        derived.set("efficiency", {"operation": "a / b"})
        derived.set_group("all", {"pattern": "*"})
        derived.save()

        reloaded = workspace.derived_metrics
        assert reloaded.metrics == {"efficiency": {"operation": "a / b"}}
        assert reloaded.groups == {"all": {"pattern": "*"}}


######################################
# The settings engine itself
######################################

class SampleSettings(Settings):
    name = Setting("", type="str")
    count = Setting(1, type="int")
    enabled = Setting(False, type="bool", style="yesno")
    items = Setting(factory=list, type="int_list")


class TestSettingsEngine:
    def test_defaults_are_not_shared(self):
        first, second = SampleSettings(), SampleSettings()
        first.items.append(1)
        assert second.items == []

    def test_types_are_coerced(self):
        settings = SampleSettings.from_dict({"count": "3", "enabled": "Yes", "items": "1, 2"})
        assert settings.count == 3
        assert settings.enabled is True
        assert settings.items == [1, 2]

    def test_unknown_keys_land_in_extra(self):
        settings = SampleSettings.from_dict({"name": "x", "other": 1})
        assert settings.extra == {"other": 1}
        assert settings.to_dict()["other"] == 1

    def test_equality_against_a_mapping(self):
        settings = SampleSettings(name="x")
        assert settings == SampleSettings(name="x")
        assert settings != SampleSettings(name="y")
        assert settings == settings.to_dict()

    def test_mapping_access(self):
        settings = SampleSettings()
        settings["name"] = "x"
        assert settings["name"] == "x"
        assert "name" in settings
        assert settings.get("nope") is None

    def test_update(self):
        settings = SampleSettings().update({"name": "x"}, count=2)
        assert (settings.name, settings.count) == ("x", 2)
