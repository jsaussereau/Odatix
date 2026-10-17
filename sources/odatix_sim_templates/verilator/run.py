"""
Simulation template: Verilator.

Run by Odatix in the job's work directory, as "python run.py <odatix_path>".
What it runs is read from "odatix_sim.yml" (see odatix.sim.runner).

The testbench is an ordinary SystemVerilog one: "--binary" builds the
simulator with its own main and timing support, no C++ to write.
"""

import os
import sys

# Odatix runs this script with its own Python and says where it is installed.
if len(sys.argv) > 1:
    sys.path.insert(0, os.path.dirname(os.path.realpath(sys.argv[1])))

from odatix.sim.runner import SimRunner, parameter_args

sim = SimRunner("verilator", languages=["verilog", "sv"])
top = sim.tb_top

command = [
    "verilator", "--binary", "--assert", "-j", "0", "-Wno-fatal",
    "--top-module", top, "-Mdir", "obj_dir", "-o", "odatix_sim",
]
command += ["+incdir+" + directory for directory in sim.include_dirs]
command += parameter_args(sim.tb_parameters, "-G{name}={value}")
command += sim.files("verilog", "sv")

# Verilating and building the C++ is both compiling and elaborating.
sim.run("compile", command, log="verilator")
sim.run("simulate", [os.path.join("obj_dir", "odatix_sim")], log="simulation")
sim.finish()
