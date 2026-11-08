"""
RTL analysis with Icarus and Verilator of a design whose parameters live in a
SystemVerilog package of another file: their library search ("-y rtl") finds
modules by file name, never packages, so those files are given explicitly.
"""

import importlib.util
import os
import shutil
import subprocess

import pytest

from conftest import SOURCES_DIR

EDA_TOOLS = os.path.join(SOURCES_DIR, "odatix_eda_tools")

PACKAGE = "package cfg_pkg;\n  parameter int WIDTH = 8;\nendpackage\n"
TOP = (
    "module top (input logic clk, input logic [cfg_pkg::WIDTH-1:0] d, output logic [cfg_pkg::WIDTH-1:0] q);\n"
    "  always_ff @(posedge clk) q <= d;\n"
    "endmodule\n"
)


@pytest.fixture
def job_dir(tmp_path, monkeypatch):
    (tmp_path / "rtl").mkdir()
    (tmp_path / "rtl" / "top.sv").write_text(TOP)
    (tmp_path / "rtl" / "cfg_pkg.sv").write_text(PACKAGE)
    (tmp_path / "rtl" / "other.sv").write_text("module other; endmodule\n")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "settings.tcl").write_text("set top_level_module top\nset top_level_file top.sv\n")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def load_script():
    spec = importlib.util.spec_from_file_location("rtl_analysis", os.path.join(EDA_TOOLS, "_common", "rtl_analysis.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_package_files_come_before_the_top_level(job_dir):
    script = load_script()
    assert script.package_sources("top.sv") == ["rtl/cfg_pkg.sv"]
    for tool in ("verilator", "icarus"):
        command = script.command(tool, "top", "top.sv")
        assert command[-2:] == ["rtl/cfg_pkg.sv", "rtl/top.sv"]


@pytest.mark.parametrize("tool, program", [("verilator", "verilator"), ("icarus", "iverilog")])
def test_the_makefile_finds_the_package(job_dir, tool, program):
    if shutil.which(program) is None or shutil.which("make") is None:
        pytest.skip(program + " not installed")
    makefile = os.path.join(EDA_TOOLS, tool, "makefile.mk")
    subprocess.run(["make", "-s", "-f", makefile, "analyze"], cwd=str(job_dir), capture_output=True)
    log = (job_dir / "log" / "analysis.log").read_text()
    assert "cfg_pkg" not in log, log
    assert (job_dir / "log" / "synth_status.log").exists()


@pytest.mark.parametrize("tool, program", [("verilator", "verilator"), ("icarus", "iverilog")])
def test_an_adder_tree_configured_by_its_package_elaborates(tmp_path, monkeypatch, tool, program):
    from conftest import FIXTURES_DIR

    if shutil.which(program) is None or shutil.which("make") is None:
        pytest.skip(program + " not installed")
    shutil.copytree(os.path.join(FIXTURES_DIR, "rtl", "adder_tree"), str(tmp_path / "rtl"))
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "settings.tcl").write_text("set top_level_module adder_tree\nset top_level_file adder_tree.sv\n")
    monkeypatch.chdir(tmp_path)
    subprocess.run(["make", "-s", "-f", os.path.join(EDA_TOOLS, tool, "makefile.mk"), "analyze"],
                   cwd=str(tmp_path), capture_output=True)
    log = (tmp_path / "log" / "analysis.log").read_text()
    assert "tree_config_pkg" not in log and "rror" not in log, log
