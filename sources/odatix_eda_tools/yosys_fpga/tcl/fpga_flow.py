"""
Open source FPGA synthesis, placement and routing of an Odatix job: Yosys
synthesizes the design for a Lattice ECP5 or iCE40, nextpnr places and routes
it and reports the frequency the routed design reaches.

    python fpga_flow.py fmax   [options]   maximum frequency
    python fpga_flow.py custom [options]   at the frequency of frequency.txt
    python fpga_flow.py --version          the versions of the tools

Run in the work directory of a job: it reads the design and the target from
settings.yml, writes the logs to log/, the reports to report/ and the netlist
to result/. Only Python and the tools are needed (no make, no tclsh, no POSIX
shell), so it runs the same on Linux, macOS and Windows, with the OSS CAD Suite
for instance.

The target names the part as <family>-<device>-<package>[-<speed>]:

    ecp5-25k-CABGA381-6     nextpnr-ecp5 --25k --package CABGA381 --speed 6
    ice40-hx8k-CT256        nextpnr-ice40 --hx8k --package ct256

The I/Os are left unconstrained: nextpnr places them itself, as Vivado does
out of context. The package must still have enough pins for the ports of the
design.

nextpnr times the routed design and says which frequency it reaches, whatever
the constraint was: an fmax search is a few runs, not a binary search. Its
placer and router work for the frequency they are asked, so each run after the
first asks for what the one before reached, and the best reached is the
maximum frequency.
"""

import argparse
import json
import math
import os
import re
import shlex
import shutil
import subprocess
import sys

LOG_DIR = "log"
REPORT_DIR = "report"
RESULT_DIR = "result"

# What Odatix reads to tell a job finished and found a frequency (see
# odatix.lib.hard_settings)
DONE = "Done: 100%"
FMAX_STATUS = os.path.join(LOG_DIR, "status.log")
SYNTH_STATUS = os.path.join(LOG_DIR, "synth_status.log")
FREQUENCY_SEARCH = os.path.join(LOG_DIR, "frequency_search.log")
FMAX_FOUND = "Highest frequency with timing constraints being met: {} MHz"

FAMILIES = {
  "ecp5": {
    "synth": "synth_ecp5",
    "nextpnr": "nextpnr-ecp5",
    # What nextpnr reports the use of, under the names of the other FPGA tools
    # of Odatix (see the metrics.yml of vivado). A slice holds two LUT4 and two
    # flip-flops; nextpnr counts its halves.
    "resources": {
      "LUT": ["TRELLIS_COMB"],
      "Reg": ["TRELLIS_FF"],
      "BRAM": ["DP16KD"],
      "DSP": ["MULT18X18D"],
      "IO": ["TRELLIS_IO"],
    },
    "speed": "6",
  },
  "ice40": {
    "synth": "synth_ice40",
    "nextpnr": "nextpnr-ice40",
    # An iCE40 logic cell is one LUT4 and one flip-flop: the LUT and register
    # counts come from the synthesized netlist, the cells from nextpnr.
    "resources": {
      "LC": ["ICESTORM_LC"],
      "BRAM": ["ICESTORM_RAM"],
      "DSP": ["ICESTORM_DSP"],
      "IO": ["SB_IO"],
    },
  },
}

# Cells of the synthesized netlist counted as LUTs and as registers: a carry
# cell of the ECP5 holds two LUT4.
NETLIST_LUTS = {"LUT4": 1, "CCU2C": 2, "SB_LUT4": 1}
NETLIST_REGS = re.compile(r"^(TRELLIS_FF|SB_DFF\w*)$")


class FlowError(Exception):
  pass


######################################
# Job
######################################

def read_settings():
  """The settings Odatix wrote for the job (settings.yml), as a dict."""
  try:
    import yaml
  except ImportError:
    raise FlowError("PyYAML is missing: run this script with the Python of Odatix")
  with open("settings.yml", encoding="utf-8") as f:
    return yaml.safe_load(f) or {}


def parse_target(target):
  """The family, the device, the package and the speed grade a target names."""
  parts = str(target).split("-")
  family = parts[0].lower()
  if family not in FAMILIES or len(parts) < 3:
    raise FlowError(
      'target "' + str(target) + '" is not <family>-<device>-<package>[-<speed>] '
      "with a family among " + ", ".join(sorted(FAMILIES))
    )
  device, package = parts[1].lower(), parts[2]
  speed = parts[3] if len(parts) > 3 else FAMILIES[family].get("speed")
  if family == "ice40":
    package = package.lower()
  return family, device, package, speed


