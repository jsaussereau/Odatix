"""
odatix.workspace.detect: the "auto detect" guesses of the GUI, from Python.
"""

import pytest

from odatix.workspace import (
    NotFoundError,
    Workspace,
    WorkspaceError,
    detect_parameters,
    detect_sources,
    parameter_domain_settings,
)


def test_sources_of_a_verilog_design_are_guessed(example_workspace):
    found = detect_sources(str(example_workspace / "examples" / "counter_sv"))
    assert found.settings() == {
        "top_level_module": "counter", "top_level_file": "counter.sv",
        "clock_signal": "clock", "reset_signal": "reset",
    }
    assert found.to_dict()["top_level_module"][0]["value"] == "counter"


def test_a_directory_without_hdl_is_reported(in_tmp_dir):
    with pytest.raises(NotFoundError):
        detect_sources(str(in_tmp_dir))


def test_parameters_are_ranked_by_relevance(example_workspace):
    params = detect_parameters(str(example_workspace / "examples" / "cordic_vhdl" / "cordic.vhdl"), sort=True)
    assert [p.name for p in params[:2]] == ["WIDTH", "ITERATIONS"]
    assert params[0].kind == "generic" and params[0].relevance > params[-1].relevance


def test_unknown_parameter_is_reported(example_workspace):
    with pytest.raises(NotFoundError):
        parameter_domain_settings(str(example_workspace / "examples" / "counter_sv" / "counter.sv"), "NOPE")


def test_domain_settings_isolate_the_value(example_workspace):
    settings = parameter_domain_settings(str(example_workspace / "examples" / "counter_sv" / "counter.sv"), "BITS", [8, "16"])
    assert settings["start_delimiter"] == "BITS = "
    assert settings["param_target_file"] == "counter.sv"
    assert settings["variables"] == {"BITS": {"type": "list", "settings": {"list": [8, 16]}}}


def test_an_architecture_is_built_from_its_sources(example_workspace):
    ws = Workspace.open(str(example_workspace))
    arch = ws.architectures.create("Detected")
    arch.settings.rtl_path = "examples/counter_sv"
    arch.settings.clock_signal = "kept"
    changed = arch.fill_from_sources()
    assert "clock_signal" not in changed and arch.settings.clock_signal == "kept"
    assert arch.settings.top_level_module == "counter"
    arch.save()

    assert [p.name for p in arch.detect_parameters()] == ["BITS"]
    domain = arch.domains.create_from_parameter("BITS", [8, 16, 32])
    assert domain.configuration_names() == ["8", "16", "32"]
    assert ws.architectures["Detected"].domains["BITS"].settings.param_target_file == "counter.sv"


def test_domains_from_parameters_need_a_file(example_workspace):
    arch = Workspace.open(str(example_workspace)).architectures.create("NoFile")
    with pytest.raises(WorkspaceError):
        arch.domains.create_from_parameter("BITS")


def test_detection_needs_the_rtl_path(example_workspace):
    arch = Workspace.open(str(example_workspace)).architectures.create("NoPath")
    for rtl_path in ("", "."):
        arch.settings.rtl_path = rtl_path
        with pytest.raises(WorkspaceError):
            arch.fill_from_sources()


def test_a_run_refuses_an_rtl_path_holding_the_work_directory(example_workspace):
    from odatix.run import Run
    from odatix.run.errors import RunError

    arch = Workspace.open(str(example_workspace)).architectures.create("Everything")
    arch.update(rtl_path=".", top_level_file="examples/counter_sv/counter.sv",
                top_level_module="counter", clock_signal="clock", reset_signal="reset")
    run = Run(Workspace.open(str(example_workspace)), "analysis", tool="verilator",
              architectures=["Everything"], check_eda_tool=False, quiet=True)
    try:
        plan = run.check()
    except RunError:
        return
    assert not plan.jobs


