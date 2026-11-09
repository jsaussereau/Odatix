"""
RTL analysis with a linter, without make nor a POSIX shell: what the "analyze"
target of the makefile of icarus and verilator does, for Windows, and how
yosys, GHDL and Questa analyze a design on every system.

    python rtl_analysis.py <ghdl|icarus|questa|verilator|yosys> [--version]

Run in the work directory of a job: it reads the top level from
scripts/settings.tcl, writes what the linter says to log/analysis.log and marks
the analysis done in log/synth_status.log when the linter got to the end, even
if it reported errors in the design.
"""

import os
import re
import shutil
import subprocess
import sys

SCRIPT_DIR = "scripts"
LOG_DIR = "log"

# The programs of each linter, the first one found is run: Windows does not run
# the Perl front end of Verilator, only its binary.
PROGRAMS = {
  "ghdl": ["ghdl"],
  "icarus": ["iverilog"],
  "questa": ["vsim"],
  "verilator": ["verilator", "verilator_bin"],
  "yosys": ["yosys"],
}

# Highest exit code meaning that the linter went through the design
FINISHED = {
  "ghdl": 1,
  "icarus": 125,
  # vlog, vcom and vsim exit with 2 when they report errors in the design.
  "questa": 2,
  "verilator": 1,
  "yosys": 1,
}

# What each linter is asked to print its version with
VERSION = {
  "ghdl": "--version",
  "icarus": "-V",
  "questa": "-version",
  "verilator": "--version",
  "yosys": "-V",
}

# The sources yosys reads besides the top level file: it has no library search
# of its own for SystemVerilog ("-y rtl" of the others), so it is given every
# one, elaborated only if the design uses it ("-defer").
VERILOG_EXTENSIONS = (".v", ".sv")

# Where GHDL and Questa compile the design, in the work directory
GHDL_WORKDIR = "ghdl_work"
QUESTA_LIBRARY = "questa_work"

# The first line of a message of GHDL, and the number of lines below it showing
# where it is (the source line, then a caret)
GHDL_MESSAGE = (re.compile(rb"^\S+:\d+:\d+:"), 2)


def program(tool):
  for name in PROGRAMS[tool]:
    path = shutil.which(name)
    if path:
      return path
  sys.stderr.write(" or ".join(PROGRAMS[tool]) + " is not in the PATH\n")
  sys.exit(127)


def environment(path):
  """
  The environment to run a linter with. The Perl front end of Verilator tells
  its binary where its include files are: run alone, the binary needs
  VERILATOR_ROOT, found next to it in the usual layouts (OSS CAD Suite, MSYS2).
  """
  env = dict(os.environ)
  if "VERILATOR_ROOT" not in env and os.path.basename(path).lower().startswith("verilator"):
    prefix = os.path.dirname(os.path.dirname(os.path.abspath(path)))
    for root in (os.path.join(prefix, "share", "verilator"), prefix):
      if os.path.isdir(os.path.join(root, "include")):
        env["VERILATOR_ROOT"] = root
        break
  return env


def setting(name):
  with open(os.path.join(SCRIPT_DIR, "settings.tcl"), encoding="utf-8") as f:
    for line in f:
      match = re.match(r"\s*set\s+" + name + r"\s+(\S+)", line)
      if match:
        return match.group(1)
  sys.stderr.write("No \"" + name + "\" in " + os.path.join(SCRIPT_DIR, "settings.tcl") + "\n")
  sys.exit(2)


def rtl_sources(top_level_file):
  """Every Verilog and SystemVerilog source of rtl/, the top level file first."""
  sources = ["rtl/" + top_level_file]
  for directory, subdirs, files in os.walk("rtl"):
    subdirs.sort()
    for name in sorted(files):
      path = os.path.join(directory, name).replace(os.sep, "/")
      if name.lower().endswith(VERILOG_EXTENSIONS) and path not in sources:
        sources.append(path)
  # Less the testbenches kept next to the RTL
  benches = without_testbench_files(sources[1:])
  return sources[:1] + benches


def without_testbench_files(paths):
  """`paths` less those holding only testbenches (see design_info.without_benches)."""
  try:
    from odatix.sim.design_info import without_benches
  except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from odatix.sim.design_info import without_benches
  return without_benches({"sv": list(paths)}, "", ".")["sv"]


