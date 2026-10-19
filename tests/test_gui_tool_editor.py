"""
The tool editor (/tool_editor): flow parameters and tools extending another one.

What the page shows has to come back the way it was read, so the tests render
the flows, read them back the way Dash hands them to the callbacks (one list per
id type, in layout order), and compare.
"""

import json
import os
import textwrap

import dash
import pytest

from odatix.workspace import Workspace
from odatix.workspace.tools import ToolSettings
from odatix.workspace.yaml_io import read_yaml


@pytest.fixture(scope="module")
def te():
    # dash.register_page (called at page-module import) requires an app
    dash.Dash(__name__, use_pages=True, pages_folder="")
    import odatix.gui.pages.tool_editor as tool_editor

    return tool_editor


@pytest.fixture
def workspace(tmp_path):
    return Workspace.from_dict({"tools_path": "tools"}, root=str(tmp_path))


def write_tool(workspace, name, content):
    path = workspace.tools.entry(name).path
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, "tool.yml"), "w", encoding="utf-8") as handle:
        handle.write(textwrap.dedent(content))
    return path


STANDALONE = """\
    label: Mine
    custom_key: {kept: 1}
    default_flow: base
    parameters:
      shell: my_shell
      effort: 3
      retime: false
      options: [-a, -b]
    unix:
      custom_freq_synthesis_command: [$shell, -f, run.tcl]
    flows:
      fast:
        metrics_file: $tool_path/fast.yml
        parameters:
          effort: 0
      scripted:
        unix:
          custom_freq_synthesis_command: [other, -f, mine.tcl]
    """

BASE = """\
    default_flow: plain
    parameters:
      shell: base_shell
      compile: compile
    unix:
      tool_test_command: [$shell, -version]
      custom_freq_synthesis_command: [$shell, -f, run.tcl]
    flows:
      ultra:
        parameters:
          compile: compile_ultra
    """

DERIVED = """\
    extends: base
    label: Derived
    parameters:
      shell: derived_shell
    flows:
      retime:
        parameters:
          compile_options: [-retime]
    """


def _walk(node):
    yield node
    children = getattr(node, "children", None)
    if children is None:
        return
    if not isinstance(children, (list, tuple)):
        children = [children]
    for child in children:
        if child is not None and not isinstance(child, (str, int, float)):
            yield from _walk(child)


def page_fields(te, cards):
    """The values of the flow fields as the callbacks receive them."""
    by_type = {}
    for card in cards:
        for node in _walk(card):
            node_id = getattr(node, "id", None)
            if isinstance(node_id, dict):
                by_type.setdefault(node_id["type"], []).append(node)
    return {
        name: [node.id if prop == "id" else getattr(node, prop, None) for node in by_type.get(id_type, [])]
        for name, id_type, _pattern, prop, _kind in te.FLOW_FIELDS
    }


def through_the_page(te, settings, base_parameters=None):
    """The flows of `settings`, rendered then read back."""
    settings = json.loads(json.dumps(settings))
    cards = te.flow_cards(settings["flows"], base_parameters=base_parameters)
    return te.gather_flows(page_fields(te, cards))


class TestParameterValues:
    def test_a_number_typed_as_text_stays_a_number(self, te):
        assert te._scalar("3") == 3
        assert te._scalar("-2") == -2
        assert te._scalar("0.5") == 0.5
        # Only what a tool.yml would have read as a number.
        assert te._scalar("007") == "007"
        assert te._scalar("1e3") == "1e3"
        assert te._scalar("compile") == "compile"
        assert te._scalar("") == ""

    @pytest.mark.parametrize("value", ["compile_ultra", "", 0, 2.5, True, False, [], ["-a", "-b"], [1, "x"]])
    def test_a_value_survives_its_row(self, te, value):
        assert te.param_value(te.param_row("p", value)) == value

    def test_display(self, te):
        assert te.param_display(True) == ("on", False)
        assert te.param_display(["-a", "-b"]) == ("-a -b", False)
        assert te.param_display([]) == ("empty list", True)
        assert te.param_display("") == ("empty", True)

    def test_retyping_starts_from_what_was_typed(self, te):
        row = te.param_row("p", "-a -b")
        assert te.param_value(te._retype_param(row, "list")) == ["-a", "-b"]
        row = te.param_row("p", ["-a", "-b"])
        assert te.param_value(te._retype_param(row, "text")) == "-a -b"
        assert te.param_value(te._retype_param(te.param_row("p", "yes"), "bool")) is True

    def test_invalid_and_duplicate_names_are_reported(self, te):
        flows = [{"name": "f", "parameters": [te.param_row("1bad", "x")]}]
        assert "1bad" in te.flow_errors(flows)
        flows = [{"name": "f", "parameters": [te.param_row("a", "x"), te.param_row("a", "y")]}]
        assert "twice" in te.flow_errors(flows)
        assert te.flow_errors([{"name": "f", "parameters": [te.param_row("ok_1", "x")]}]) is None


