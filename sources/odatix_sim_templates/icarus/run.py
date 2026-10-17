"""
Simulation template: Icarus Verilog.

Run by Odatix in the job's work directory, as "python run.py <odatix_path>".
What it runs is read from "odatix_sim.yml" (see odatix.sim.runner).

Icarus supports only part of SystemVerilog: a testbench using classes or
other verification constructs is better run with another simulator.
"""

import os
import sys

# Odatix runs this script with its own Python and says where it is installed.
if len(sys.argv) > 1:
    sys.path.insert(0, os.path.dirname(os.path.realpath(sys.argv[1])))

from odatix.sim.runner import SimRunner

sim = SimRunner("icarus", languages=["verilog", "sv"])
top = sim.tb_top

command = ["iverilog", "-g2012", "-o", "odatix_sim.vvp", "-s", top]
command += ["-I" + directory for directory in sim.include_dirs]
command += ["-P" + top + "." + name + "=" + value for name, value in sim.tb_parameters.items()]
command += sim.files("verilog", "sv")

# iverilog compiles and elaborates at once.
sim.run("compile", command, log="iverilog")
sim.run("simulate", ["vvp", "-n", "odatix_sim.vvp"], log="vvp")
sim.finish()