# A file declaring a SystemVerilog package: the library search of Icarus and
# Verilator ("-y rtl") finds modules by their file name, never a package, so
# these files are given to them explicitly, before the top level file.
PACKAGE_DECLARATION = re.compile(r"^\s*package\s+[A-Za-z_][A-Za-z0-9_]*\s*;", re.M)


def package_sources(top_level_file):
  """The sources of rtl/ (but the top level file) that declare a package."""
  found = []
  for path in rtl_sources(top_level_file)[1:]:
    try:
      with open(path, encoding="utf-8", errors="replace") as f:
        if PACKAGE_DECLARATION.search(f.read()):
          found.append(path)
    except OSError:
      pass
  return sorted(found)


def yosys_script(top_level_module, top_level_file, macros=()):
  """
  What yosys runs: it reads the design, elaborates it from its top level
  ("hierarchy -check" says what is missing), turns its processes into logic and
  checks the result (undriven signals, multiple drivers, logic loops).
  """
  sources = " ".join('"' + path + '"' for path in rtl_sources(top_level_file))
  return "; ".join([
    "read_verilog -sv -defer -Irtl " + "".join(macro + " " for macro in macros) + sources,
    "hierarchy -check -top " + top_level_module,
    "proc",
    "check",
  ])


def design_sources():
  """
  The sources of the design by language, in compilation order (see
  odatix.sim.design_info): the file list of the design when it has one
  ("filelist" in its settings, or filelist.f in rtl/), with its include
  directories and macros, an order computed from the sources otherwise. A
  testbench kept next to the RTL is left out: the design is what is analyzed.
  """
  try:
    from odatix.sim.design_info import job_sources, without_benches
  except ImportError:
    # Run from a source tree: odatix is next to odatix_eda_tools
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from odatix.sim.design_info import job_sources, without_benches
  return without_benches(job_sources("."), "", ".")


def ghdl_analysis(path, top_level_module, log):
  """
  GHDL finds the compilation order itself: the files are imported ("-i"), then
  "-m" analyzes and elaborates the design from its top level, and "--synth"
  turns it into logic, which reports latches and multiple drivers. Each step
  runs only if the one before went through: the next would only say again
  that the design is broken.
  """
  options = ["--std=08", "-fsynopsys", "--workdir=" + GHDL_WORKDIR]
  if not os.path.isdir(GHDL_WORKDIR):
    os.makedirs(GHDL_WORKDIR)
  # What "-i" says of the sources, "-m" says again: it is kept only when it
  # fails. "-m" itself says its warnings twice, once when it looks for what is
  # out of date and once when it analyzes it.
  status = run([path, "-i"] + options + design_sources()["vhdl"], log, quiet=True)
  if status == 0:
    status = run([path, "-m", "-Wall"] + options + [top_level_module], log, once=GHDL_MESSAGE)
  if status == 0:
    status = run([path, "--synth", "-Wall", "--out=none"] + options + [top_level_module], log)
  return status


def questa_analysis(path, top_level_module, log):
  """
  Questa (or ModelSim) compiles the sources in the order Odatix computes,
  Verilog first, then VHDL one file at a time so that every file is reported
  on, and elaborates the design from its top level once everything compiled.
  """
  bin_dir = os.path.dirname(path)
  sources = design_sources()
  status = run([os.path.join(bin_dir, "vlib"), QUESTA_LIBRARY], log, quiet=True)
  if status != 0:
    return status
  options = ["-lint", "-quiet", "-work", QUESTA_LIBRARY]
  incdirs = ["+incdir+" + directory for directory in sources["include_dirs"]]
  steps = []
  if sources["verilog"]:
    steps.append([os.path.join(bin_dir, "vlog")] + options + incdirs + sources["verilog"])
  if sources["sv"]:
    steps.append([os.path.join(bin_dir, "vlog"), "-sv"] + options + incdirs + sources["sv"])
  for source in sources["vhdl"]:
    steps.append([os.path.join(bin_dir, "vcom"), "-2008"] + options + [source])
  for args in steps:
    status = max(status, run(args, log))
  if status != 0:
    return status
  # vsim starts every line it prints in the console with "# ".
  return run([path, "-c", "-quiet", "-lib", QUESTA_LIBRARY, "-do", "quit -f", top_level_module], log, prefix="# ")


