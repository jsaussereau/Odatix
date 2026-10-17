"""
Simulation template: GHDL.

Run by Odatix in the job's work directory, as "python run.py <odatix_path>".
What it runs is read from "odatix_sim.yml" (see odatix.sim.runner).

GHDL finds the compilation order itself: the files are imported ("ghdl -i"),
then "ghdl -m" analyses what is out of date and elaborates the testbench.
"""

import os
import sys

# Odatix runs this script with its own Python and says where it is installed.
if len(sys.argv) > 1:
    sys.path.insert(0, os.path.dirname(os.path.realpath(sys.argv[1])))

from odatix.sim.runner import SimRunner, parameter_args

OPTIONS = ["--std=08", "-fsynopsys", "--workdir=ghdl_work"]

sim = SimRunner("ghdl", languages=["vhdl"])
top = sim.tb_top
generics = parameter_args(sim.tb_parameters, "-g{name}={value}")

if not os.path.isdir("ghdl_work"):
    os.makedirs("ghdl_work")

sim.run("compile", ["ghdl", "-i"] + OPTIONS + sim.files("vhdl"), log="ghdl_import")
sim.run("elaborate", ["ghdl", "-m"] + OPTIONS + [top], log="ghdl_make")
# The generics of the top are run options: with the GCC and LLVM backends,
# "-m" has already built the simulation.
# The VHDL testbench Odatix generates leaves its waves to the simulator.
waves = ["--vcd=" + sim.waves] if sim.waves else []
sim.run("simulate", ["ghdl", "-r"] + OPTIONS + [top] + generics + waves, log="ghdl_run")
sim.finish()
