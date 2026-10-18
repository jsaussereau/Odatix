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

# "-j" builds the C++ with the cores this job may use: "-j 0" takes every core
# in each of the jobs running at once, which runs them all slower.
command = [
    "verilator", "--binary", "--assert", "-j", str(sim.build_jobs), "-Wno-fatal",
    "--top-module", top, "-Mdir", "obj_dir", "-o", "odatix_sim",
]
if sim.waves:
    # "$dumpvars" in the testbench only records something when traced
    command += ["--trace"]
command += ["+incdir+" + directory for directory in sim.include_dirs]
command += parameter_args(sim.tb_parameters, "-G{name}={value}")
command += sim.files("verilog", "sv")

# Verilating and building the C++ is both compiling and elaborating: there is
# no elaboration time of its own (see _metrics.yml).
sim.run("compile", command, log="verilator")
sim.run("simulate", [os.path.join("obj_dir", "odatix_sim")], log="simulation")
sim.finish()