def design_sources(top=""):
  """
  The sources of the design by language, in compilation order (see
  odatix.sim.design_info): a filelist.f of rtl/ when the design has one, an
  order computed from the sources otherwise. A testbench kept next to the RTL
  is left out: Yosys would stop on it.
  """
  try:
    from odatix.sim.design_info import collect_sources, without_benches
  except ImportError:
    # Run from a source tree: odatix is next to odatix_eda_tools
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from odatix.sim.design_info import collect_sources, without_benches
  return without_benches(collect_sources("."), top, ".")


def tcl_quote(path):
  return '"' + path.replace("\\", "/") + '"'


######################################
# Tools
######################################

def program(name):
  path = shutil.which(name)
  if path is None:
    raise FlowError(name + " is not in the PATH (or in the tool_install_path of target_yosys_fpga.yml)")
  return path


def run(args, log_path):
  """Run a command, writing what it says to the console and to a log."""
  print("$ " + " ".join(shlex.quote(arg) for arg in args))
  sys.stdout.flush()
  with open(log_path, "wb") as log:
    process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    for line in iter(process.stdout.readline, b""):
      log.write(line)
      sys.stdout.write(line.decode("utf-8", "replace"))
      sys.stdout.flush()
    return process.wait()


def report_progress(path, progress, comment=""):
  with open(path, "w", encoding="utf-8") as f:
    if progress >= 100:
      f.write(DONE + (" " + comment if comment else "") + "\n")
    else:
      f.write("In progress: " + str(int(progress)) + "% " + comment + "\n")


######################################
# Synthesis
######################################

def vhdl_to_verilog(sources, top):
  """
  The VHDL of the design, elaborated by GHDL into a Verilog netlist that Yosys
  reads (result/vhdl_design.v). The ghdl binary does it alone: the GHDL plugin
  of Yosys has to be built against the very Yosys it is loaded in, which some
  builds of the OSS CAD Suite get wrong.
  """
  output = os.path.join(RESULT_DIR, "vhdl_design.v")
  workdir = "ghdl_work"
  if not os.path.isdir(workdir):
    os.makedirs(workdir)
  args = [program("ghdl"), "--synth", "--std=08", "-fsynopsys", "--workdir=" + workdir, "--out=verilog"] + sources + ["-e", top]
  print("$ " + " ".join(shlex.quote(arg) for arg in args) + " > " + output)
  sys.stdout.flush()
  with open(output, "wb") as out, open(os.path.join(LOG_DIR, "ghdl.log"), "wb") as log:
    status = subprocess.call(args, stdout=out, stderr=log)
  if status != 0:
    with open(os.path.join(LOG_DIR, "ghdl.log"), encoding="utf-8", errors="replace") as log:
      sys.stdout.write(log.read())
    raise FlowError("GHDL failed (see " + LOG_DIR + "/ghdl.log)")
  return output


def synthesize(settings, family, options):
  """
  Synthesize the design for the family with Yosys: result/netlist.json for
  nextpnr, result/netlist.v for whoever wants to read it, and the statistics
  of the netlist in report/synth_stat.json.
  """
  top = str(settings["top_level_module"])
  sources = design_sources(top)
  includes = " ".join("-I" + tcl_quote(d) for d in sources.get("include_dirs", []))
  commands = []
  for language, flag in (("verilog", ""), ("sv", " -sv")):
    if sources.get(language):
      commands.append("read_verilog" + flag + " -defer " + includes + " " + " ".join(tcl_quote(p) for p in sources[language]))
  if sources.get("vhdl"):
    commands.append("read_verilog " + tcl_quote(vhdl_to_verilog(sources["vhdl"], top)))
  if not commands:
    raise FlowError("no Verilog, SystemVerilog or VHDL source in rtl/")
  commands += [
    FAMILIES[family]["synth"] + " -top " + top + " " + " ".join(options),
    "tee -q -o " + REPORT_DIR + "/synth_stat.json stat -json",
    "tee -q -o " + REPORT_DIR + "/synth_stat.rep stat",
    "write_json " + RESULT_DIR + "/netlist.json",
    "write_verilog -noattr " + RESULT_DIR + "/netlist.v",
  ]
  with open(os.path.join("scripts", "yosys_synth.ys"), "w", encoding="utf-8") as f:
    f.write("\n".join(commands) + "\n")
  status = run([program("yosys"), "-l", os.path.join(LOG_DIR, "yosys.log"), "-q", "-s", os.path.join("scripts", "yosys_synth.ys")],
               os.path.join(LOG_DIR, "yosys_console.log"))
  if status != 0:
    raise FlowError("Yosys failed (see " + LOG_DIR + "/yosys.log)")


def netlist_counts(top):
  """The LUTs and the registers of the synthesized netlist."""
  with open(os.path.join(REPORT_DIR, "synth_stat.json"), encoding="utf-8") as f:
    stat = json.load(f)
  modules = stat.get("modules", {})
  cells = (stat.get("design") or modules.get("\\" + top) or {}).get("num_cells_by_type", {})
  luts = sum(count * NETLIST_LUTS.get(cell.lstrip("\\"), 0) for cell, count in cells.items())
  regs = sum(count for cell, count in cells.items() if NETLIST_REGS.match(cell.lstrip("\\")))
  return luts, regs


