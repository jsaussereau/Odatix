"""Tests for virtual parameter domains (odatix.lib.virtual_param_domain).

Virtual parameter domains are the variables of an instance
(``generate_configurations_settings.variables``) used as parameter domains: they
expand into one job per combination and their values can be referenced as
``${variable}`` in commands. These tests cover the architecture side
(``generate_command``); the workflow side (task commands) is exercised through
the same shared helpers.
"""

import os

import pytest
import yaml

import odatix.lib.hard_settings as hard_settings
import odatix.lib.virtual_param_domain as vpd
from odatix.lib.architecture_handler import ArchitectureHandler
from odatix.lib.settings import OdatixSettings


######################################
# Pure helpers
######################################

class TestHelpers:
    def test_referenced_variable_names_finds_both_syntaxes(self):
        assert vpd.referenced_variable_names("make W=${width} S=$seed") == {"width", "seed"}

    def test_referenced_variable_names_ignores_non_strings(self):
        assert vpd.referenced_variable_names(None, 42, "${a}") == {"a"}

    def test_replace_command_vars_leaves_unknown_names_alone(self):
        command = "make W=${width} OUT=$HOME/build"
        assert vpd.replace_command_vars(command, {"width": "16"}) == "make W=16 OUT=$HOME/build"

    def test_replace_command_vars_without_substitutions_is_a_noop(self):
        assert vpd.replace_command_vars("make W=${width}", {}) == "make W=${width}"

    def test_sanitize_value_keeps_directory_safe_characters(self):
        assert vpd.sanitize_value("1.5-a_b") == "1.5-a_b"
        assert vpd.sanitize_value("a b/c") == "a_b_c"
        assert vpd.sanitize_value("") == "_"

    def test_virtual_domain_names_come_from_the_variables(self):
        settings = {"generate_configurations_settings": {"variables": {"width": {}, "seed": {}}}}
        assert vpd.get_virtual_domain_names(settings) == {"width", "seed"}

    def test_no_virtual_domain_names_without_variables(self):
        assert vpd.get_virtual_domain_names({}) == set()
        assert vpd.get_virtual_domain_names(None) == set()

    def test_split_requested_param_domains(self):
        physical, virtual = vpd.split_requested_param_domains(["corner/tt", "width/16"], {"width"})
        assert physical == ["corner/tt"]
        assert virtual == ["width/16"]

    def test_variants_are_not_generated_when_configurations_are_generated(self):
        settings = {
            "generate_configurations": True,
            "generate_configurations_settings": {"variables": {"width": {"type": "list", "settings": {"list": ["8"]}}}},
        }
        assert vpd.build_variants(settings, "settings.yml") == []

    def test_variants_cover_every_combination(self):
        settings = {
            "generate_configurations": False,
            "generate_configurations_settings": {
                "variables": {
                    "width": {"type": "list", "settings": {"list": ["8", "16"]}},
                    "seed": {"type": "list", "settings": {"list": ["a", "b"]}},
                }
            },
        }
        variants = vpd.build_variants(settings, "settings.yml")
        combinations = sorted((v["substitutions"]["width"], v["substitutions"]["seed"]) for v in variants)
        assert combinations == [("16", "a"), ("16", "b"), ("8", "a"), ("8", "b")]
        assert sorted(variants[0]["requested_param_domains"])[0].startswith("seed/")

    def test_filter_variants_keeps_matching_values_and_wildcards(self):
        variants = [
            {"requested_param_domains": ["width/8"], "substitutions": {"width": "8"}},
            {"requested_param_domains": ["width/16"], "substitutions": {"width": "16"}},
        ]
        assert len(vpd.filter_variants(variants, ["width/*"])) == 2
        assert vpd.filter_variants(variants, ["width/16"])[0]["substitutions"] == {"width": "16"}
        assert vpd.filter_variants(variants, ["width/32"]) == []


######################################
# Architecture integration
######################################

SETTINGS_WITH_VARIABLES = """\
generate_rtl: true
design_path: design
generate_command: {command}
generate_output: rtl
top_level_file: top.v
top_level_module: top
clock_signal: clk
reset_signal: rst
use_parameters: false
generate_configurations: false
generate_configurations_settings:
  variables:
    width:
      type: list
      settings:
        list: ["8", "16"]
"""


def write_architecture(arch_path, name, command):
    arch_dir = os.path.join(arch_path, name)
    os.makedirs(arch_dir, exist_ok=True)
    with open(os.path.join(arch_dir, hard_settings.param_settings_filename), "w") as f:
        f.write(SETTINGS_WITH_VARIABLES.format(command=command))
    return arch_dir