def test_init_writes_the_guide_of_agents(in_tmp_dir):
    from odatix.lib.settings import OdatixSettings

    assert OdatixSettings.init_path()
    text = (in_tmp_dir / "AGENTS.md").read_text()
    assert text.startswith("# Odatix workspace") and OdatixSettings.AGENTS_BEGIN not in text


def test_init_adds_its_notes_to_an_existing_guide_once(in_tmp_dir):
    from odatix.lib.settings import OdatixSettings

    (in_tmp_dir / "AGENTS.md").write_text("# My project\n\nRun make test.")
    assert OdatixSettings.init_path()
    assert OdatixSettings.init_path()
    text = (in_tmp_dir / "AGENTS.md").read_text()
    assert text.startswith("# My project\n\nRun make test.\n")
    assert text.count(OdatixSettings.AGENTS_BEGIN) == 1
    assert "\n## Odatix workspace: notes for AI agents\n" in text and "\n### Layout\n" in text
    assert "\n# Run, then read the results" not in text and "arch.fill_from_sources()           # take" in text


######################################
# Designs of tests/fixtures/rtl, with what their detection should guess
######################################

import os
import shutil

from conftest import FIXTURES_DIR

RTL_FIXTURES = os.path.join(FIXTURES_DIR, "rtl")

DESIGNS = [
    # directory, file of the parameters, top level, clock, reset, parameters to sweep, derived ones
    ("fir", "fir_filter.v", "fir_filter", "clk", "rst", ["DATA_WIDTH", "COEF_WIDTH", "TAPS"], ["ACC_WIDTH", "COEF"]),
    ("mavg", "moving_average.vhd", "moving_average", "clock_in", "areset_n", ["WIDTH", "DEPTH_LOG2"], ["DEPTH"]),
    # A testbench in the same directory is not the top level
    ("scrambler", "lfsr_scrambler.sv", "lfsr_scrambler", "i_sys_clk", "i_rst_n", ["LANES", "LFSR_LEN"], []),
    # Parameters in a package of another file
    ("adder_tree", "tree_config_pkg.sv", "adder_tree", "clk_core", "sync_rst",
     ["N_INPUTS", "IN_WIDTH", "REGISTER_LEVELS"], ["LEVELS", "OUT_WIDTH"]),
]


@pytest.mark.parametrize("directory, file, top, clock, reset, swept, derived", DESIGNS, ids=[d[0] for d in DESIGNS])
def test_the_designs_of_the_fixtures_are_guessed(directory, file, top, clock, reset, swept, derived):
    found = detect_sources(os.path.join(RTL_FIXTURES, directory))
    assert (found.top.value, found.clock.value, found.reset.value) == (top, clock, reset)

    params = detect_parameters(os.path.join(RTL_FIXTURES, directory, file), sort=True)
    relevance = dict((p.name, p.relevance) for p in params)
    assert [p.name for p in params[:len(swept)]] == swept
    assert all(relevance[name] < min(relevance[s] for s in swept) for name in derived)


def test_a_domain_sweeps_a_parameter_of_a_package(example_workspace):
    shutil.copytree(os.path.join(RTL_FIXTURES, "adder_tree"), str(example_workspace / "rtl" / "adder_tree"))
    arch = Workspace.open(str(example_workspace)).architectures.create("AdderTree")
    arch.settings.rtl_path = "rtl/adder_tree"
    arch.fill_from_sources()
    arch.save()
    assert arch.settings.top_level_file == "adder_tree.sv"

    # The top level only has local copies of the parameters of the package
    assert max(p.relevance for p in arch.detect_parameters()) < 5
    assert arch.detect_parameters(file="tree_config_pkg.sv")[0].name == "N_INPUTS"
    domain = arch.domains.create_from_parameter("N_INPUTS", [4, 8, 16], file="tree_config_pkg.sv")
    assert domain.settings.param_target_file == "tree_config_pkg.sv"
    assert domain.configuration_names() == ["4", "8", "16"]
