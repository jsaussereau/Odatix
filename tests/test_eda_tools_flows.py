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
Discovery and resolution of eda tool flows (odatix.lib.eda_tools).

A flow is a way of running a tool: a different script, different options,
sometimes a different binary (Vivado timing oriented vs power oriented with clock
gating, Design Compiler in wire load vs topographical mode). Flows of the same
tool are alternatives meant to be compared, so each gets its own work directory.

These tests cover the built-in declarations, the job type filtering, the work
directory naming, and the merge that lets a user tool.yml add a flow to a
built-in tool without copying its whole definition.
"""

import os
import textwrap

import pytest

import odatix.lib.eda_tools as eda_tools
from odatix.lib.settings import OdatixSettings


@pytest.fixture
def user_tools_dir(tmp_path, monkeypatch):
    """An empty workspace tools directory, used as the user tools search path."""
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    monkeypatch.setattr(OdatixSettings, "user_tools_path", str(tools_dir))
    # Flows are resolved for the current platform: keep the tests on the "unix"
    # section whatever the platform running them.
    monkeypatch.setattr(eda_tools, "platform_key", lambda *args, **kwargs: "unix")
    return tools_dir


def write_tool(tools_dir, name, content):
    tool_dir = tools_dir / name
    tool_dir.mkdir(parents=True, exist_ok=True)
    (tool_dir / "tool.yml").write_text(textwrap.dedent(content), encoding="utf-8")
    return tool_dir


VIVADO_FLOWS = ["standard", "runtime", "performance", "area", "power_opt"]
DC_FLOWS = ["standard", "high_effort", "ultra", "ultra_timing", "ultra_area", "ultra_power"]
INNOVUS_FLOWS = ["standard", "express", "extreme", "timing", "area", "power"]
LIBRELANE_FLOWS = ["standard", "area", "timing", "timing_extreme"]
QUARTUS_FLOWS = ["standard", "balanced", "runtime", "performance", "area", "power_opt"]


class TestBuiltinFlows:
    def test_vivado_declares_its_flows(self, user_tools_dir):
        flows = eda_tools.list_flows("vivado")
        assert list(flows) == VIVADO_FLOWS
        assert flows["standard"]["is_default"]
        assert flows["power_opt"]["label"] == "Power optimized"

    def test_default_flow_comes_first(self, user_tools_dir):
        assert eda_tools.get_default_flow("vivado") == "standard"

    def test_flows_are_filtered_by_job_type(self, user_tools_dir):
        assert eda_tools.get_flow_names("vivado", "fmax_synthesis") == VIVADO_FLOWS
        # A flow inherits what it does not redefine, so it runs every job type
        # the tool does — here RTL analysis, which power_opt has nothing to say
        # about.
        assert eda_tools.flow_supports("vivado", "power_opt", "analysis")
        assert eda_tools.get_flow_command("vivado", "power_opt", "analysis") == eda_tools.get_flow_command(
            "vivado", "standard", "analysis"
        )
        # A job type the tool itself cannot run is not invented for any flow.
        assert not eda_tools.flow_supports("verilator", "lint", "fmax_synthesis")

    def test_design_compiler_declares_its_strategies(self, user_tools_dir):
        assert eda_tools.get_flow_names("design_compiler", "fmax_synthesis") == DC_FLOWS
        assert eda_tools.get_default_flow("design_compiler") == "standard"
        # Every strategy runs the same steps with the same binary: only how the
        # design is compiled changes.
        standard = eda_tools.get_flow_steps("design_compiler", "standard", "custom_freq_synthesis")
        for flow in DC_FLOWS:
            assert eda_tools.get_flow_steps("design_compiler", flow, "custom_freq_synthesis") == standard, flow
        assert eda_tools.get_flow_parameters("design_compiler")["compile"] == "compile"
        assert eda_tools.get_flow_parameters("design_compiler", "ultra_timing")["compile"] == "compile_ultra"

    def test_innovus_declares_its_strategies(self, user_tools_dir):
        assert eda_tools.get_flow_names("innovus", "pnr") == INNOVUS_FLOWS
        assert eda_tools.get_default_flow("innovus") == "standard"
        standard = eda_tools.get_flow_steps("innovus", "standard", "pnr")
        for flow in INNOVUS_FLOWS:
            assert eda_tools.get_flow_steps("innovus", flow, "pnr") == standard, flow
        assert eda_tools.get_flow_parameters("innovus")["utilization"] == 0.7
        timing = eda_tools.get_flow_parameters("innovus", "timing")
        assert timing["fix_hold"] is True
        # Innovus takes its boolean options as words: a bare YAML true would
        # reach the Tcl scripts as 1.
        assert "true" in timing["route_options"]

    def test_librelane_declares_its_strategies(self, user_tools_dir):
        for job_type in ("fmax_synthesis", "custom_freq_synthesis", "analysis"):
            assert eda_tools.get_flow_names("librelane", job_type) == LIBRELANE_FLOWS, job_type
        assert eda_tools.get_default_flow("librelane") == "standard"
        standard = eda_tools.get_flow_steps("librelane", "standard", "custom_freq_synthesis")
        assert [step["name"] for step in standard] == ["synthesis", "floorplan", "place", "cts", "route", "signoff"]
        for flow in LIBRELANE_FLOWS:
            assert eda_tools.get_flow_steps("librelane", flow, "custom_freq_synthesis") == standard, flow
        # The default flow leaves every LibreLane variable to LibreLane: an empty
        # parameter is not given on the command line.
        assert eda_tools.get_flow_parameters("librelane")["SYNTH_STRATEGY"] == ""
        assert eda_tools.get_flow_parameters("librelane", "timing")["SYNTH_STRATEGY"] == "DELAY 1"
        assert eda_tools.get_flow_parameters("librelane", "timing")["RUN_POST_GRT_RESIZER_TIMING"] is True

    def test_librelane_fmax_steps_search_at_their_own_depth(self, user_tools_dir):
        steps = {
            step["name"]: " ".join(step["command"])
            for step in eda_tools.get_flow_steps("librelane", "standard", "fmax_synthesis")
        }
        assert "step_fmax_synthesis.tcl" in steps["synthesis"]
        assert "step_fmax_pnr.tcl" in steps["pnr"]
        assert eda_tools.get_default_step("librelane", "standard", "fmax_synthesis") == "synthesis"
        assert eda_tools.get_default_step("librelane", "standard", "custom_freq_synthesis") == "route"

    def test_quartus_declares_its_strategies(self, user_tools_dir):
        for job_type in ("fmax_synthesis", "custom_freq_synthesis", "analysis"):
            assert eda_tools.get_flow_names("quartus", job_type) == QUARTUS_FLOWS, job_type
        assert eda_tools.get_default_flow("quartus") == "standard"
        standard = eda_tools.get_flow_steps("quartus", "standard", "custom_freq_synthesis")
        assert [step["name"] for step in standard] == ["elaboration", "synthesis", "pnr", "bitstream"]
        for flow in QUARTUS_FLOWS:
            assert eda_tools.get_flow_steps("quartus", flow, "custom_freq_synthesis") == standard, flow
        assert eda_tools.get_flow_parameters("quartus")["optimization_mode"] == "HIGH PERFORMANCE EFFORT"
        assert eda_tools.get_flow_parameters("quartus")["virtual_pins"] is True
        area = eda_tools.get_flow_parameters("quartus", "area")
        assert area["optimization_mode"] == "AGGRESSIVE AREA"
        assert area["allow_register_retiming"] is False
        # What a flow does not set is the default flow's
        assert area["power_analysis"] is True

    def test_quartus_fmax_steps_search_at_their_own_depth(self, user_tools_dir):
        steps = {
            step["name"]: " ".join(step["command"])
            for step in eda_tools.get_flow_steps("quartus", "standard", "fmax_synthesis")
        }
        assert "step_fmax_synthesis.tcl" in steps["synthesis"]
        assert "step_fmax_pnr.tcl" in steps["pnr"]
        assert "step_fmax_bitstream.tcl" in steps["bitstream"]
        assert eda_tools.get_default_step("quartus", "standard", "fmax_synthesis") == "pnr"
        assert eda_tools.get_default_step("quartus", "standard", "custom_freq_synthesis") == "pnr"

    def test_dc_nxt_is_design_compiler_with_another_binary(self, user_tools_dir):
        assert eda_tools.tool_lineage("dc_nxt") == ["design_compiler", "dc_nxt"]
        assert eda_tools.get_flow_names("dc_nxt", "fmax_synthesis") == DC_FLOWS
        for tool, binary in (("design_compiler", "dc_shell"), ("dc_nxt", "dcnxt_shell")):
            flows = eda_tools.list_flows(tool)
            for flow in flows.values():
                assert flow["tool_test_command"][0] == binary, (tool, flow["name"])
                for step in eda_tools.resolve_steps(flow, "custom_freq_synthesis"):
                    assert binary in step["command"], (tool, flow["name"], step["name"])
        # Same technologies, and the scripts of the tool it extends.
        assert eda_tools.get_target_filename("dc_nxt") == "target_design_compiler.yml"
        assert eda_tools.get_tool_dirs("dc_nxt")[0] == eda_tools.get_tool_dir("design_compiler")
        # A tool of its own all the same: its own work directory.
        assert eda_tools.tool_work_dirname("dc_nxt", "ultra") == "dc_nxt@ultra"

    def test_tool_test_command_is_inherited_by_default(self, user_tools_dir):
        # Unlike the job commands, a flow that does not override it keeps the
        # tool's own installation check.
        flows = eda_tools.list_flows("vivado")
        assert flows["power_opt"]["tool_test_command"] == flows["standard"]["tool_test_command"]

    def test_a_tool_without_flows_section_gets_one_default_flow(self, user_tools_dir):
        write_tool(
            user_tools_dir,
            "legacy",
            """\
            default_metrics_file: metrics.yml
            unix:
              tool_test_command: true
              fmax_synthesis_command: run_fmax
            """,
        )
        flows = eda_tools.list_flows("legacy")
        assert list(flows) == [eda_tools.DEFAULT_FLOW_NAME]
        assert flows[eda_tools.DEFAULT_FLOW_NAME]["is_default"]
        assert eda_tools.get_flow_command("legacy", job_type="fmax_synthesis") == "run_fmax"

    def test_tool_supports_reports_any_flow(self, user_tools_dir):
        assert eda_tools.tool_supports("vivado", "custom_freq_synthesis")
        assert not eda_tools.tool_supports("verilator", "fmax_synthesis")
        assert "vivado" in eda_tools.tools_supporting("analysis")


class TestUserFlows:
    def test_user_tool_yml_adds_a_flow_to_a_builtin_tool(self, user_tools_dir):
        write_tool(
            user_tools_dir,
            "vivado",
            """\
            flows:
              gate_level_sim:
                label: "Gate level simulation"
                unix:
                  custom_freq_synthesis_command: my_custom_command
            """,
        )
        flows = eda_tools.list_flows("vivado")
        # The built-in flows are kept, the user one is added.
        assert set(flows) == set(VIVADO_FLOWS) | {"gate_level_sim"}
        assert flows["gate_level_sim"]["label"] == "Gate level simulation"
        assert eda_tools.get_flow_command("vivado", "gate_level_sim", "custom_freq_synthesis") == "my_custom_command"
        # ...and the rest of the built-in definition still resolves.
        assert eda_tools.get_tool_label("vivado") == "Vivado"
        assert eda_tools.get_default_flow("vivado") == "standard"
        # The added flow gets its own work directory.
        assert eda_tools.tool_work_dirname("vivado", "gate_level_sim") == "vivado@gate_level_sim"

    def test_user_tool_yml_cannot_override_a_builtin_flow(self, user_tools_dir):
        builtin_label = eda_tools.list_flows("vivado")["power_opt"]["label"]
        builtin_command = eda_tools.get_flow_command("vivado", "power_opt", "fmax_synthesis")
        write_tool(
            user_tools_dir,
            "vivado",
            """\
            flows:
              power_opt:
                label: "My power flow"
                unix:
                  fmax_synthesis_command: my_fmax
            """,
        )
        # The built-in flows belong to Odatix: the workspace is ignored there,
        # rather than making odatix run something else than what it reports.
        flows = eda_tools.list_flows("vivado")
        assert flows["power_opt"]["label"] == builtin_label
        assert eda_tools.get_flow_command("vivado", "power_opt", "fmax_synthesis") == builtin_command

    def test_user_tool_yml_cannot_override_the_builtin_default_flow(self, user_tools_dir):
        builtin_command = eda_tools.get_flow_command("vivado", "standard", "custom_freq_synthesis")
        write_tool(
            user_tools_dir,
            "vivado",
            """\
            default_flow: mine
            unix:
              custom_freq_synthesis_command: my_command
            """,
        )
        assert eda_tools.get_default_flow("vivado") == "standard"
        assert eda_tools.get_flow_command("vivado", "standard", "custom_freq_synthesis") == builtin_command

    def test_a_rejected_override_keeps_what_it_may_change(self, user_tools_dir):
        write_tool(
            user_tools_dir,
            "vivado",
            """\
            label: "My Vivado"
            unix:
              custom_freq_synthesis_command: my_command
            flows:
              power_opt:
                label: "My power flow"
              mine:
                label: "Mine"
                unix:
                  fmax_synthesis_command: my_fmax
            """,
        )
        # Only what the built-in definition owns is dropped: the rest of the
        # overlay still applies.
        assert eda_tools.get_tool_label("vivado") == "My Vivado"
        flows = eda_tools.list_flows("vivado")
        assert set(flows) == set(VIVADO_FLOWS) | {"mine"}
        assert flows["mine"]["label"] == "Mine"
        assert eda_tools.get_flow_command("vivado", "mine", "fmax_synthesis") == "my_fmax"

    def test_a_rejected_override_is_reported(self, user_tools_dir, capsys):
        eda_tools._reported_builtin_overrides.clear()
        write_tool(
            user_tools_dir,
            "vivado",
            """\
            flows:
              power_opt:
                label: "My power flow"
            """,
        )
        eda_tools.load_tool_settings("vivado")
        assert "read-only" in capsys.readouterr().out

    def test_a_user_tool_is_not_restricted(self, user_tools_dir):
        # Nothing is read-only in a tool the workspace owns.
        write_tool(
            user_tools_dir,
            "mytool",
            """\
            unix:
              tool_test_command: true
              fmax_synthesis_command: my_run
            """,
        )
        assert eda_tools.get_flow_command("mytool", None, "fmax_synthesis") == "my_run"

    def test_tool_defined_in_both_places_yields_both_directories(self, user_tools_dir):
        write_tool(user_tools_dir, "vivado", "flows: {}\n")
        dirs = eda_tools.get_tool_dirs("vivado")
        assert len(dirs) == 2
        # Built-in first (lowest precedence), user last: tcl scripts are copied
        # in that order so the user ones win.
        assert dirs[0].startswith(OdatixSettings.odatix_eda_tools_path)
        assert dirs[1] == str(user_tools_dir / "vivado")

    def test_default_flow_can_be_renamed_by_the_user(self, user_tools_dir):
        write_tool(
            user_tools_dir,
            "mytool",
            """\
            default_flow: quick
            unix:
              tool_test_command: true
              fmax_synthesis_command: quick_run
            flows:
              quick:
                label: "Quick"
              thorough:
                unix:
                  fmax_synthesis_command: thorough_run
            """,
        )
        flows = eda_tools.list_flows("mytool")
        assert list(flows) == ["quick", "thorough"]
        assert flows["quick"]["is_default"] and flows["quick"]["label"] == "Quick"
        assert eda_tools.get_flow_command("mytool", None, "fmax_synthesis") == "quick_run"
        assert eda_tools.get_flow_command("mytool", "thorough", "fmax_synthesis") == "thorough_run"


class TestReadToolSettings:
    def test_resolves_the_command_of_the_requested_flow(self, user_tools_dir):
        tool_dir = write_tool(
            user_tools_dir,
            "mytool",
            """\
            default_flow: base
            default_metrics_file: base_metrics.yml
            unix:
              tool_test_command: true
              custom_freq_synthesis_command: base_run
            flows:
              extended:
                metrics_file: extended_metrics.yml
                unix:
                  custom_freq_synthesis_command: extended_run
            """,
        )
        from odatix.lib.read_tool_settings import read_tool_settings

        settings_file = str(tool_dir / "tool.yml")

        *_, metrics_file, flow_name, steps = read_tool_settings("mytool", settings_file, synth_type="custom_freq_synthesis")
        assert flow_name == "base" and metrics_file == "base_metrics.yml" and steps is None

        _, command, _, metrics_file, flow_name, _steps = read_tool_settings(
            "mytool", settings_file, synth_type="custom_freq_synthesis", flow="extended"
        )
        assert command == "extended_run"
        assert flow_name == "extended"
        # A flow can ship its own metrics definition file.
        assert metrics_file == "extended_metrics.yml"

    def test_unknown_flow_exits(self, user_tools_dir):
        tool_dir = write_tool(
            user_tools_dir,
            "mytool",
            """\
            default_metrics_file: metrics.yml
            unix:
              tool_test_command: true
              custom_freq_synthesis_command: base_run
            """,
        )
        from odatix.lib.read_tool_settings import read_tool_settings

        with pytest.raises(SystemExit):
            read_tool_settings("mytool", str(tool_dir / "tool.yml"), synth_type="custom_freq_synthesis", flow="nope")

    def test_flow_not_supporting_the_job_type_exits(self, user_tools_dir):
        # A job type only one flow brings: the others have nothing to inherit
        # for it, so asking for one of them is an error rather than a silent run
        # of the wrong thing.
        tool_dir = write_tool(
            user_tools_dir,
            "mytool",
            """\
            default_metrics_file: metrics.yml
            unix:
              tool_test_command: true
              fmax_synthesis_command: base_run
            flows:
              with_custom_freq:
                unix:
                  custom_freq_synthesis_command: custom_freq_run
            """,
        )
        from odatix.lib.read_tool_settings import read_tool_settings

        assert eda_tools.get_flow_names("mytool", "custom_freq_synthesis") == ["with_custom_freq"]
        with pytest.raises(SystemExit):
            read_tool_settings(
                "mytool", str(tool_dir / "tool.yml"), synth_type="custom_freq_synthesis", flow="default"
            )


class TestWorkDirNaming:
    """
    Two flows of the same tool are alternatives meant to be compared, so they get
    separate work directories. The default flow keeps the bare tool name, so work
    directories produced before flows existed keep resolving.
    """

    def test_default_flow_keeps_the_bare_tool_name(self, user_tools_dir):
        assert eda_tools.tool_work_dirname("vivado") == "vivado"
        assert eda_tools.tool_work_dirname("vivado", "standard") == "vivado"
        assert eda_tools.tool_work_dirname("vivado", None) == "vivado"
        assert eda_tools.tool_work_dirname("vivado", "") == "vivado"

    def test_other_flows_get_their_own_directory(self, user_tools_dir):
        assert eda_tools.tool_work_dirname("vivado", "power_opt") == "vivado@power_opt"

    def test_round_trip(self, user_tools_dir):
        assert eda_tools.split_tool_work_dirname("vivado") == ("vivado", None)
        assert eda_tools.split_tool_work_dirname("vivado@power_opt") == ("vivado", "power_opt")
        # Tool names may contain underscores and dashes: only the separator splits.
        assert eda_tools.split_tool_work_dirname("design_compiler@topographical") == (
            "design_compiler",
            "topographical",
        )

    def test_separator_is_makefile_safe(self):
        # openlane and verilator pass the work directory into a makefile
        # (WORK_DIR=$work_path), where "#" would start a comment.
        assert eda_tools.WORK_DIR_FLOW_SEPARATOR == "@"
        assert "#" not in eda_tools.WORK_DIR_FLOW_SEPARATOR

    def test_flow_names_that_cannot_round_trip_are_rejected(self, user_tools_dir):
        assert eda_tools.check_flow_name("power_opt")
        assert not eda_tools.check_flow_name("power@opt")
        assert not eda_tools.check_flow_name("power/opt")
        assert not eda_tools.check_flow_name("")

    def test_a_flow_with_an_invalid_name_is_not_declared(self, user_tools_dir):
        write_tool(
            user_tools_dir,
            "mytool",
            """\
            unix:
              tool_test_command: true
              fmax_synthesis_command: base_run
            flows:
              "bad@name":
                unix:
                  fmax_synthesis_command: nope
            """,
        )
        assert list(eda_tools.list_flows("mytool")) == [eda_tools.DEFAULT_FLOW_NAME]


class TestMetricsFileResolution:
    """
    The metrics definition file must be resolved from the *merged* tool settings:
    a workspace tool.yml that only adds flows has no "default_metrics_file" of its
    own and must inherit the built-in one.
    """

    def test_user_tool_yml_adding_a_flow_inherits_the_builtin_metrics_file(self, user_tools_dir):
        import odatix.components.export_results as export_results

        write_tool(
            user_tools_dir,
            "vivado",
            """\
            flows:
              gate_level_sim:
                unix:
                  custom_freq_synthesis_command: my_custom_command
            """,
        )
        metrics_file = export_results.resolve_metrics_file("vivado", flow="gate_level_sim")
        assert metrics_file is not None
        assert metrics_file.endswith(os.path.join("vivado", "metrics.yml"))

    def test_a_flow_can_ship_its_own_metrics_file(self, user_tools_dir, tmp_path):
        import odatix.components.export_results as export_results

        tool_dir = write_tool(
            user_tools_dir,
            "vivado",
            """\
            flows:
              gate_level_sim:
                metrics_file: $tool_path/gate_level_metrics.yml
                unix:
                  custom_freq_synthesis_command: my_custom_command
            """,
        )
        (tool_dir / "gate_level_metrics.yml").write_text("metrics: {}\n", encoding="utf-8")

        # "$tool_path" resolves against the directory shipping the file, even
        # though the tool is also defined in the built-in directory.
        metrics_file = export_results.resolve_metrics_file("vivado", flow="gate_level_sim")
        assert metrics_file == str(tool_dir / "gate_level_metrics.yml")

        # The other flows keep the built-in metrics file.
        assert export_results.resolve_metrics_file("vivado", flow="standard").endswith(os.path.join("vivado", "metrics.yml"))


class TestFlowSteps:
    """
    Being split into steps is a property of a flow, not a flow of its own: a
    flow declares "<job_type>_steps" (an ordered list of named commands) instead
    of "<job_type>_command", and every flow of a tool can be stepped.
    """

    def test_every_vivado_flow_is_stepped(self, user_tools_dir):
        # An fmax search starts again from the RTL at every step, so it has no
        # use for a separate elaboration step.
        expected = {
            "fmax_synthesis": ["synthesis", "pnr", "bitstream"],
            "custom_freq_synthesis": ["elaboration", "synthesis", "pnr", "bitstream"],
        }
        for job_type, steps in expected.items():
            for flow in eda_tools.get_flow_names("vivado", job_type):
                assert eda_tools.get_flow_step_names("vivado", flow, job_type) == steps, (flow, job_type)

    def test_vivado_strategies_only_change_parameters(self, user_tools_dir):
        # A strategy is the same steps with other directives: the scripts read
        # them from the parameters, whatever the job type.
        for job_type in ("custom_freq_synthesis", "fmax_synthesis"):
            standard = eda_tools.get_flow_steps("vivado", "standard", job_type)
            for flow in VIVADO_FLOWS:
                assert eda_tools.get_flow_steps("vivado", flow, job_type) == standard, (flow, job_type)
        power_opt = eda_tools.get_flow_parameters("vivado", "power_opt")
        assert power_opt["power_opt"] is True
        assert "-gated_clock_conversion" in power_opt["synth_options"]
        # What a strategy does not set is the default flow's.
        assert eda_tools.get_flow_parameters("vivado", "standard")["power_opt"] is False

    def test_the_fmax_steps_search_at_their_own_depth(self, user_tools_dir):
        steps = {
            step["name"]: " ".join(step["command"])
            for step in eda_tools.get_flow_steps("vivado", "standard", "fmax_synthesis")
        }
        # Searching on post-synthesis timing and searching on post-route timing
        # are two searches, not a search and its continuation.
        assert "step_fmax_synthesis.tcl" in steps["synthesis"]
        assert "step_fmax_pnr.tcl" in steps["pnr"]
        assert "step_fmax_bitstream.tcl" in steps["bitstream"]

    def test_dummy_ships_a_stepped_flow(self, user_tools_dir, install_dummy_tool):
        install_dummy_tool(user_tools_dir)
        assert eda_tools.get_flow_step_names("dummy", "synthesis", "custom_freq_synthesis") == [
            "synthesis",
            "pnr",
            "bitstream",
        ]

    def test_a_flow_can_replace_inherited_steps_with_one_command(self, user_tools_dir, install_dummy_tool):
        install_dummy_tool(user_tools_dir)
        # dummy's "quick" flow declares a plain command where the default flow
        # is stepped: it runs in one go.
        assert eda_tools.get_flow_steps("dummy", "quick", "custom_freq_synthesis") is None
        assert eda_tools.get_flow_command("dummy", "quick", "custom_freq_synthesis")

    def test_a_one_shot_flow_has_no_step(self, user_tools_dir, install_dummy_tool):
        install_dummy_tool(user_tools_dir)
        assert eda_tools.get_flow_step_names("vivado", "standard", "analysis") == []
        assert eda_tools.get_flow_steps("dummy", "synthesis", "fmax_synthesis") is None

    def test_steps_are_inherited_by_name_keeping_the_declared_order(self, user_tools_dir):
        write_tool(
            user_tools_dir,
            "mytool",
            """\
            default_metrics_file: metrics.yml
            unix:
              tool_test_command: true
              custom_freq_synthesis_steps:
                - name: first
                  command: run_first
                - name: second
                  command: run_second
            flows:
              variant:
                unix:
                  custom_freq_synthesis_steps:
                    - name: third
                      command: run_third
                    - name: second
                      command: run_second_differently
            """,
        )
        steps = eda_tools.get_flow_steps("mytool", "variant", "custom_freq_synthesis")
        # "second" is replaced where it already was; "third" is new, so it goes
        # last whatever order the flow declared it in.
        assert [step["name"] for step in steps] == ["first", "second", "third"]
        assert steps[1]["command"] == "run_second_differently"

    def test_a_flow_declaring_only_steps_supports_the_job_type(self, user_tools_dir):
        write_tool(
            user_tools_dir,
            "mytool",
            """\
            default_metrics_file: metrics.yml
            unix:
              tool_test_command: true
              custom_freq_synthesis_steps:
                - name: first
                  command: run_first
                - name: second
                  command: run_second
            """,
        )
        assert eda_tools.tool_supports("mytool", "custom_freq_synthesis")
        assert eda_tools.get_flow_step_names("mytool", None, "custom_freq_synthesis") == ["first", "second"]

    def test_read_tool_settings_returns_the_steps(self, user_tools_dir, install_dummy_tool):
        install_dummy_tool(user_tools_dir)
        from odatix.lib.read_tool_settings import read_tool_settings

        settings_file = eda_tools.get_tool_settings_file("dummy")
        *_, flow_name, steps = read_tool_settings(
            "dummy", settings_file, synth_type="custom_freq_synthesis", flow="synthesis"
        )
        assert flow_name == "synthesis"
        assert [step["name"] for step in steps] == ["synthesis", "pnr", "bitstream"]

    def test_malformed_steps_are_ignored(self, user_tools_dir):
        write_tool(
            user_tools_dir,
            "mytool",
            """\
            default_metrics_file: metrics.yml
            unix:
              tool_test_command: true
              custom_freq_synthesis_command: one_shot
              custom_freq_synthesis_steps:
                - name: nameless_command_missing
                - command: no_name
            """,
        )
        # Neither entry is usable: the flow stays a one shot one rather than
        # running a silently truncated pipeline.
        assert eda_tools.get_flow_steps("mytool", None, "custom_freq_synthesis") is None
        assert eda_tools.get_flow_command("mytool", None, "custom_freq_synthesis") == "one_shot"


class TestSessions:
    """
    A flow can declare how the tool is opened for a job type ("<job_type>_session")
    and let its steps declare only what they add to it ("args"). The steps of one
    run then share a single process instead of opening and closing the tool once
    per step.
    """

    SESSION_TOOL = """\
        default_metrics_file: metrics.yml
        unix:
          tool_test_command: true
          custom_freq_synthesis_session:
            command: [mytool, -log $log_path/$first_step.log]
            begin: [-source setup.tcl]
            end: [-source exit.tcl]
          custom_freq_synthesis_steps:
            - name: first
              args: [-source first.tcl]
            - name: second
              args: [-source second.tcl]
            - name: apart
              command: mytool_other
        """

    def test_a_step_declaring_args_runs_a_session_of_its_own(self, user_tools_dir):
        write_tool(user_tools_dir, "mytool", self.SESSION_TOOL)
        steps = eda_tools.get_flow_steps("mytool", None, "custom_freq_synthesis")

        # Run alone, a step is the session framing what it adds.
        assert steps[0]["command"] == [
            "mytool", "-log $log_path/$first_step.log", "-source setup.tcl", "-source first.tcl", "-source exit.tcl"
        ]
        # A step declaring its whole command stays a process of its own.
        assert steps[2]["session"] is None
        assert steps[2]["command"] == "mytool_other"

    def test_steps_sharing_a_session_are_run_by_one_process(self, user_tools_dir):
        from odatix.components.synthesis_common import build_job_command

        write_tool(user_tools_dir, "mytool", self.SESSION_TOOL)
        steps = eda_tools.get_flow_steps("mytool", None, "custom_freq_synthesis")
        pipeline = build_job_command(None, steps, None)

        # Two processes for three steps: the two sharing a session, then the one
        # declaring its own command.
        assert len(pipeline) == 2
        assert pipeline[0][0]["steps"] == ["first", "second"]
        assert pipeline[0][0]["command"] == (
            "mytool -log $log_path/first.log -source setup.tcl -source first.tcl -source second.tcl -source exit.tcl"
        )
        assert pipeline[1][0]["steps"] == ["apart"]

    def test_a_run_resuming_opens_the_session_on_what_is_left(self, user_tools_dir):
        from odatix.components.synthesis_common import build_job_command

        write_tool(user_tools_dir, "mytool", self.SESSION_TOOL)
        steps = eda_tools.get_flow_steps("mytool", None, "custom_freq_synthesis")
        pipeline = build_job_command(None, steps, None, start_index=1)

        # "first" is already done: it is not run again, and the session covers
        # exactly what is left — including the log it is named after.
        assert pipeline[0][0]["steps"] == ["second"]
        assert "-source first.tcl" not in pipeline[0][0]["command"]
        assert "-log $log_path/second.log" in pipeline[0][0]["command"]

    def test_a_flow_changes_the_session_and_keeps_the_steps(self, user_tools_dir):
        write_tool(
            user_tools_dir,
            "mytool",
            self.SESSION_TOOL
            + """flows:
          variant:
            unix:
              custom_freq_synthesis_session:
                begin: [-source setup.tcl, -source variant.tcl]
        """,
        )
        steps = eda_tools.get_flow_steps("mytool", "variant", "custom_freq_synthesis")
        # The session is merged key by key: the flow changed what every session
        # sources on opening and inherited the rest, steps included.
        assert [step["name"] for step in steps] == ["first", "second", "apart"]
        assert "-source variant.tcl" in steps[0]["command"]
        assert steps[0]["command"][0] == "mytool"

    def test_a_step_with_args_and_no_session_is_dropped(self, user_tools_dir):
        write_tool(
            user_tools_dir,
            "mytool",
            """\
            default_metrics_file: metrics.yml
            unix:
              tool_test_command: true
              custom_freq_synthesis_steps:
                - name: first
                  command: run_first
                - name: orphan
                  args: [-source orphan.tcl]
            """,
        )
        # Nothing can be built from a fragment with no session to put it in.
        assert eda_tools.get_flow_step_names("mytool", None, "custom_freq_synthesis") == ["first"]


class TestStepIsNotADimension:
    def test_a_job_advancing_replaces_its_own_record(self):
        """
        A job resumed to a further step refines its result: its record must be
        replaced, not duplicated. The flow, on the other hand, is a dimension.
        """
        import odatix.lib.results_schema as results_schema

        def record(flow, step):
            return results_schema.make_record(
                {
                    results_schema.META_TYPE: "custom_freq_synthesis",
                    results_schema.META_TARGET: "t",
                    results_schema.META_ARCHITECTURE: "a",
                    results_schema.META_CONFIGURATION: "c",
                    results_schema.META_FLOW: flow,
                    results_schema.META_STEP: step,
                },
                {"Fmax": 100},
            )

        records = results_schema.upsert_records([], [record("staged", "synthesis")])
        records = results_schema.upsert_records(records, [record("staged", "pnr")])
        assert len(records) == 1
        assert records[0]["meta"][results_schema.META_STEP] == "pnr"

        # Another flow of the same tool is a separate point.
        records = results_schema.upsert_records(records, [record("power_opt", "pnr")])
        assert len(records) == 2


class TestToolInheritance:
    """A tool extending another one is that tool run differently."""

    def test_a_tool_extends_another_and_changes_a_parameter(self, user_tools_dir):
        write_tool(
            user_tools_dir,
            "base",
            """\
            default_metrics_file: metrics.yml
            default_flow: plain
            parameters:
              shell: base_shell
            unix:
              tool_test_command: [$shell, -version]
              custom_freq_synthesis_command: [$shell, -f, $script_path/run.tcl]
            flows:
              fast:
                parameters:
                  effort: low
            format:
              logs:
                error: ['<error>', 'Error:']
            """,
        )
        write_tool(
            user_tools_dir,
            "derived",
            """\
            extends: base
            label: Derived
            parameters:
              shell: derived_shell
            """,
        )
        assert eda_tools.tool_lineage("derived") == ["base", "derived"]
        assert eda_tools.get_tool_label("derived") == "Derived"
        flows = eda_tools.list_flows("derived")
        assert list(flows) == ["plain", "fast"]
        # The binary changes in every flow, the rest of the strategy stays.
        assert eda_tools.get_flow_command("derived", "fast", "custom_freq_synthesis") == [
            "derived_shell", "-f", "$script_path/run.tcl"
        ]
        assert flows["fast"]["tool_test_command"] == ["derived_shell", "-version"]
        assert flows["fast"]["parameters"] == {"shell": "derived_shell", "effort": "low"}
        # The base tool is left alone.
        assert eda_tools.get_flow_command("base", "fast", "custom_freq_synthesis")[0] == "base_shell"
        # Its scripts and its log formatting come from the tool it extends.
        assert eda_tools.get_tool_dirs("derived") == [
            str(user_tools_dir / "base"), str(user_tools_dir / "derived")
        ]
        assert eda_tools.get_format_settings_file("derived").endswith(os.path.join("base", "tool.yml"))

    def test_a_cycle_stops_the_lineage(self, user_tools_dir):
        write_tool(user_tools_dir, "a", "extends: b\n")
        write_tool(user_tools_dir, "b", "extends: a\n")
        assert eda_tools.tool_lineage("a") == ["b", "a"]

    def test_extending_an_unknown_tool_is_extending_nothing(self, user_tools_dir):
        write_tool(user_tools_dir, "lonely", "extends: nowhere\n")
        assert eda_tools.tool_lineage("lonely") == ["lonely"]


class TestFlowParameters:
    def test_parameters_are_merged_key_by_key(self, user_tools_dir):
        write_tool(
            user_tools_dir,
            "tuned",
            """\
            default_metrics_file: metrics.yml
            parameters:
              effort: medium
              options: [-a]
            unix:
              tool_test_command: true
              custom_freq_synthesis_command: [run, $effort, $options, $effort_bis]
            flows:
              high:
                parameters:
                  effort: high
            """,
        )
        assert eda_tools.get_flow_parameters("tuned", "high") == {"effort": "high", "options": ["-a"]}
        # A list reads as its words in a command; a name only matches whole.
        assert eda_tools.get_flow_command("tuned", "high", "custom_freq_synthesis") == [
            "run", "high", "-a", "$effort_bis"
        ]
        assert eda_tools.get_flow_parameters("tuned") == {"effort": "medium", "options": ["-a"]}

    def test_parameters_reach_the_tcl_settings(self):
        from odatix.lib.prepare_work import tcl_flow_parameters

        assert tcl_flow_parameters({}) == "[dict create]"
        assert tcl_flow_parameters({
            "compile": "compile_ultra",
            "options": ["-retime", "-timing_high_effort_script"],
            "gate_clock": True,
            "max_area": 0,
        }) == (
            "[dict create {compile} {compile_ultra} {options} [list {-retime} {-timing_high_effort_script}]"
            " {gate_clock} 1 {max_area} {0}]"
        )
        # Braces that do not pair up cannot be braced: they are escaped.
        assert tcl_flow_parameters({"odd": "a}b"}) == "[dict create {odd} a\\}b]"

    def test_the_workspace_model_keeps_the_parameters(self):
        from odatix.workspace.tools import ToolSettings

        data = {
            "default_flow": "plain",
            "parameters": {"shell": "x"},
            "unix": {"tool_test_command": "true", "custom_freq_synthesis_command": ["run"]},
            "flows": {"fast": {"label": "Fast", "parameters": {"effort": "low"}}},
        }
        settings = ToolSettings.from_dict(data)
        assert settings.flow("plain").parameters == {"shell": "x"}
        assert settings.flow("fast").parameters == {"effort": "low"}
        document = settings.to_document()
        assert dict(document["parameters"]) == {"shell": "x"}
        assert dict(document["flows"]["fast"]["parameters"]) == {"effort": "low"}
        # The default flow's parameters sit at the top level, and it has
        # nothing else to say under "flows".
        assert "plain" not in document["flows"]
        assert ToolSettings.from_dict(settings.to_dict()).flow("fast").parameters == {"effort": "low"}


class TestToolsWithoutMetrics:
    def test_verilator_declares_no_metrics(self, user_tools_dir, capsys):
        """An RTL linter measures nothing: it must not borrow another tool's metrics."""
        from odatix.lib.read_tool_settings import read_tool_settings
        import odatix.lib.metrics as metrics_lib

        settings_file = eda_tools.get_tool_settings_file("verilator")
        _, _, _, metrics_file, flow_name, _ = read_tool_settings("verilator", settings_file, synth_type="analysis")
        assert (metrics_file, flow_name) == (None, "lint")
        assert metrics_lib.metrics_files("verilator", missing_ok=True) == []
        assert "error" not in capsys.readouterr().out