def write_param_domain(arch_dir, domain, value, content):
    domain_dir = os.path.join(arch_dir, domain)
    os.makedirs(domain_dir, exist_ok=True)
    with open(os.path.join(domain_dir, hard_settings.param_settings_filename), "w") as f:
        yaml.safe_dump({"use_parameters": False}, f)
    with open(os.path.join(domain_dir, value + ".txt"), "w") as f:
        f.write(content)


@pytest.fixture
def arch_handler(tmp_path):
    arch_path = str(tmp_path / "architectures")
    os.makedirs(arch_path, exist_ok=True)
    handler = ArchitectureHandler(
        work_path=str(tmp_path / "work"),
        arch_path=arch_path,
        script_path=OdatixSettings.odatix_eda_tools_path,
        log_path=hard_settings.work_log_path,
        work_rtl_path=hard_settings.work_rtl_path,
        work_script_path=hard_settings.work_script_path,
        work_log_path=hard_settings.work_log_path,
        work_report_path=hard_settings.work_report_path,
        process_group=False,
        command="",
        eda_target_filename=str(tmp_path / "target.yml"),
        fmax_status_filename=hard_settings.fmax_status_filename,
        frequency_search_filename=hard_settings.frequency_search_filename,
        param_settings_filename=hard_settings.param_settings_filename,
        valid_status=hard_settings.valid_status,
        valid_frequency_search=hard_settings.valid_frequency_search,
        forced_fmax_lower_bound=None,
        forced_fmax_upper_bound=None,
        forced_custom_freq_list=None,
        overwrite=False,
    )
    return handler


class TestArchitectureExpansion:
    def test_a_command_using_a_variable_expands_into_one_request_per_value(self, arch_handler):
        write_architecture(arch_handler.arch_path, "gen", "make WIDTH=${width}")

        expanded = arch_handler.expand_virtual_param_domains(["gen"])

        assert [request for request, _ in expanded] == ["gen+width/8", "gen+width/16"]
        assert [subs["width"] for _, subs in expanded] == ["8", "16"]

    def test_a_command_ignoring_the_variables_keeps_a_single_request(self, arch_handler):
        write_architecture(arch_handler.arch_path, "gen", "make")

        assert arch_handler.expand_virtual_param_domains(["gen"]) == [("gen", {})]

    def test_an_explicit_value_selects_a_single_variant(self, arch_handler):
        write_architecture(arch_handler.arch_path, "gen", "make WIDTH=${width}")

        expanded = arch_handler.expand_virtual_param_domains(["gen+width/16"])

        assert expanded == [("gen+width/16", {"width": "16"})]

    def test_an_unknown_value_is_reported_as_an_error(self, arch_handler):
        write_architecture(arch_handler.arch_path, "gen", "make WIDTH=${width}")

        assert arch_handler.expand_virtual_param_domains(["gen+width/32"]) == []

    def test_a_wildcard_on_a_virtual_domain_is_dropped_before_wildcard_expansion(self, arch_handler):
        write_architecture(arch_handler.arch_path, "gen", "make WIDTH=${width}")

        normalized = vpd.normalize_requests_for_wildcards(
            requests=["gen+width/*"],
            base_path=arch_handler.arch_path,
            get_basic=ArchitectureHandler.get_basic,
        )

        assert normalized == ["gen"]

    def test_a_physical_domain_selector_is_kept_alongside_the_variants(self, arch_handler):
        arch_dir = write_architecture(arch_handler.arch_path, "gen", "make WIDTH=${width}")
        write_param_domain(arch_dir, "corner", "tt", "TT")

        expanded = arch_handler.expand_virtual_param_domains(["gen+corner/tt"])

        assert [request for request, _ in expanded] == ["gen+corner/tt+width/8", "gen+corner/tt+width/16"]

    def test_an_architecture_without_variables_is_untouched(self, arch_handler):
        arch_dir = os.path.join(arch_handler.arch_path, "plain")
        os.makedirs(arch_dir)
        with open(os.path.join(arch_dir, hard_settings.param_settings_filename), "w") as f:
            yaml.safe_dump({"rtl_path": "rtl", "top_level_file": "top.v"}, f)

        assert arch_handler.expand_virtual_param_domains(["plain"]) == [("plain", {})]