class TestStandaloneTool:
    def test_saving_loses_nothing(self, te, workspace):
        """What the page has no field for (other keys, a flow's metrics file)
        is written back with the parameters."""
        write_tool(workspace, "mine", STANDALONE)
        settings, _builtin, overlay, base = te.load_editor_settings(workspace.tools, "mine")
        assert not overlay and base == {}

        tool = workspace.tools["mine"]
        tool.settings = te.tool_document(settings)
        tool.save(as_overlay=False)

        saved = read_yaml(tool.settings_path)
        assert saved["parameters"] == {"shell": "my_shell", "effort": 3, "retime": False, "options": ["-a", "-b"]}
        assert saved["flows"]["fast"] == {"metrics_file": "$tool_path/fast.yml", "parameters": {"effort": 0}}
        assert saved["flows"]["scripted"]["unix"]["custom_freq_synthesis_command"] == ["other", "-f", "mine.tcl"]
        assert saved["custom_key"] == {"kept": 1}
        assert saved["default_flow"] == "base"

    def test_the_page_reads_back_what_it_shows(self, te, workspace):
        write_tool(workspace, "mine", STANDALONE)
        settings, _builtin, _overlay, base = te.load_editor_settings(workspace.tools, "mine")
        flows = through_the_page(te, settings, base)
        assert te._flows_for_compare(flows) == te._flows_for_compare(settings["flows"])

    def test_a_flow_lists_what_it_inherits(self, te, workspace):
        write_tool(workspace, "mine", STANDALONE)
        settings, _builtin, _overlay, base = te.load_editor_settings(workspace.tools, "mine")
        cards = te.flow_cards(settings["flows"], base_parameters=base)
        fast = cards[1]
        texts = [node.children for node in _walk(fast) if "odx-param-inherited-value" in (getattr(node, "className", "") or "")]
        # Everything but "effort", which it sets.
        assert texts == ["my_shell", "off", "-a -b"]

    def test_a_copy_keeps_the_parameters(self, te, workspace):
        write_tool(workspace, "mine", STANDALONE)
        settings, *_ = te.load_editor_settings(workspace.tools, "mine")
        fast = settings["flows"][1]
        copy = te._flow_copy(fast, {"base", "fast", "scripted"})
        assert copy["name"] == "fast_copy"
        assert te.params_from_rows(copy["parameters"]) == {"effort": 0}
        assert copy["keep"]["metrics_file"] == "$tool_path/fast.yml"