######################################
# Placement and routing
######################################

def place_and_route(target, frequency, seed, options, tag):
  """
  Place and route result/netlist.json at a frequency (MHz). Returns the
  report nextpnr writes, or None when it failed.
  """
  family, device, package, speed = target
  report = os.path.join(REPORT_DIR, "nextpnr_" + tag + ".json")
  args = [program(FAMILIES[family]["nextpnr"]), "--" + device, "--package", package]
  if family == "ecp5" and speed:
    args += ["--speed", speed]
  if family == "ice40":
    args.append("--pcf-allow-unconstrained")
  args += [
    "--json", os.path.join(RESULT_DIR, "netlist.json"),
    "--freq", "%g" % frequency,
    "--seed", str(seed),
    "--report", report,
    "--detailed-timing-report",
    # A design missing the frequency asked is a result, not a failure: nextpnr
    # still says what it reaches
    "--timing-allow-fail",
  ] + options
  status = run(args, os.path.join(LOG_DIR, "nextpnr_" + tag + ".log"))
  if status != 0 or not os.path.isfile(report):
    return None
  with open(report, encoding="utf-8") as f:
    return json.load(f)


def reached(report):
  """
  The frequency the routed design reaches (MHz): that of its slowest clock.
  None when nothing is clocked, or nothing timed.
  """
  frequencies = [clock.get("achieved") for clock in (report or {}).get("fmax", {}).values()]
  frequencies = [f for f in frequencies if isinstance(f, (int, float)) and f > 0]
  return min(frequencies) if frequencies else None


def write_metrics(settings, family, report, frequency):
  """
  report/metrics.json: the use of the resources of the part (count and
  percentage), the frequency reached and the worst slack at the frequency the
  design was routed for.
  """
  metrics = {}
  utilization = report.get("utilization", {})
  for name, bels in FAMILIES[family]["resources"].items():
    used = sum(utilization.get(bel, {}).get("used", 0) for bel in bels)
    available = sum(utilization.get(bel, {}).get("available", 0) for bel in bels)
    metrics[name + "_count"] = used
    if available:
      metrics[name + "_percent"] = round(100.0 * used / available, 4)
  if family == "ice40":
    metrics["LUT_count"], metrics["Reg_count"] = netlist_counts(str(settings["top_level_module"]))
  achieved = reached(report)
  if achieved is not None:
    metrics["Achieved_frequency"] = round(achieved, 3)
    # The period asked for, less the critical path of the routed design (ns)
    metrics["Worst_Slack"] = round(1000.0 / frequency - 1000.0 / achieved, 4)
  with open(os.path.join(REPORT_DIR, "metrics.json"), "w", encoding="utf-8") as f:
    json.dump(metrics, f, indent=2, sort_keys=True)
    f.write("\n")
  return metrics


def print_summary(metrics):
  print("")
  for name in sorted(metrics):
    print("  " + name + ": " + str(metrics[name]))
  print("")


######################################
# Jobs
######################################

