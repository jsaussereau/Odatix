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
    monkeypatch.setattr(eda_tools, "platform_key", lambda: "unix")
    return tools_dir


def write_tool(tools_dir, name, content):
    tool_dir = tools_dir / name
    tool_dir.mkdir(parents=True, exist_ok=True)
    (tool_dir / "tool.yml").write_text(textwrap.dedent(content))
    return tool_dir


class TestBuiltinFlows:
    def test_vivado_declares_its_flows(self, user_tools_dir):
        flows = eda_tools.list_flows("vivado")
        assert list(flows) == ["standard", "power_opt"]
        assert flows["standard"]["is_default"]
        assert flows["power_opt"]["label"] == "Power optimized"

    def test_default_flow_comes_first(self, user_tools_dir):
        assert eda_tools.get_default_flow("vivado") == "standard"

    def test_flows_are_filtered_by_job_type(self, user_tools_dir):
        assert eda_tools.get_flow_names("vivado", "fmax_synthesis") == ["standard", "power_opt"]
        # A flow inherits what it does not redefine, so it runs every job type
        # the tool does — here RTL analysis, which power_opt has nothing to say
        # about.
        assert eda_tools.flow_supports("vivado", "power_opt", "analysis")
        assert eda_tools.get_flow_command("vivado", "power_opt", "analysis") == eda_tools.get_flow_command(
            "vivado", "standard", "analysis"
        )
        # A job type the tool itself cannot run is not invented for any flow.
        assert not eda_tools.flow_supports("verilator", "lint", "fmax_synthesis")

    def test_design_compiler_declares_a_dcnxt_flow(self, user_tools_dir):
        assert eda_tools.get_flow_names("design_compiler", "fmax_synthesis") == ["dc_shell", "dcnxt_shell"]
        # Both flows are stepped, the dcnxt one running the same steps with the
        # other binary.
        steps = eda_tools.get_flow_steps("design_compiler", "dcnxt_shell", "fmax_synthesis")
        assert [step["name"] for step in steps] == ["search", "netlist"]
        assert "dcnxt_shell" in str(steps[0]["command"])

    def test_a_flow_running_another_binary_checks_for_that_binary(self, user_tools_dir):
        flows = eda_tools.list_flows("design_compiler")
        assert "dc_shell" in flows["dc_shell"]["tool_test_command"]
        assert "dcnxt_shell" in flows["dcnxt_shell"]["tool_test_command"]

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
        assert set(flows) == {"standard", "power_opt", "gate_level_sim"}
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
        assert set(flows) == {"standard", "power_opt", "mine"}
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

        _, _, command, _, metrics_file, flow_name, _steps = read_tool_settings(
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
        assert metrics_file.endswith("vivado/metrics.yml")

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
        (tool_dir / "gate_level_metrics.yml").write_text("metrics: {}\n")

        # "$tool_path" resolves against the directory shipping the file, even
        # though the tool is also defined in the built-in directory.
        metrics_file = export_results.resolve_metrics_file("vivado", flow="gate_level_sim")
        assert metrics_file == str(tool_dir / "gate_level_metrics.yml")

        # The other flows keep the built-in metrics file.
        assert export_results.resolve_metrics_file("vivado", flow="standard").endswith("vivado/metrics.yml")


class TestFlowSteps:
    """
    Being split into steps is a property of a flow, not a flow of its own: a
    flow declares "<job_type>_steps" (an ordered list of named commands) instead
    of "<job_type>_command", and every flow of a tool can be stepped.
    """

    def test_every_vivado_flow_is_stepped(self, user_tools_dir):
        for job_type in ("fmax_synthesis", "custom_freq_synthesis"):
            for flow in eda_tools.get_flow_names("vivado", job_type):
                assert eda_tools.get_flow_step_names("vivado", flow, job_type) == [
                    "synthesis",
                    "pnr",
                    "bitstream",
                ], (flow, job_type)

    def test_a_flow_redefines_a_step_and_inherits_the_rest(self, user_tools_dir):
        # power_opt changes how the design is synthesized; place & route and
        # bitstream generation work from the checkpoint it leaves, so they are
        # the default flow's, unchanged.
        standard = eda_tools.get_flow_steps("vivado", "standard", "custom_freq_synthesis")
        power_opt = eda_tools.get_flow_steps("vivado", "power_opt", "custom_freq_synthesis")

        assert power_opt[0]["command"] != standard[0]["command"]
        assert "flow_power_opt.tcl" in " ".join(power_opt[0]["command"])
        assert power_opt[1:] == standard[1:]

    def test_a_flow_starting_over_at_every_step_redefines_them_all(self, user_tools_dir):
        # Each step of an fmax search starts again from the RTL, so power_opt
        # cannot inherit any of them: all three have to set the power knobs.
        for step in eda_tools.get_flow_steps("vivado", "power_opt", "fmax_synthesis"):
            assert "flow_power_opt.tcl" in " ".join(step["command"]), step["name"]

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

    def test_dummy_ships_a_stepped_flow(self, user_tools_dir):
        assert eda_tools.get_flow_step_names("dummy", "synthesis", "custom_freq_synthesis") == [
            "synthesis",
            "pnr",
            "bitstream",
        ]

    def test_a_flow_can_replace_inherited_steps_with_one_command(self, user_tools_dir):
        # dummy's "quick" flow declares a plain command where the default flow
        # is stepped: it runs in one go.
        assert eda_tools.get_flow_steps("dummy", "quick", "custom_freq_synthesis") is None
        assert eda_tools.get_flow_command("dummy", "quick", "custom_freq_synthesis")

    def test_a_one_shot_flow_has_no_step(self, user_tools_dir):
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

    def test_read_tool_settings_returns_the_steps(self, user_tools_dir):
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
