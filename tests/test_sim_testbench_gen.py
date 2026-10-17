"""
The minimal testbench Odatix generates for a design that has none
(odatix.sim.hdl_header, odatix.sim.testbench_gen).
"""

import os
import shutil
import subprocess
import textwrap

import pytest
import yaml

import odatix.sim.design_info as design_info
import odatix.sim.hdl_header as hdl_header
import odatix.sim.testbench_gen as testbench_gen
from conftest import EXAMPLES_DIR
from odatix.run import Run
from odatix.workspace import Workspace

SIMULATORS = {"ghdl": "ghdl", "verilator": "verilator", "questa": "vsim", "xsim": "xelab", "icarus": "iverilog"}


def example_source(path):
    with open(os.path.join(EXAMPLES_DIR, "examples", path)) as f:
        return f.read()


######################################
# Reading the header of the top
######################################

class TestSystemVerilogHeader:
    def test_cordic(self):
        header = hdl_header.parse(example_source("cordic_sv/cordic.sv"), "cordic", "sv")
        assert [(p.name, p.declaration) for p in header.parameters] == [
            ("WIDTH", "int WIDTH = 16"), ("ITERATIONS", "int ITERATIONS = 12"),
        ] or [(p.name, p.declaration) for p in header.parameters] == [
            ("WIDTH", "WIDTH = 16"), ("ITERATIONS", "ITERATIONS = 12"),
        ]
        ports = {p.name: (p.direction, p.type) for p in header.ports}
        assert ports["clock"] == ("input", "logic")
        assert ports["i_x"] == ("input", "logic signed [WIDTH-1:0]")
        assert ports["o_y"] == ("output", "logic signed [WIDTH-1:0]")

    def test_a_package_type_and_its_import(self):
        header = hdl_header.parse(example_source("alu_sv/alu.sv"), "alu", "sv")
        assert header.context == ["import pck_control::*;"]
        assert header.port("i_sel_op").type == "sel_alu_op_e"

    def test_shared_declarations(self):
        header = hdl_header.parse(textwrap.dedent("""
            import p::*;
            module top #(parameter A = 1, B = 2, parameter logic [3:0] C = 4'h3) (
              input wire clk, rst_n,
              input [7:0] a, b,     // two bytes
              output reg [7:0] q,
              output p::word_t w
            );
            endmodule
            """), "top", "sv")
        assert [p.declaration for p in header.parameters] == ["A = 1", "B = 2", "logic [3:0] C = 4'h3"]
        assert [(p.name, p.direction, p.type) for p in header.ports] == [
            ("clk", "input", "logic"), ("rst_n", "input", "logic"),
            ("a", "input", "logic [7:0]"), ("b", "input", "logic [7:0]"),
            ("q", "output", "logic [7:0]"), ("w", "output", "p::word_t"),
        ]
        assert header.context == ["import p::*;"]

    @pytest.mark.parametrize("text, message", [
        ("module top(a, b); input a; output b; endmodule", "non-ANSI"),
        ("module top(axi_if.slave bus, input clk); endmodule", "interface"),
        ("module top #(parameter type T = int)(input T a); endmodule", "type parameter"),
        ("module other; endmodule", 'no module "top"'),
    ])
    def test_what_is_not_handled(self, text, message):
        with pytest.raises(hdl_header.HeaderError) as error:
            hdl_header.parse(text, "top", "sv")
        assert message in str(error.value)


class TestVhdlHeader:
    def test_cordic(self):
        header = hdl_header.parse(example_source("cordic_vhdl/cordic.vhdl"), "cordic", "vhdl")
        assert [p.declaration for p in header.parameters] == ["WIDTH : integer := 16", "ITERATIONS : integer := 12"]
        ports = {p.name: (p.direction, p.type) for p in header.ports}
        assert ports["clock"] == ("in", "std_logic")
        assert ports["i_x"] == ("in", "std_logic_vector(WIDTH-1 downto 0)")
        assert ports["o_valid"] == ("out", "std_logic")
        assert "use IEEE.NUMERIC_STD.ALL;" in header.context

    def test_shared_declarations(self):
        header = hdl_header.parse(textwrap.dedent("""
            library ieee;
            use ieee.std_logic_1164.all;
            entity other is end;
            library ieee;
            use ieee.numeric_std.all;
            entity top is
              generic (N, M : natural := 4);
              port (
                clk, rst : in std_logic;
                a : in unsigned(N-1 downto 0) := (others => '0');
                q : out std_logic_vector(M-1 downto 0)
              );
            end entity;
            """), "top", "vhdl")
        assert [p.declaration for p in header.parameters] == ["N : natural := 4", "M : natural := 4"]
        assert [(p.name, p.type) for p in header.ports] == [
            ("clk", "std_logic"), ("rst", "std_logic"), ("a", "unsigned(N-1 downto 0)"),
            ("q", "std_logic_vector(M-1 downto 0)"),
        ]
        assert header.context == ["library ieee;", "use ieee.numeric_std.all;"]

    @pytest.mark.parametrize("text, message", [
        ("entity top is port (a : in std_logic_vector); end;", "unconstrained"),
        ("entity top is generic (N : natural); port (a : in bit); end;", "no default value"),
        ("entity top is port (a : std_logic); end;", "no mode"),
    ])
    def test_what_is_not_handled(self, text, message):
        with pytest.raises(hdl_header.HeaderError) as error:
            hdl_header.parse(text, "top", "vhdl")
        assert message in str(error.value)


