"""
Simulation template: Vivado simulator (xsim).

Run by Odatix in the job's work directory, as "python run.py <odatix_path>".
What it runs is read from "odatix_sim.yml" (see odatix.sim.runner).

The design is compiled first, then the testbench, each language with its own
compiler, in the order Odatix computed. Should that order be wrong, the files
are compiled one by one until they all compile.
"""

import os
import sys

# Odatix runs this script with its own Python and says where it is installed.
if len(sys.argv) > 1:
    sys.path.insert(0, os.path.dirname(os.path.realpath(sys.argv[1])))

from odatix.sim.runner import SimRunner

LIBRARY = "work"
SNAPSHOT = "odatix_sim"

sim = SimRunner("xsim", languages=["vhdl", "verilog", "sv"])
top = sim.tb_top
incdirs = []
for directory in sim.include_dirs:
    incdirs += ["-i", directory]

compilers = {
    "vhdl": lambda files: ["xvhdl", "--2008", "-work", LIBRARY] + files,
    "verilog": lambda files: ["xvlog", "-work", LIBRARY] + incdirs + files,
    "sv": lambda files: ["xvlog", "-sv", "-work", LIBRARY] + incdirs + files,
}
for part in ("design", "testbench"):
    for language in ("vhdl", "verilog", "sv"):
        files = sim.files(language, design=(part == "design"), testbench=(part == "testbench"))
        sim.compile(files, compilers[language], log=part + "_" + language)

generics = []
for name, value in sim.tb_parameters.items():
    generics += ["-generic_top", name + "=" + value]
sim.run(
    "elaborate",
    # A default timescale for the modules without one, which xelab refuses to
    # mix with modules that have one.
    ["xelab", "-L", LIBRARY, "-debug", "off", "--timescale", "1ns/1ps", "-s", SNAPSHOT]
    + generics + [LIBRARY + "." + top],
    log="xelab",
)
sim.run("simulate", ["xsim", SNAPSHOT, "-R"], log="xsim")
sim.finish()
