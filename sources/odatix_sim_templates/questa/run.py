"""
Simulation template: Questa / ModelSim.

Run by Odatix in the job's work directory, as "python run.py <odatix_path>".
What it runs is read from "odatix_sim.yml" (see odatix.sim.runner).

The design is compiled first, then the testbench, each language with its own
compiler, in the order Odatix computed. Should that order be wrong, the files
are compiled one by one until they all compile.
"""

import os
import shutil
import sys

# Odatix runs this script with its own Python and says where it is installed.
if len(sys.argv) > 1:
    sys.path.insert(0, os.path.dirname(os.path.realpath(sys.argv[1])))

from odatix.sim.runner import SimRunner, parameter_args

LIBRARY = "work"

sim = SimRunner("questa", languages=["vhdl", "verilog", "sv"])
top = sim.tb_top
incdirs = ["+incdir+" + directory for directory in sim.include_dirs]

if os.path.isdir(LIBRARY):
    shutil.rmtree(LIBRARY)
sim.run("compile", ["vlib", LIBRARY], log="vlib")

compilers = {
    "vhdl": lambda files: ["vcom", "-2008", "-work", LIBRARY] + files,
    "verilog": lambda files: ["vlog", "-work", LIBRARY] + incdirs + files,
    "sv": lambda files: ["vlog", "-sv", "-work", LIBRARY] + incdirs + files,
}
for part in ("design", "testbench"):
    for language in ("vhdl", "verilog", "sv"):
        files = sim.files(language, design=(part == "design"), testbench=(part == "testbench"))
        sim.compile(files, compilers[language], log=part + "_" + language)

# vsim elaborates, then runs the script: what it prints in between tells the
# elaboration time from the simulation time.
script = "echo odatix_elaborated; "
if sim.waves and "vhdl" in sim.tb_languages:
    # A SystemVerilog testbench dumps its waves itself ($dumpvars), a VHDL one
    # leaves it to the simulator.
    script += "vcd file " + sim.waves + "; vcd add -r /" + top + "/dut/*; "
script += "run -all; quit -f"
sim.run(
    "simulate",
    ["vsim", "-c", "-onfinish", "stop", "-work", LIBRARY]
    # "$dumpvars" needs the signals to be kept.
    + (["-voptargs=+acc"] if sim.waves else [])
    + parameter_args(sim.tb_parameters, "-G{name}={value}")
    + [LIBRARY + "." + top, "-do", script],
    log="vsim",
    elaborated_mark="odatix_elaborated",
)
sim.finish()