@pytest.mark.parametrize("name, active_low", [
    ("reset", False), ("rst", False), ("i_rst", False), ("reset_in", False), ("areset", False),
    ("rst_n", True), ("resetn", True), ("rstn", True), ("nreset", True), ("n_rst", True), ("arst_ni", True),
    ("i_rst_n", True), ("reset_b", True),
])
def test_the_reset_polarity_is_guessed_from_its_name(name, active_low):
    assert design_info.reset_is_active_low(name) is active_low


######################################
# The generated testbench
######################################

def generated(work_dir, language, rtl, top, **testbench):
    """Write a design into a work directory, and generate its testbench."""
    path = os.path.join(str(work_dir), "rtl", "top." + ("vhd" if language == "vhdl" else "sv"))
    os.makedirs(os.path.dirname(path))
    with open(path, "w") as f:
        f.write(textwrap.dedent(rtl))
    info = design_info.build_info(str(work_dir), top=top, clock="clk", reset="rst_n", testbench=testbench)
    assert info["testbench"]["generated"]
    filename, tb_top, tb_language = testbench_gen.write(info, str(work_dir))
    with open(os.path.join(str(work_dir), filename)) as f:
        return f.read(), info


class TestGeneration:
    COUNTER_SV = """
        module top #(parameter W = 4) (input logic clk, input logic rst_n, input logic en, output logic [W-1:0] q);
          always_ff @(posedge clk) if (!rst_n) q <= '0; else if (en) q <= q + 1'b1;
        endmodule
        """

    def test_systemverilog(self, tmp_path):
        text, info = generated(tmp_path, "sv", self.COUNTER_SV, "top")
        assert info["dut"]["reset_active_low"] is True
        assert "localparam W = 4;" in text
        assert "logic [W-1:0] q;" in text
        assert "rst_n = 1'b0;" in text and "rst_n = 1'b1;" in text
        assert "en = {4{$urandom}};" in text
        assert "$isunknown(q)" in text
        assert '$dumpvars(0, dut);' in text
        assert "ODATIX_CYCLES = 1000;" in text

    def test_the_timescale_of_the_design(self, tmp_path):
        text, _info = generated(tmp_path, "sv", self.COUNTER_SV, "top")
        assert "`timescale" not in text
        timed, _info = generated(tmp_path / "timed", "sv", "`timescale 1ns / 1ps\n" + self.COUNTER_SV, "top")
        assert timed.startswith("`timescale 1ns / 1ps\n")

    def test_options(self, tmp_path):
        text, _info = generated(tmp_path, "sv", self.COUNTER_SV, "top", cycles=50, stimulus="zero", waves=False)
        assert "ODATIX_CYCLES = 50;" in text
        assert "$urandom" not in text
        assert "$dumpvars" not in text

    def test_vhdl(self, tmp_path):
        text, _info = generated(tmp_path, "vhdl", """
            library ieee;
            use ieee.std_logic_1164.all;
            use ieee.numeric_std.all;
            entity top is
              generic (W : natural := 4);
              port (clk : in std_logic; rst_n : in std_logic; en : in std_logic; d : in unsigned(W-1 downto 0);
                    q : out std_logic_vector(W-1 downto 0));
            end entity;
            architecture rtl of top is begin q <= std_logic_vector(d); end;
            """, "top")
        assert "constant W : natural := 4;" in text
        assert "signal clk : std_logic := '0';" in text
        assert "d <= unsigned(odatix_random_vector(d'length));" in text
        assert "if is_x(q) then" in text
        assert text.count("use ieee.numeric_std.all;") == 1

    def test_the_settings_say_what_to_generate(self):
        from odatix.lib.simulation_handler import check_testbench

        assert check_testbench({"cycles": 100, "stimulus": "zero", "waves": False}) is None
        assert "cycles" in check_testbench({"cycles": 0})
        assert "stimulus" in check_testbench({"stimulus": "ones"})
        assert "waves" in check_testbench({"waves": "maybe"})


######################################
# Runs
######################################

def without_testbench(workspace, architecture):
    path = workspace / "odatix_userconfig" / "architectures" / architecture / "_settings.yml"
    data = yaml.safe_load(path.read_text())
    data.pop("testbench", None)
    path.write_text(yaml.dump(data))