def fmax(settings, target, args):
  """
  Maximum frequency: route at the lower bound of the search, then at what the
  previous run reached, and keep the best routed design.
  """
  lower = float(settings.get("fmax_lower_bound") or 10)
  upper = float(settings.get("fmax_upper_bound") or 1000)
  passes = max(1, int(args.passes))
  with open(FREQUENCY_SEARCH, "w", encoding="utf-8") as f:
    f.write("nextpnr search in [{}:{}] MHz, {} pass(es)\n\n".format(int(lower), int(upper), passes))
  report_progress(FMAX_STATUS, 0, "(synthesis)")
  synthesize(settings, target[0], args.synth_options)

  best = None
  frequency = lower
  for index in range(1, passes + 1):
    report_progress(FMAX_STATUS, 100.0 * index / (passes + 1), "({}/{})".format(index, passes))
    report = place_and_route(target, frequency, args.seed, args.nextpnr_options, str(index))
    achieved = reached(report)
    with open(FREQUENCY_SEARCH, "a", encoding="utf-8") as f:
      f.write("{:g} MHz: {}\n".format(frequency, "FAILED" if report is None else
                                       "no clock" if achieved is None else "reached {:.2f} MHz".format(achieved)))
    if achieved is None:
      break
    if best is None or achieved > best[0]:
      best = (achieved, frequency, report, index)
    next_frequency = min(max(achieved, lower), upper)
    if abs(next_frequency - frequency) < 1:
      break
    frequency = next_frequency

  if best is None:
    if report is None:
      raise FlowError("nextpnr could not place and route the design (see the nextpnr log: "
                      "a design with more I/Os than the part has pins fails this way)")
    raise FlowError("nextpnr reached no frequency: the design has no register-to-register path "
                    "timed by its clock signal (is the clock signal right? are the inputs or "
                    "outputs only connected to registers through logic?)")
  achieved, _, report, index = best
  if achieved > upper:
    # As the binary search of the other tools: an Fmax above the bounds of the
    # search is not measured, and the upper bound is not an Fmax
    with open(FREQUENCY_SEARCH, "a", encoding="utf-8") as f:
      f.write("\nNo timing violated! Try raising the upper bound ({:g} MHz)\n".format(upper))
    raise FlowError("No timing violated! Try raising the upper bound ({:g} MHz): the design reached "
                    "{:.2f} MHz (\"upper_bound\" of \"fmax_synthesis\" in the architecture settings, "
                    "or --to)".format(upper, achieved))
  # The reports and the log of the best run are the job's
  shutil.copyfile(os.path.join(REPORT_DIR, "nextpnr_" + str(index) + ".json"), os.path.join(REPORT_DIR, "nextpnr.json"))
  shutil.copyfile(os.path.join(LOG_DIR, "nextpnr_" + str(index) + ".log"), os.path.join(LOG_DIR, "nextpnr.log"))
  found = int(math.floor(achieved))
  # The slack is that of the frequency found, as for the other tools
  metrics = write_metrics(settings, target[0], report, found)
  with open(FREQUENCY_SEARCH, "a", encoding="utf-8") as f:
    f.write("\n" + FMAX_FOUND.format(found) + "\n")
  with open(os.path.join(REPORT_DIR, "frequency.rep"), "w", encoding="utf-8") as f:
    f.write("Target frequency:         {}\n".format(found))
  print(FMAX_FOUND.format(found))
  print_summary(metrics)
  report_progress(FMAX_STATUS, 100, "({}/{})".format(passes, passes))
  report_progress(SYNTH_STATUS, 100)


def custom(settings, target, args):
  """Synthesis, placement and routing at the frequency of the job."""
  frequency = float(settings.get("target_frequency") or 0)
  if frequency <= 0:
    with open("frequency.txt", encoding="utf-8") as f:
      frequency = float(re.search(r"([0-9.]+)", f.read()).group(1))
  report_progress(SYNTH_STATUS, 5)
  synthesize(settings, target[0], args.synth_options)
  report_progress(SYNTH_STATUS, 40)
  report = place_and_route(target, frequency, args.seed, args.nextpnr_options, "custom")
  if report is None:
    raise FlowError("nextpnr failed (see " + LOG_DIR + "/nextpnr_custom.log)")
  shutil.copyfile(os.path.join(REPORT_DIR, "nextpnr_custom.json"), os.path.join(REPORT_DIR, "nextpnr.json"))
  metrics = write_metrics(settings, target[0], report, frequency)
  print_summary(metrics)
  report_progress(SYNTH_STATUS, 100)


def versions():
  """
  The versions of Yosys and of the nextpnr found. The tool is installed with
  Yosys and the nextpnr of one family at least: a build of nextpnr for the
  ECP5 alone is enough to synthesize for the ECP5.
  """
  found = {}
  for name in ["yosys"] + sorted(set(family["nextpnr"] for family in FAMILIES.values())):
    path = shutil.which(name)
    if path is None:
      print(name + ": not in the PATH")
      continue
    sys.stdout.flush()
    found[name] = subprocess.call([path, "-V" if name == "yosys" else "--version"]) == 0
  nextpnr = [ok for name, ok in found.items() if name != "yosys"]
  return 0 if found.get("yosys") and any(nextpnr) else 1


def main(argv):
  if argv[1:] == ["--version"]:
    return versions()
  parser = argparse.ArgumentParser(prog="fpga_flow.py")
  parser.add_argument("job", choices=["fmax", "custom"])
  parser.add_argument("--seed", default="1")
  parser.add_argument("--passes", default="2", help="placement and routing runs of an fmax search")
  # Given as --synth-options="-abc9 -dff": a value starting with "-" is not an
  # option of its own that way
  parser.add_argument("--synth-options", default="", type=shlex.split)
  parser.add_argument("--nextpnr-options", default="", type=shlex.split)
  args = parser.parse_args(argv[1:])

  for directory in (LOG_DIR, REPORT_DIR, RESULT_DIR):
    if not os.path.isdir(directory):
      os.makedirs(directory)
  try:
    settings = read_settings()
    target = parse_target(settings.get("target") or open("target.txt", encoding="utf-8").read().strip())
    if args.job == "fmax":
      fmax(settings, target, args)
    else:
      custom(settings, target, args)
  except FlowError as e:
    print("error: " + str(e))
    return 1
  return 0


if __name__ == "__main__":
  sys.exit(main(sys.argv))
