"""
RTL analysis with a linter, without make nor a POSIX shell: what the "analyze"
target of the makefile of icarus and verilator does, for Windows, and how
yosys analyzes a design on every system.

    python rtl_analysis.py <icarus|verilator|yosys> [--version]

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
  "icarus": ["iverilog"],
  "verilator": ["verilator", "verilator_bin"],
  "yosys": ["yosys"],
}

# Highest exit code meaning that the linter went through the design
FINISHED = {
  "icarus": 125,
  "verilator": 1,
  "yosys": 1,
}

# What each linter is asked to print its version with
VERSION = {
  "icarus": "-V",
  "verilator": "--version",
  "yosys": "-V",
}

# The sources yosys reads besides the top level file: it has no library search
# of its own for SystemVerilog ("-y rtl" of the others), so it is given every
# one, elaborated only if the design uses it ("-defer").
VERILOG_EXTENSIONS = (".v", ".sv")


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
  return sources


def yosys_script(top_level_module, top_level_file):
  """
  What yosys runs: it reads the design, elaborates it from its top level
  ("hierarchy -check" says what is missing), turns its processes into logic and
  checks the result (undriven signals, multiple drivers, logic loops).
  """
  sources = " ".join('"' + path + '"' for path in rtl_sources(top_level_file))
  return "; ".join([
    "read_verilog -sv -defer -Irtl " + sources,
    "hierarchy -check -top " + top_level_module,
    "proc",
    "check",
  ])


def command(tool, top_level_module, top_level_file):
  # "/" whatever the system: a finding is located the way the log names it
  source = "rtl/" + top_level_file
  if tool == "yosys":
    return ["-q", "-p", yosys_script(top_level_module, top_level_file)]
  if tool == "icarus":
    return ["-g2012", "-Wall", "-t", "null", "-I", "rtl", "-y", "rtl", "-Y", ".sv", "-Y", ".svh",
            "-s", top_level_module, source]
  return ["--lint-only", "-Wall", "-Wno-fatal", "-Irtl", "-y", "rtl", "--top-module", top_level_module, source]


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
  args = [path] + command(tool, setting("top_level_module"), setting("top_level_file"))
  if not os.path.isdir(LOG_DIR):
    os.makedirs(LOG_DIR)
  process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=environment(path))
  with open(os.path.join(LOG_DIR, "analysis.log"), "wb") as log:
    for line in iter(process.stdout.readline, b""):
      log.write(line)
      sys.stdout.write(line.decode("utf-8", "replace"))
      sys.stdout.flush()
  status = process.wait()
  if status <= FINISHED[tool]:
    with open(os.path.join(LOG_DIR, "synth_status.log"), "w", encoding="utf-8") as f:
      f.write("Done: 100%\n")
  return status


if __name__ == "__main__":
  sys.exit(main(sys.argv))
