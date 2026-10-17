"""
What Odatix tells a simulation about the design under test: "odatix_sim.yml",
"odatix_sim.f" and the placeholders of its commands (odatix.sim.design_info).
"""

import os
import shutil
import subprocess
import textwrap

import pytest
import yaml

import odatix.sim.design_info as design_info
from odatix.run import Run
from odatix.workspace import Workspace


def write(root, relpath, text):
    path = os.path.join(str(root), relpath)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(textwrap.dedent(text))
    return path


# A design whose files, sorted by name, are in the wrong compilation order: the
# top uses a package and a sub-entity that come after it.
VHDL_DESIGN = {
    "rtl/a_top.vhd": """
        library ieee;
        use ieee.std_logic_1164.all;
        use work.b_pkg.all;

        entity a_top is
          port (clk : in std_logic; q : out std_logic_vector(WIDTH-1 downto 0));
        end entity a_top;

        architecture rtl of a_top is
        begin
          u_sub: entity work.c_sub port map (clk => clk, q => q);
        end architecture;
        """,
    "rtl/c_sub.vhd": """
        library ieee;
        use ieee.std_logic_1164.all;
        use work.b_pkg.all;  -- entity not_a_unit is

        entity c_sub is
          port (clk : in std_logic; q : out std_logic_vector(WIDTH-1 downto 0));
        end entity c_sub;

        architecture rtl of c_sub is
        begin
          q <= (others => '0');
        end architecture;
        """,
    "rtl/pkg/z_pkg.vhd": """
        package b_pkg is
          constant WIDTH : integer := 4;
          function twice(x : integer) return integer;
        end package;
        """,
    "rtl/pkg/y_pkg_body.vhd": """
        package body b_pkg is
          function twice(x : integer) return integer is
          begin
            return 2 * x;
          end function;
        end package body;
        """,
}


