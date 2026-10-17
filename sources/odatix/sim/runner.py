# ********************************************************************** #
#                                Odatix                                  #
# ********************************************************************** #
#
# Copyright (C) 2022 Jonathan Saussereau
#
# This file is part of Odatix.
# Odatix is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Odatix is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Odatix. If not, see <https://www.gnu.org/licenses/>.
#

"""
What the script of a simulation template is written with.

A template's "run.py" says which commands compile, elaborate and run the
design with its simulator. Everything else is here, the same for every
simulator:

  - what to run, read from "odatix_sim.yml" (see odatix.sim.design_info);
  - the progress, written to "log/progress.log" in the usual format;
  - one log per command in "log/", next to what it printed;
  - the errors and warnings the commands print, counted;
  - the time spent compiling, elaborating and simulating;
  - the cycles simulated, when the testbench prints them as
    "odatix_cycles: <n>", and the cycles per second;
  - "sim_report.yml", which the template's "_metrics.yml" reads.

    sim = SimRunner("ghdl", languages=["vhdl"])
    sim.run("compile", ["ghdl", "-i", "--std=08"] + sim.files("vhdl"))
    sim.run("elaborate", ["ghdl", "-m", "--std=08", sim.tb_top])
    sim.run("simulate", ["ghdl", "-r", "--std=08", sim.tb_top])
    sim.finish()

A command exiting with an error code stops the simulation, which is then
failed; so does an error message in what the simulation printed.
"""

import os
import re
import subprocess
import sys
import time

import yaml

import odatix.sim.design_info as design_info

REPORT_FILENAME = "sim_report.yml"
LOG_DIR = "log"
PROGRESS_FILENAME = os.path.join(LOG_DIR, "progress.log")

STAGES = ("compile", "elaborate", "simulate")
# Progress reached at the end of each stage.
STAGE_PROGRESS = {"compile": 40, "elaborate": 60, "simulate": 99}

# What a line reporting an error or a warning looks like, for most simulators.
DEFAULT_ERRORS = (
  r"^\s*#?\s*\*\*\s*(Error|Fatal)\b",  # Questa, "# " in its transcript
  r"^\s*%(Error|Fatal)\b",              # Verilator
  r"^\s*(ERROR|FATAL|Error|Fatal)\s*:",  # xsim, Icarus, $error/$fatal
  r":\s*error\s*:",                     # GHDL, compilers
  r"\((assertion|report) (error|failure)\)",  # GHDL assertions
)
DEFAULT_WARNINGS = (
  r"^\s*#?\s*\*\*\s*Warning\b",
  r"^\s*%Warning\b",
  r"^\s*(WARNING|Warning)\s*:",
  r":\s*warning\s*:",
  r"\((assertion|report) warning\)",
)
CYCLES_PATTERN = re.compile(r"odatix_cycles\s*[:=]\s*([0-9]+)")


class SimulationFailed(Exception):
  pass