class TestGenerateCommandResolution:
    def test_variable_values_are_substituted_in_the_generation_command(self, arch_handler):
        write_architecture(arch_handler.arch_path, "gen", "make WIDTH=${width}")

        instance = arch_handler.get_architecture("gen+width/16", command_substitutions={"width": "16"})

        assert instance is not None
        assert instance.generate_command == "make WIDTH=16"

    def test_parameter_domain_values_are_substituted_in_the_generation_command(self, arch_handler):
        arch_dir = write_architecture(arch_handler.arch_path, "gen", "make CORNER=${corner}")
        write_param_domain(arch_dir, "corner", "tt", "typical")

        instance = arch_handler.get_architecture("gen+corner/tt")

        assert instance is not None
        assert instance.generate_command == "make CORNER=typical"

    def test_unknown_names_are_left_untouched(self, arch_handler):
        write_architecture(arch_handler.arch_path, "gen", "make OUT=$HOME/build W=${width}")

        instance = arch_handler.get_architecture("gen+width/8", command_substitutions={"width": "8"})

        assert instance is not None
        assert instance.generate_command == "make OUT=$HOME/build W=8"


######################################
# GUI: highlighted command fields
######################################

@pytest.mark.gui
class TestCommandFieldHighlighting:
    """
    The generation command input and the workflow command textareas are colored
    by assets/variable_highlight.js, which picks its fields by the shared
    "odatix-command-field" class and reads the names to color from the window
    globals fed by each page's clientside callback.
    """

    HIGHLIGHT_CLASS = "odatix-command-field"

    @pytest.fixture
    def editors(self):
        dash = pytest.importorskip("dash")
        dash.Dash(__name__, use_pages=True, pages_folder="")
        import odatix.gui.pages.architecture_editor as architecture_editor
        import odatix.gui.pages.workflow_editor as workflow_editor

        return architecture_editor, workflow_editor

    def find_by_id(self, component, component_id):
        if getattr(component, "id", None) == component_id:
            return component
        for child in self.children_of(component):
            found = self.find_by_id(child, component_id)
            if found is not None:
                return found
        return None

    @staticmethod
    def children_of(component):
        children = getattr(component, "children", None)
        if children is None:
            return []
        if isinstance(children, (list, tuple)):
            return children
        return [children]

    def test_generation_command_input_is_highlighted(self, editors):
        architecture_editor, _ = editors

        form = architecture_editor.architecture_form({"generate_rtl": True})
        command_input = self.find_by_id(form, "generate_command")

        assert command_input is not None
        assert self.HIGHLIGHT_CLASS in (command_input.className or "")

    def test_workflow_command_textarea_is_highlighted(self, editors):
        _, workflow_editor = editors

        card = workflow_editor.wf_task_card(name="main")
        textarea = self.find_by_id(card, {"type": "wf-task-field-commands", "name": "main"})

        assert textarea is not None
        assert self.HIGHLIGHT_CLASS in (textarea.className or "")

    def test_highlighted_names_are_the_domains_and_the_variables(self, editors, tmp_path, monkeypatch):
        architecture_editor, _ = editors

        arch_path = str(tmp_path / "architectures")
        arch_dir = write_architecture(arch_path, "gen", "make WIDTH=${width}")
        write_param_domain(arch_dir, "corner", "tt", "typical")

        domains, variables = architecture_editor.update_arch_highlight_names(
            search="?arch=gen",
            page=architecture_editor.page_path,
            odatix_settings={"arch_path": arch_path},
        )

        assert domains == ["corner"]
        assert variables == ["width"]

    def test_variables_generating_configurations_are_not_command_names(self, editors, tmp_path):
        architecture_editor, _ = editors

        arch_path = str(tmp_path / "architectures")
        arch_dir = write_architecture(arch_path, "gen", "make WIDTH=${width}")
        settings_file = os.path.join(arch_dir, hard_settings.param_settings_filename)
        with open(settings_file) as f:
            settings = yaml.safe_load(f)
        settings["generate_configurations"] = True
        settings["generate_configurations_settings"]["name"] = "cfg_${width}"
        settings["generate_configurations_settings"]["template"] = "parameter W = ${width};"
        with open(settings_file, "w") as f:
            yaml.safe_dump(settings, f)

        _domains, variables = architecture_editor.update_arch_highlight_names(
            search="?arch=gen",
            page=architecture_editor.page_path,
            odatix_settings={"arch_path": arch_path},
        )

        assert variables == []

    def test_no_names_for_an_unsaved_architecture(self, editors):
        architecture_editor, _ = editors

        assert architecture_editor.update_arch_highlight_names(
            search="", page=architecture_editor.page_path, odatix_settings={}
        ) == ([], [])