class TestDerivedTool:
    def test_it_shows_the_flows_it_runs(self, te, workspace):
        write_tool(workspace, "base", BASE)
        write_tool(workspace, "derived", DERIVED)
        settings, _builtin, overlay, base = te.load_editor_settings(workspace.tools, "derived")
        assert not overlay
        assert settings["extends"] == "base"
        assert [(flow["name"], flow["origin"]) for flow in settings["flows"]] == [
            ("plain", te.ORIGIN_BASE), ("ultra", te.ORIGIN_BASE), ("retime", te.ORIGIN_OWN),
        ]
        # The default flow is the base tool's; it holds what the tool changes.
        assert settings["flows"][0]["is_default"]
        assert te.params_from_rows(settings["flows"][0]["parameters"]) == {"shell": "derived_shell"}
        assert base == {"shell": "base_shell", "compile": "compile"}

    def test_saving_writes_only_what_it_changes(self, te, workspace):
        write_tool(workspace, "base", BASE)
        write_tool(workspace, "derived", DERIVED)
        settings, *_ = te.load_editor_settings(workspace.tools, "derived")
        tool = workspace.tools["derived"]
        tool.settings = te.tool_document(settings)
        tool.save(as_overlay=False)

        saved = read_yaml(tool.settings_path)
        assert saved["extends"] == "base"
        assert saved["parameters"] == {"shell": "derived_shell"}
        # Nothing of the base tool's flows, nor of its commands.
        assert list(saved["flows"]) == ["retime"]
        assert "unix" not in saved

    def test_the_page_reads_back_what_it_shows(self, te, workspace):
        write_tool(workspace, "base", BASE)
        write_tool(workspace, "derived", DERIVED)
        settings, _builtin, _overlay, base = te.load_editor_settings(workspace.tools, "derived")
        flows = through_the_page(te, settings, base)
        assert te._flows_for_compare(flows) == te._flows_for_compare(settings["flows"])
        assert [flow["origin"] for flow in flows] == [te.ORIGIN_BASE, te.ORIGIN_BASE, te.ORIGIN_OWN]

    def test_a_hand_written_change_to_a_base_flow_is_kept(self, te, workspace):
        write_tool(workspace, "base", BASE)
        write_tool(workspace, "derived", DERIVED.rstrip(" ") + "      ultra:\n        parameters:\n          compile: compile_x\n")
        settings, *_ = te.load_editor_settings(workspace.tools, "derived")
        ultra = settings["flows"][1]
        assert te.params_from_rows(ultra["parameters"]) == {"compile": "compile_x"}
        saved = te.tool_document(settings)
        assert [flow["name"] for flow in saved["flows"]] == ["plain", "ultra", "retime"]
        assert saved["flows"][1]["parameters"] == {"compile": "compile_x"}

    def test_another_base_tool(self, te, workspace):
        write_tool(workspace, "base", BASE)
        write_tool(workspace, "derived", DERIVED)
        settings, *_ = te.load_editor_settings(workspace.tools, "derived")

        standalone = te.rebase_flows(settings["flows"], [])
        assert [flow["name"] for flow in standalone] == ["plain", "retime"]
        assert standalone[0]["is_default"] and standalone[0]["origin"] == te.ORIGIN_OWN
        # What the default flow changed follows it.
        assert te.params_from_rows(standalone[0]["parameters"]) == {"shell": "derived_shell"}

        base_flows, _parameters = te.base_tool_context(workspace.tools, "base", "derived")
        rebased = te.rebase_flows(standalone, base_flows)
        assert [flow["name"] for flow in rebased] == ["plain", "ultra", "retime"]
        assert te.params_from_rows(rebased[0]["parameters"]) == {"shell": "derived_shell"}

    def test_a_tool_cannot_extend_one_extending_it(self, te, workspace):
        write_tool(workspace, "base", BASE)
        write_tool(workspace, "derived", DERIVED)
        names = [option["value"] for option in te.extends_options(workspace.tools, "base")]
        assert "derived" not in names and "base" not in names
        assert "base" in [option["value"] for option in te.extends_options(workspace.tools, "derived")]


class TestBuiltinTools:
    @pytest.mark.parametrize("name", ["design_compiler", "dc_nxt", "vivado"])
    def test_the_page_reads_back_what_it_shows(self, te, workspace, name):
        settings, _builtin, overlay, base = te.load_editor_settings(workspace.tools, name)
        assert overlay
        assert all(flow["origin"] == te.ORIGIN_BUILTIN for flow in settings["flows"])
        flows = through_the_page(te, settings, base)
        assert te._flows_for_compare(flows) == te._flows_for_compare(settings["flows"])

    def test_dc_nxt_shows_the_flows_of_design_compiler(self, te, workspace):
        settings, *_ = te.load_editor_settings(workspace.tools, "dc_nxt")
        names = [flow["name"] for flow in settings["flows"]]
        assert names[:3] == ["standard", "high_effort", "ultra"]
        assert te.params_from_rows(settings["flows"][0]["parameters"])["shell"] == "dcnxt_shell"

    def test_a_copy_of_a_strategy_is_saved_with_its_parameters(self, te, workspace):
        settings, *_ = te.load_editor_settings(workspace.tools, "design_compiler")
        ultra = next(flow for flow in settings["flows"] if flow["name"] == "ultra")
        copy = te._flow_copy(ultra, {flow["name"] for flow in settings["flows"]})
        assert copy["origin"] == te.ORIGIN_OWN and not copy["builtin"]

        workspace.tools["design_compiler"].save_overlay({}, te.flows_to_save([copy]))
        saved = read_yaml(workspace.tools["design_compiler"].settings_path)
        assert saved["flows"]["ultra_copy"]["parameters"] == {"compile": "compile_ultra"}
        assert saved["flows"]["ultra_copy"]["label"].endswith("(copy)")


class TestToolSettingsExtends:
    def test_extends_is_written_first(self):
        document = ToolSettings.from_dict({"extends": "base", "label": "X"}).to_document()
        assert list(document)[0] == "extends"

    def test_an_empty_default_flow_entry_is_not_written(self):
        document = ToolSettings.from_dict({"default_flow": "plain", "parameters": {"a": 1}}).to_document()
        assert "flows" not in document
        assert document["parameters"] == {"a": 1}