class SimRunner(object):
  """
  Args:
    simulator (str): name of the simulator, as reported.
    languages (list): the languages the simulator compiles. A design or a
      testbench written in another one is refused before anything runs.
    errors, warnings (list): regular expressions telling an error line or a
      warning line in what the commands print. The defaults fit most
      simulators.
  """

  def __init__(self, simulator, languages=None, errors=DEFAULT_ERRORS, warnings=DEFAULT_WARNINGS, work_dir="."):
    self.simulator = simulator
    self.work_dir = work_dir
    self.info = design_info.read_info(work_dir)
    self._errors = [re.compile(pattern) for pattern in errors]
    self._warnings = [re.compile(pattern) for pattern in warnings]
    self._start = time.time()
    self._log_count = {}
    self.last_elapsed = 0.0
    self.report = {
      "simulator": simulator,
      "status": "running",
      "message": "",
      "errors": 0,
      "warnings": 0,
      "compile_time": 0.0,
      "elaboration_time": 0.0,
      "simulation_time": 0.0,
      "total_time": 0.0,
      "cycles": None,
      "cycles_per_second": None,
    }
    _makedirs(os.path.join(work_dir, LOG_DIR))
    for name in (REPORT_FILENAME,):
      path = os.path.join(work_dir, name)
      if os.path.isfile(path):
        os.remove(path)
    self.progress(1)
    if not self.info:
      self.fail('"' + design_info.SIM_INFO_FILENAME + '" is missing: this script is run by Odatix, as a simulation')
    if languages is not None:
      self.check_languages(languages)

  ######################################
  # What to run
  ######################################

  @property
  def dut_top(self):
    return str(self.info.get("dut", {}).get("top", ""))

  @property
  def tb_top(self):
    top = str(self.info.get("testbench", {}).get("top", ""))
    if not top:
      self.fail(
        "No testbench: the simulation gives none, the architecture neither, "
        "and its top could not be found in the files given"
      )
    return top

  @property
  def tb_parameters(self):
    """{name: value} the testbench top is given (its "parameters")."""
    parameters = self.info.get("testbench", {}).get("parameters") or {}
    return {str(name): str(value) for name, value in parameters.items()}

  @property
  def include_dirs(self):
    return list(self.info.get("sources", {}).get("include_dirs", []))

  def files(self, *languages, **kwargs):
    """
    The design's files of these languages, then the testbench's, each in
    compilation order. testbench=False leaves the testbench out, design=False
    the design.
    """
    with_design = kwargs.get("design", True)
    with_testbench = kwargs.get("testbench", True)
    languages = languages or design_info.LANGUAGES
    files = []
    if with_design:
      for language in languages:
        files.extend(self.info.get("sources", {}).get(language, []))
    if with_testbench:
      files.extend(
        path for path in self.info.get("testbench", {}).get("files", [])
        if design_info.language_of(path) in languages
      )
    return files

  def languages(self):
    """Languages of the design and of its testbench."""
    languages = list(self.info.get("dut", {}).get("languages", []))
    for language in self.info.get("testbench", {}).get("languages", []):
      if language not in languages:
        languages.append(language)
    return languages

  def check_languages(self, accepted):
    refused = [language for language in self.languages() if language not in accepted]
    if refused:
      self.fail(
        self.simulator + " cannot compile " + ", ".join(refused)
        + " (it compiles " + ", ".join(accepted) + ")"
      )

  ######################################
  # Running
  ######################################

  def progress(self, percent):
    try:
      with open(os.path.join(self.work_dir, PROGRESS_FILENAME), "w") as f:
        f.write("progress: " + str(int(percent)) + "%\n")
    except (IOError, OSError):
      pass

  def run(self, stage, command, log=None, env=None, check=True, record=True, elaborated_mark=None):
    """
    Run one command of a stage ("compile", "elaborate" or "simulate"), from the
    work directory, printing what it prints and keeping it in "log/<log>.log".

    Args:
      check (bool): stop the simulation when the command fails.
      record (bool): count its errors, warnings and time in the report.
      elaborated_mark (str): for a simulator elaborating and simulating in one
        command, what it prints once elaborated: the time until then is
        elaboration time, the rest simulation time.

    Returns:
      (returncode, output)
    """
    if stage not in STAGES:
      raise ValueError("unknown stage: " + str(stage))
    command = [str(part) for part in command]
    log_path = self._log_path(log or stage)
    print("> " + " ".join(_quote(part) for part in command))
    sys.stdout.flush()

    start = time.time()
    lines = []
    full_env = dict(os.environ)
    if env:
      full_env.update({str(key): str(value) for key, value in env.items()})
    try:
      process = subprocess.Popen(
        command, cwd=self.work_dir, env=full_env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, errors="replace",
      )
    except OSError as e:
      self.fail('cannot run "' + command[0] + '": ' + str(e))
    elaborated = None
    with open(log_path, "w") as log_file:
      for line in process.stdout:
        if elaborated is None and elaborated_mark and elaborated_mark in line:
          elaborated = time.time() - start
        sys.stdout.write(line)
        log_file.write(line)
        lines.append(line)
      sys.stdout.flush()
      returncode = process.wait()
    elapsed = time.time() - start
    self.last_elapsed = elapsed
    output = "".join(lines)

    if record:
      if elaborated is not None:
        self.record("elaborate", "", elaborated)
        elapsed -= elaborated
      self.record(stage, output, elapsed)
    if check and returncode != 0:
      self.fail(stage + " failed (" + command[0] + " exited with code " + str(returncode) + "), see " + log_path)
    if stage in STAGE_PROGRESS:
      self.progress(STAGE_PROGRESS[stage])
    return returncode, output

  def record(self, stage, output, elapsed=0.0):
    """Count the errors, warnings, cycles and time of what a stage printed."""
    errors, warnings = self.count(output)
    self.report["errors"] += errors
    self.report["warnings"] += warnings
    key = {"compile": "compile_time", "elaborate": "elaboration_time", "simulate": "simulation_time"}[stage]
    self.report[key] = round(self.report[key] + elapsed, 3)
    if stage == "simulate":
      cycles = CYCLES_PATTERN.findall(output)
      if cycles:
        self.report["cycles"] = int(cycles[-1])

  def count(self, output):
    errors = warnings = 0
    for line in output.splitlines():
      if any(pattern.search(line) for pattern in self._errors):
        errors += 1
      elif any(pattern.search(line) for pattern in self._warnings):
        warnings += 1
    return errors, warnings

  def compile(self, files, command, log="compile"):
    """
    Compile `files` with `command(files)`: all of them at once, in the order
    Odatix computed, and when that fails, one by one, again and again, as long
    as one more file compiles each time. The last resort for an order Odatix
    got wrong; a file that never compiles fails the simulation.
    """
    if not files:
      return
    returncode, output = self.run("compile", command(files), log=log, check=False, record=False)
    if returncode == 0:
      self.record("compile", output, self.last_elapsed)
      return
    if len(files) == 1:
      self.record("compile", output, self.last_elapsed)
      self.fail("compile failed, see " + self._log_path(log, new=False))

    print("Compiling all at once failed: compiling the files one by one until they all compile")
    elapsed = self.last_elapsed
    remaining = list(files)
    outputs = {}
    while remaining:
      failed = []
      for path in remaining:
        returncode, outputs[path] = self.run("compile", command([path]), log=log, check=False, record=False)
        elapsed += self.last_elapsed
        if returncode != 0:
          failed.append(path)
      if len(failed) == len(remaining):
        for path in failed:
          self.record("compile", outputs[path])
        self.record("compile", "", elapsed)
        self.fail("compile failed for " + ", ".join(failed) + ", see the logs in " + LOG_DIR)
      remaining = failed
    # What the files printed when they compiled: the errors of the attempts
    # made in the wrong order are not the design's.
    for path in files:
      self.record("compile", outputs.get(path, ""))
    self.record("compile", "", elapsed)

  ######################################
  # Outcome
  ######################################

  def fail(self, message):
    """Stop: the simulation failed."""
    self.report["status"] = "failed"
    self.report["message"] = str(message)
    print("Error: " + str(message))
    self._write_report()
    sys.exit(1)

  def finish(self):
    """
    End the simulation: passed when nothing printed an error. Exits with the
    outcome.
    """
    if self.report["errors"] > 0:
      self.report["status"] = "failed"
      self.report["message"] = str(self.report["errors"]) + " error(s), see the logs in " + LOG_DIR
    else:
      self.report["status"] = "passed"
    self._write_report()
    self.progress(100)
    print("Simulation " + self.report["status"])
    sys.exit(0 if self.report["status"] == "passed" else 1)

  def _write_report(self):
    self.report["total_time"] = round(time.time() - self._start, 3)
    cycles = self.report.get("cycles")
    if cycles and self.report["simulation_time"] > 0:
      self.report["cycles_per_second"] = round(cycles / self.report["simulation_time"], 1)
    with open(os.path.join(self.work_dir, REPORT_FILENAME), "w") as f:
      yaml.dump(self.report, f, default_flow_style=False, sort_keys=False)

  def _log_path(self, name, new=True):
    """log/<name>.log, numbered from the second command of the same name on."""
    count = self._log_count.get(name, 0)
    if new:
      count += 1
      self._log_count[name] = count
    suffix = "" if count <= 1 else "_" + str(count)
    return os.path.join(LOG_DIR, name + suffix + ".log")


def _makedirs(path):
  if not os.path.isdir(path):
    os.makedirs(path)


def _quote(part):
  return '"' + part + '"' if (" " in part or part == "") else part


def parameter_args(parameters, form):
  """
  The arguments giving the testbench top its parameters: `form` is formatted
  with {name} and {value}, e.g. "-g{name}={value}".
  """
  return [form.format(name=name, value=value) for name, value in parameters.items()]