class TestCompilationOrder:
    def test_vhdl_packages_and_entities_come_first(self, tmp_path):
        for relpath, text in VHDL_DESIGN.items():
            write(tmp_path, relpath, text)
        sources = design_info.collect_sources(str(tmp_path))
        vhdl = sources["vhdl"]
        assert sources["order"] == "dependencies"
        assert vhdl.index("rtl/pkg/z_pkg.vhd") < vhdl.index("rtl/c_sub.vhd") < vhdl.index("rtl/a_top.vhd")
        assert vhdl.index("rtl/pkg/z_pkg.vhd") < vhdl.index("rtl/pkg/y_pkg_body.vhd")

    @pytest.mark.skipif(shutil.which("ghdl") is None, reason="needs ghdl")
    def test_the_order_compiles(self, tmp_path):
        """GHDL analyses files one by one: a wrong order fails."""
        for relpath, text in VHDL_DESIGN.items():
            write(tmp_path, relpath, text)
        for path in design_info.collect_sources(str(tmp_path))["vhdl"]:
            subprocess.check_call(["ghdl", "-a", "--std=08", path], cwd=str(tmp_path))
        subprocess.check_call(["ghdl", "-e", "--std=08", "a_top"], cwd=str(tmp_path))

    def test_a_sv_package_comes_before_its_importers(self, tmp_path):
        write(tmp_path, "rtl/a_core.sv", "import z_types::*;\nmodule a_core(output word_t q); endmodule\n")
        write(tmp_path, "rtl/b_util.v", "module b_util; endmodule\n")
        write(tmp_path, "rtl/z_types.sv", "package z_types;\n  typedef logic [3:0] word_t;\nendpackage\n")
        write(tmp_path, "rtl/inc/defs.svh", "`define W 4\n")
        sources = design_info.collect_sources(str(tmp_path))
        assert sources["sv"] == ["rtl/z_types.sv", "rtl/a_core.sv"]
        assert sources["verilog"] == ["rtl/b_util.v"]
        assert sources["include_dirs"] == ["rtl/inc"]

    def test_independent_files_keep_their_order(self, tmp_path):
        for name in ("c.sv", "a.sv", "b.sv"):
            write(tmp_path, "rtl/" + name, "module " + name[0] + "; endmodule\n")
        assert design_info.collect_sources(str(tmp_path))["sv"] == ["rtl/a.sv", "rtl/b.sv", "rtl/c.sv"]

    def test_a_cycle_does_not_lose_files(self, tmp_path):
        write(tmp_path, "rtl/a.sv", "package a; import b::*; endpackage\n")
        write(tmp_path, "rtl/b.sv", "package b; import a::*; endpackage\n")
        assert sorted(design_info.collect_sources(str(tmp_path))["sv"]) == ["rtl/a.sv", "rtl/b.sv"]

    def test_a_filelist_gives_the_order(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ODATIX_TEST_LIB", "lib")
        write(tmp_path, "rtl/top.sv", "module top; endmodule\n")
        write(tmp_path, "rtl/pkg.sv", "package pkg; endpackage\n")
        write(tmp_path, "rtl/lib/util.vhd", "entity util is end;\n")
        write(tmp_path, "rtl/more.f", "pkg.sv\n")
        write(tmp_path, "rtl/filelist.f", """
            // the top first, on purpose
            +incdir+inc+$ODATIX_TEST_LIB
            -timescale 1ns/1ps
            top.sv   # a comment
            -f more.f
            ${ODATIX_TEST_LIB}/util.vhd
            notes.txt
            """)
        sources = design_info.collect_sources(str(tmp_path))
        assert sources["order"] == "filelist"
        assert sources["sv"] == ["rtl/top.sv", "rtl/pkg.sv"]
        assert sources["vhdl"] == ["rtl/lib/util.vhd"]
        assert sources["include_dirs"] == ["rtl/inc", "rtl/lib"]


class TestTestbench:
    def test_the_tb_directory_is_the_default(self, tmp_path):
        write(tmp_path, "tb/tb_dut.sv", "module tb_dut; dut u (.a(1)); endmodule\n")
        write(tmp_path, "tb/model.cpp", "int main() {}\n")
        testbench = design_info.collect_testbench(str(tmp_path), dut_top="dut")
        assert testbench == {"top": "tb_dut", "files": ["tb/tb_dut.sv"], "languages": ["sv"]}

    def test_the_top_is_the_unit_nothing_instantiates(self, tmp_path):
        write(tmp_path, "tb/bench.vhd", """
            entity helper is end entity helper;
            architecture a of helper is begin end;
            entity bench is end entity bench;
            architecture a of bench is
            begin
              u: entity work.helper;
              v : helper port map (x => y);
            end;
            """)
        assert design_info.collect_testbench(str(tmp_path))["top"] == "bench"

    def test_declared_files_and_top(self, tmp_path):
        write(tmp_path, "bench/a.sv", "module a; endmodule\n")
        write(tmp_path, "bench/b.sv", "module b; endmodule\n")
        write(tmp_path, "tb/ignored.sv", "module ignored; endmodule\n")
        testbench = design_info.collect_testbench(str(tmp_path), {"top": "b", "files": ["bench/*.sv"]})
        assert testbench == {"top": "b", "files": ["bench/a.sv", "bench/b.sv"], "languages": ["sv"]}

    def test_the_setting_is_checked(self):
        from odatix.lib.simulation_handler import check_testbench

        assert check_testbench({"top": "tb", "files": ["tb/a.sv"]}) is None
        assert check_testbench({"files": "tb/a.sv"}) is None
        assert "mapping" in check_testbench(["tb/a.sv"])
        assert "unknown keys" in check_testbench({"topp": "tb"})
        assert "files" in check_testbench({"files": 3})


class TestInformationFile:
    def test_written_and_read_back(self, tmp_path):
        for relpath, text in VHDL_DESIGN.items():
            write(tmp_path, relpath, text)
        write(tmp_path, "tb/tb_a_top.sv", "module tb_a_top; a_top dut (.clk(clk)); endmodule\n")
        info = design_info.build_info(
            str(tmp_path), simulation="sim", top="a_top", clock="clk", reset="rst_n", param_domains={"width": 8},
        )
        design_info.write_info(str(tmp_path), info)

        assert design_info.read_info(str(tmp_path)) == info
        assert info["dut"]["languages"] == ["vhdl"]
        assert info["param_domains"] == {"width": "8"}
        with open(os.path.join(str(tmp_path), design_info.SIM_FILELIST_FILENAME)) as f:
            lines = [line.strip() for line in f if not line.startswith("//")]
        assert lines == info["sources"]["vhdl"] + ["tb/tb_a_top.sv"]

        values = design_info.substitutions(info)
        assert values["tb_top"] == "tb_a_top"
        assert values["vhdl_files"].split() == info["sources"]["vhdl"]
        assert values["reset_signal"] == "rst_n"
        assert values["languages"] == "vhdl"

    def test_refreshed_once_the_rtl_is_generated(self, tmp_path):
        info = design_info.build_info(str(tmp_path), top="gen", rtl_generated=True)
        design_info.write_info(str(tmp_path), info)
        assert info["sources"]["verilog"] == []

        write(tmp_path, "rtl/gen.v", "module gen; endmodule\n")
        subprocess.check_call(design_info.refresh_command(str(tmp_path)), shell=True)
        refreshed = design_info.read_info(str(tmp_path))
        assert refreshed["sources"]["verilog"] == ["rtl/gen.v"]
        assert refreshed["dut"]["languages"] == ["verilog"]
        assert refreshed["dut"]["top"] == "gen"


class TestSimulationJobs:
    """The examples, prepared for real: Cordic and Counter, in VHDL and in SV."""

    CASES = [
        ("TB_Example_Cordic_QuestaSim", "Example_Cordic_vhdl + iterations/12 + width/8", "vhdl", "rtl/cordic.vhdl"),
        ("TB_Example_Cordic_QuestaSim", "Example_Cordic_sv + iterations/16 + width/12", "sv", "rtl/cordic.sv"),
        ("TB_Example_Counter_GHDL", "Example_Counter_vhdl/08bits", "vhdl", "rtl/counter.vhdl"),
        ("TB_Example_Counter_Verilator", "Example_Counter_sv/08bits", "sv", "rtl/counter.sv"),
    ]

    @pytest.mark.parametrize("simulation, architecture, language, source", CASES)
    def test_every_job_is_told_about_its_design(self, example_workspace, simulation, architecture, language, source):
        Run(Workspace.open(), "simulation", simulations=[simulation], architectures=[architecture], noask=True).prepare()

        found = []
        for root, _dirs, files in os.walk(str(example_workspace / "work" / "simulations" / simulation)):
            if design_info.SIM_INFO_FILENAME in files:
                found.append(design_info.read_info(root))
        assert len(found) == 1
        info = found[0]
        assert info["simulation"] == simulation
        assert info["dut"]["languages"] == [language]
        assert info["sources"][language] == [source]
        assert info["dut"]["clock"] == "clock"
        assert info["dut"]["reset"] == "reset"
        if "Cordic" in simulation:
            assert info["testbench"]["top"] == "tb_cordic"
            assert info["param_domains"] == dict(
                part.strip().split("/") for part in architecture.split("+")[1:]
            )

    def test_the_commands_get_the_placeholders(self, example_workspace):
        settings = example_workspace / "odatix_userconfig" / "simulations" / "TB_Example_Cordic_QuestaSim" / "_settings.yml"
        data = yaml.safe_load(settings.read_text())
        data["tasks"][0]["commands"] = ["echo ${tb_top} ${languages} ${vhdl_files} ${tb_files} ${reset_signal} ${width}"]
        settings.write_text(yaml.dump(data))

        run = Run(
            Workspace.open(), "simulation", simulations=["TB_Example_Cordic_QuestaSim"],
            architectures=["Example_Cordic_vhdl + iterations/12 + width/8"], noask=True,
        )
        jobs = run.prepare().job_list
        assert [job.command for job in jobs] == ["echo tb_cordic vhdl rtl/cordic.vhdl tb/tb_cordic.sv reset 8"]

    def test_every_placeholder_is_offered_by_the_editors(self):
        from odatix.gui.builtin_variables import BUILTIN_VARIABLES, DEPRECATED_VARIABLES

        offered = {name for name, _ in BUILTIN_VARIABLES["simulation"] + DEPRECATED_VARIABLES["simulation"]}
        assert set(design_info.substitutions({})) <= offered