def run_job(workspace, simulation, architecture):
    jobs = Run(Workspace.open(), "simulation", simulations=[simulation], architectures=[architecture], noask=True).prepare().job_list
    assert len(jobs) == 1
    job = jobs[0]
    completed = subprocess.run(
        job.command, shell=True, cwd=job.directory, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        universal_newlines=True,
    )
    with open(os.path.join(job.directory, "sim_report.yml")) as f:
        return completed, yaml.safe_load(f), job.directory


def needs(template):
    if shutil.which(SIMULATORS[template]) is None:
        pytest.skip("needs " + SIMULATORS[template])


class TestRuns:
    CASES = [
        ("ghdl", "Example_Counter_vhdl/08bits"),
        ("icarus", "Example_Counter_sv/08bits"),
        ("icarus", "Example_ALU_sv/08bits"),
        ("verilator", "Example_ALU_sv/16bits"),
        ("verilator", "Example_Shift_Register_sv/08bits"),
        ("questa", "Example_Counter_vhdl/08bits"),
        ("questa", "Example_Counter_verilog/08bits"),
        ("xsim", "Example_Counter_sv/08bits"),
        ("ghdl", "Example_Cordic_vhdl + iterations/12 + width/8"),
        ("icarus", "Example_Cordic_sv + iterations/12 + width/8"),
    ]

    @pytest.mark.integration
    @pytest.mark.parametrize("template, architecture", CASES)
    def test_a_design_without_testbench_runs(self, example_workspace, template, architecture):
        needs(template)
        without_testbench(example_workspace, architecture.split("/")[0].split("+")[0].strip())
        completed, report, work = run_job(example_workspace, template, architecture)
        assert completed.returncode == 0, completed.stdout[-3000:]
        assert report["status"] == "passed"
        assert report["cycles"] == 1000
        assert os.path.getsize(os.path.join(work, "odatix_sim.vcd")) > 0
        with open(os.path.join(work, "odatix_sim.yml")) as f:
            info = yaml.safe_load(f)
        assert info["testbench"]["top"] == "odatix_tb" and info["testbench"]["generated"]

    @pytest.mark.integration
    def test_the_architecture_says_how_many_cycles(self, example_workspace):
        needs("icarus")
        path = example_workspace / "odatix_userconfig" / "architectures" / "Example_Counter_sv" / "_settings.yml"
        data = yaml.safe_load(path.read_text())
        data["testbench"] = {"cycles": 50, "waves": False}
        path.write_text(yaml.dump(data))
        completed, report, work = run_job(example_workspace, "icarus", "Example_Counter_sv/08bits")
        assert completed.returncode == 0, completed.stdout[-3000:]
        assert report["cycles"] == 50
        assert not os.path.exists(os.path.join(work, "odatix_sim.vcd"))

    @pytest.mark.integration
    def test_an_unknown_output_fails_the_simulation(self, example_workspace):
        needs("icarus")
        (example_workspace / "rtl_x").mkdir()
        (example_workspace / "rtl_x" / "top.sv").write_text(
            "module top(input logic clock, input logic reset, input logic d, output logic q, output logic never);\n"
            "  always_ff @(posedge clock) q <= reset ? 1'b0 : d;\n"
            "endmodule\n"
        )
        settings = example_workspace / "odatix_userconfig" / "architectures" / "Unknown" / "_settings.yml"
        settings.parent.mkdir()
        settings.write_text(
            'rtl_path: "rtl_x"\ntop_level_file: "top.sv"\ntop_level_module: "top"\n'
            'clock_signal: "clock"\nreset_signal: "reset"\nuse_parameters: No\n'
        )
        completed, report, _work = run_job(example_workspace, "icarus", "Unknown")
        assert completed.returncode == 1
        assert report["status"] == "failed"
        assert "output never is unknown at cycle 1" in completed.stdout
        # Reported 10 times, not once per cycle
        assert completed.stdout.count("output never is unknown") == testbench_gen.REPORTED_UNKNOWNS

    @pytest.mark.integration
    def test_a_header_it_cannot_read_says_what_to_do(self, example_workspace):
        needs("icarus")
        (example_workspace / "rtl_if").mkdir()
        (example_workspace / "rtl_if" / "top.sv").write_text(
            "interface bus_if; logic a; endinterface\nmodule top(bus_if bus, input logic clock, input logic reset); endmodule\n"
        )
        settings = example_workspace / "odatix_userconfig" / "architectures" / "Interface" / "_settings.yml"
        settings.parent.mkdir()
        settings.write_text(
            'rtl_path: "rtl_if"\ntop_level_file: "top.sv"\ntop_level_module: "top"\n'
            'clock_signal: "clock"\nreset_signal: "reset"\nuse_parameters: No\n'
        )
        completed, report, _work = run_job(example_workspace, "icarus", "Interface")
        assert completed.returncode == 1
        assert "interface ports are not handled" in report["message"]
        assert '"testbench" in the settings of its architecture' in report["message"]