def filelist_command(tool, top_level_module, sources):
  """
  The command line of a linter given the file list of the design: its files in
  order, its include directories and its macros, and nothing found by search.
  """
  files = sources.get("verilog", []) + sources.get("sv", [])
  includes = sources.get("include_dirs", [])
  defines = sources.get("defines", [])
  if tool == "yosys":
    return ["-q", "-p", "; ".join([
      "read_verilog -sv -defer " + " ".join(["-I" + d for d in includes] + ['-D' + m for m in defines])
      + " " + " ".join('"' + path + '"' for path in files),
      "hierarchy -check -top " + top_level_module,
      "proc",
      "check",
    ])]
  if tool == "icarus":
    return (["-g2012", "-Wall", "-t", "null", "-s", top_level_module]
            + ["-I" + d for d in includes] + ["-D" + m for m in defines] + files)
  return (["--lint-only", "-Wall", "-Wno-fatal", "--top-module", top_level_module]
          + ["-I" + d for d in includes] + ["-D" + m for m in defines] + files)


def command(tool, top_level_module, top_level_file):
  # "/" whatever the system: a finding is located the way the log names it
  source = "rtl/" + top_level_file
  sources = design_sources()
  if sources.get("order") == "filelist":
    return filelist_command(tool, top_level_module, sources)
  macros = ["-D" + macro for macro in sources.get("defines", [])]
  if tool == "yosys":
    return ["-q", "-p", yosys_script(top_level_module, top_level_file, macros)]
  if tool == "icarus":
    return ["-g2012", "-Wall", "-t", "null", "-I", "rtl", "-y", "rtl", "-Y", ".sv", "-Y", ".svh",
            "-s", top_level_module] + macros + package_sources(top_level_file) + [source]
  return (["--lint-only", "-Wall", "-Wno-fatal", "-Irtl", "-y", "rtl", "--top-module", top_level_module]
          + macros + package_sources(top_level_file) + [source])


def run(args, log, quiet=False, prefix=None, once=None):
  """
  Run a command, writing what it says to the console and to the log, without
  `prefix` at the start of its lines. A quiet command is written only if it
  fails. With `once`, the pattern of the first line of a message and the
  number of lines below it, a message said again is left out.
  """
  process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=environment(args[0]))
  lines = []
  said = set()
  skipped = 0
  for line in iter(process.stdout.readline, b""):
    if prefix is not None and line.startswith(prefix.encode()):
      line = line[len(prefix):]
    if skipped:
      skipped -= 1
      continue
    if once is not None and once[0].search(line):
      if line in said:
        skipped = once[1]
        continue
      said.add(line)
    if quiet:
      lines.append(line)
    else:
      write(line, log)
  status = process.wait()
  if status != 0:
    for line in lines:
      write(line, log)
  return status


def write(line, log):
  log.write(line)
  sys.stdout.write(line.decode("utf-8", "replace"))
  sys.stdout.flush()


def main(argv):
  if len(argv) < 2 or argv[1] not in PROGRAMS:
    sys.stderr.write("usage: rtl_analysis.py <" + "|".join(sorted(PROGRAMS)) + "> [--version]\n")
    return 2
  tool = argv[1]
  if argv[2:] == ["--version"]:
    path = program(tool)
    return subprocess.call([path, VERSION[tool]], env=environment(path))

  print("Running " + tool + " analysis...")
  sys.stdout.flush()
  path = program(tool)
  top_level_module = setting("top_level_module")
  if not os.path.isdir(LOG_DIR):
    os.makedirs(LOG_DIR)
  with open(os.path.join(LOG_DIR, "analysis.log"), "wb") as log:
    if tool == "ghdl":
      status = ghdl_analysis(path, top_level_module, log)
    elif tool == "questa":
      status = questa_analysis(path, top_level_module, log)
    else:
      status = run([path] + command(tool, top_level_module, setting("top_level_file")), log)
  if status <= FINISHED[tool]:
    with open(os.path.join(LOG_DIR, "synth_status.log"), "w", encoding="utf-8") as f:
      f.write("Done: 100%\n")
  return status


if __name__ == "__main__":
  sys.exit(main(sys.argv))
