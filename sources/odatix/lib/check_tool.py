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

import os
import re
import time
import subprocess
import tempfile
import threading

import odatix.lib.printc as printc
from odatix.lib.utils import *

script_name = os.path.basename(__file__)


######################################
# Why a check failed
######################################

#: What a test command says about a tool: it starts, it is not there, it starts
#: but gets no license, or it fails for another reason.
INSTALLED = "installed"
NOT_INSTALLED = "not_installed"
NO_LICENSE = "no_license"
FAILED = "failed"

# A line about licenses that also says something went wrong. Both are needed:
# the banner of a tool speaks of licenses too ("a written license agreement",
# "Licensed Products") without anything being wrong.
_LICENSE_WORD = re.compile(r"licen[cs](e|ing)|flex(lm|net)|lmgrd|snpslmd", re.IGNORECASE)
_FAILURE_WORD = re.compile(
  r"\b(unable|cannot|can't|can not|could not|couldn't|failed|failure|not available|unavailable|"
  r"denied|expired|not found|no such feature|must exist|invalid|not valid|error|fatal|refused|"
  r"down|not responding|exceeded|reached)\b",
  re.IGNORECASE,
)
# Synopsys says "Design Compiler is not enabled. (DCSH-1)" without the word
_NOT_ENABLED = re.compile(r"\b(is|are) not enabled\b", re.IGNORECASE)
# The shell found no such program (127 on posix and in WSL, 9009 in cmd.exe)
_NOT_FOUND_CODES = (127, 9009)
_NOT_FOUND = re.compile(
  r"command not found|no such file or directory|is not recognized as an internal or external command",
  re.IGNORECASE,
)


def _lines(text):
  # A tool of Windows ends its lines with "\r\n"
  return [line.strip() for line in (text or "").replace("\r\n", "\n").splitlines() if line.strip()]


def _cap(line):
  return line[:300] + "…" if len(line) > 300 else line


def classify_failure(returncode, stderr, stdout=""):
  """
  Why a test command failed, from its exit code and what it wrote:
  (NOT_INSTALLED | NO_LICENSE | FAILED, the line saying so).

  A license failure is looked for on both outputs: Synopsys tools write it on
  stdout, with nothing on stderr. Otherwise the reason is the last line of
  stderr, else of stdout, else the exit code.
  """
  err_lines, out_lines = _lines(stderr), _lines(stdout)
  for line in err_lines + out_lines:
    if _NOT_ENABLED.search(line) or (_LICENSE_WORD.search(line) and _FAILURE_WORD.search(line)):
      return NO_LICENSE, _cap(line)
  last = err_lines or out_lines
  reason = _cap(last[-1]) if last else "exit code {0}".format(returncode)
  if returncode in _NOT_FOUND_CODES:
    return NOT_INSTALLED, reason
  for line in err_lines + out_lines:
    if _NOT_FOUND.search(line):
      return NOT_INSTALLED, _cap(line)
  return FAILED, reason


class ToolCheck:
  """
  An eda tool check that runs in the background.

  The test command is launched as soon as the object is created, so the caller
  can keep reading and checking its settings while the tool starts up, and only
  call wait() right before it needs the outcome (typically just before the
  "continue?" prompt).

  Nothing is printed when the tool launches fine and quickly: only a failure is
  reported (followed by sys.exit(-1)). If the tool is still starting up after
  QUIET_DELAY seconds, the usual "checking .." line and its result are printed
  after all, so the user knows what is being waited for.

  In debug mode the test command output goes to the terminal, so the check is
  not backgrounded: it is run entirely inside wait(), to keep the output in
  order with whatever the caller prints meanwhile.

  wait() is the terminal interface (print on failure, then sys.exit). Callers
  that must not die, like the GUI, use running()/result() instead and report
  the outcome themselves.
  """

  # How long the check may run before it announces itself (seconds)
  QUIET_DELAY = 2

  def __init__(self, tool, command, supported_tools, tool_install_path, debug=False, script_name=script_name):
    self.tool = tool
    self.command = command
    self.supported_tools = supported_tools
    self.tool_install_path = tool_install_path
    self.debug = debug
    #: Who reports a failure: the command (or "run" for the Python API) that
    #: asked for the check, rather than this module.
    self.script_name = script_name
    self.done = False
    self.process = None
    self._result = None
    # stderr goes to a temporary file, not to a pipe: nobody reads the check
    # while it runs, and a tool writing more than the pipe buffer would block
    # there until the end of the check (and never finish).
    self.stderr_file = None
    self.stdout_file = None
    #: (NOT_INSTALLED | NO_LICENSE | FAILED, reason) once the check failed
    self._failure = None
    if not debug and recently_passed(command):
      # Passed a moment ago in this process (the GUI checks every tool it
      # lists): launching the tool again would only make the user wait.
      self._result = (True, "")
      self.done = True
      return
    if not debug:
      self.process = self._start()

  def _start(self):
    self.stderr_file = tempfile.TemporaryFile()
    # stdout is kept too: some tools (Synopsys) say there that they got no license
    self.stdout_file = tempfile.TemporaryFile()
    return subprocess.Popen(
      self.command,
      stdout=self.stdout_file,
      stderr=self.stderr_file,
      shell=True,
    )

  def running(self):
    """True while the test command is still running (never blocks)."""
    return self.process is not None and self.process.poll() is None

  def result(self):
    """
    Wait for the check and return (ok, error_message), without printing
    anything and without exiting: for callers that report failures their own
    way (the GUI shows them in the run popup).
    """
    if self._result is None:
      if self.process is None:
        self.process = self._start()
      self.process.wait()
      # A tool of Windows ends its lines with "\r\n"
      error_message = self._read_output("stderr_file").replace("\r\n", "\n").strip()
      output = self._read_output("stdout_file")
      ok = self.process.returncode == 0
      if ok:
        remember_passed(self.command)
      else:
        self._failure = classify_failure(self.process.returncode, error_message, output)
        # The line saying there is no license, or what explains the failure
        # when the tool wrote nothing on stderr
        if self._failure[0] == NO_LICENSE or not error_message:
          error_message = self._failure[1]
      self._result = (ok, error_message)
    return self._result

  def _read_output(self, attribute):
    stream = getattr(self, attribute)
    if stream is None:
      return ""
    stream.seek(0)
    text = stream.read().decode("utf-8", errors="replace")
    stream.close()
    setattr(self, attribute, None)
    return text

  def failure(self):
    """(NOT_INSTALLED | NO_LICENSE | FAILED, reason) of a failed check, else None."""
    self.result()
    return self._failure

  def failure_message(self):
    """One-line reason of a failed check, ready to be shown to the user."""
    _ok, error_message = self.result()
    failure = self._failure
    if failure is not None and failure[0] == NO_LICENSE:
      return 'Could not launch eda tool "' + self.tool + '", it got no license: ' + failure[1]
    message = 'Could not launch eda tool "' + self.tool + '"'
    if error_message:
      # A tool can be very verbose on stderr: keep the last line, capped, so the
      # popup shows a reason and not a wall of output.
      message += ": " + _cap(error_message.splitlines()[-1].strip())
    return message

  def cancel(self):
    """
    Stop a check whose outcome is no longer needed (a run with nothing to run
    does not wait for the tool to start up), without reporting anything.
    """
    self.done = True
    if self.process is not None and self.process.poll() is None:
      try:
        self.process.kill()
        self.process.wait()
      except OSError:
        pass
    for attribute in ("stderr_file", "stdout_file"):
      if getattr(self, attribute) is not None:
        getattr(self, attribute).close()
        setattr(self, attribute, None)

  def wait(self):
    if self.done:
      return
    self.done = True

    if self.process is None:
      _check_tool_blocking(self.tool, self.command, self.supported_tools, self.tool_install_path, self.debug, self.script_name)
      return

    # Stay silent while the check is quick; only announce it if the tool takes
    # long enough that the user would otherwise wait without knowing why.
    announced = False
    deadline = time.time() + self.QUIET_DELAY
    while self.process.poll() is None:
      if not announced and time.time() >= deadline:
        print('checking the selected eda tool "' + self.tool + '" ..', end="")
        sys.stdout.flush()
        announced = True
      elif announced:
        print(".", end="", flush=True)
      time.sleep(0.2 if not announced else 0.5)

    ok, error_message = self.result()

    if ok:
      if announced:
        printc.green(" success!")
        print()
      return

    if announced:
      printc.red(" failed!")
    failure = self._failure
    _print_check_failure(
      self.tool, self.supported_tools, error_message, self.debug, self.script_name,
      kind=failure[0] if failure else None,
    )


def start_tool_check(tool, command, supported_tools, tool_install_path, debug=False, script_name=script_name):
  """
  Start an eda tool check in the background and return the ToolCheck handle.
  Call handle.wait() when the outcome is needed.
  """
  return ToolCheck(tool, command, supported_tools, tool_install_path, debug=debug, script_name=script_name)


def _print_check_failure(tool, supported_tools, error_message, debug, script_name=script_name, kind=None):
  if kind == NO_LICENSE:
    printc.error('Could not launch eda tool "' + tool + '": it starts but gets no license', script_name)
  else:
    printc.error('Could not launch eda tool "' + tool + '"', script_name)
  if error_message:
    printc.cyan("error details: ", script_name, end="")
    # The message of the tool ends the line: what follows starts on its own.
    printc.red(error_message)
  if not debug:
    printc.note("Use '-D' option for more details", script_name)
  if kind == NO_LICENSE:
    # Installed and found: the PATH hints below would send the user astray
    printc.note(
      "Check that the license server is reachable and that the license variable of the tool "
      "(SNPSLMD_LICENSE_FILE, LM_LICENSE_FILE, ...) is set where Odatix runs",
      script_name,
    )
    sys.exit(-1)
  # A tool whose check explains itself (a "note:" of its own, such as Quartus
  # naming the directory it needs) knows better than the generic hint, which
  # would then only repeat it, less precisely.
  if "note:" not in (error_message or ""):
    printc.note("Did you add the directory of the tool's executables to your PATH environment variable?", script_name)
    if os.name == "nt":
      printc.note('Example (PowerShell) -> $env:PATH = "<installation directory of ' + tool + '>\\bin;$env:PATH"', script_name)
    else:
      printc.note("Example -> export PATH=$PATH:<installation directory of " + tool + ">/bin", script_name)
    printc.note(
      'or set tool_install_path in odatix_userconfig/targets/target_' + tool + '.yml',
      script_name,
    )
  if tool not in supported_tools:
    printc.note(
      'The selected eda tool "{}" is not one of the supported tool. '.format(tool)
      + "Check out Odatix's documentation to add support for your own eda tool",
      script_name,
    )
  sys.exit(-1)


def check_tool(tool, command, supported_tools, tool_install_path, debug=False, script_name=script_name):
  """Blocking eda tool check. See ToolCheck for the background variant."""
  _check_tool_blocking(tool, command, supported_tools, tool_install_path, debug, script_name)


def _check_tool_blocking(tool, command, supported_tools, tool_install_path, debug=False, script_name=script_name):
  if debug:
    print('checking the selected eda tool "' + tool + '":')
    printc.bold(' > ' + command)
    if not debug:
      print('..', end="")
  else:
    print('checking the selected eda tool "' + tool + '" ..', end="")
  sys.stdout.flush()
  test_process = subprocess.Popen(
    command,
    stdout=None if debug else subprocess.DEVNULL,
    stderr=None if debug else subprocess.DEVNULL,
    shell=True,
  )
  while test_process.poll() is None:
    if not debug:
      print(".", end="", flush=True)
    time.sleep(0.5)
  if test_process.returncode == 0:
    printc.green(" success!")
    remember_passed(command)
  else:
    printc.red(" failed!")
    error_message = ""
    if test_process.stderr is not None:
      error_message = test_process.stderr.read()
      error_message = error_message.decode("utf-8", errors="replace")
    _print_check_failure(tool, supported_tools, error_message, debug, script_name)
  print()


######################################
# Checks already done
######################################

#: How long a passed check is trusted without launching the tool again
#: (seconds). Long enough for a GUI user going from the list of tools to the
#: run popup, short enough to notice a tool that went away.
PASSED_CHECK_TTL = 600

#: When each test command last passed in this process, by command.
_passed_checks = {}


def remember_passed(command):
  """Note that a test command has just passed."""
  if command:
    _passed_checks[command] = time.time()


def recently_passed(command):
  """Whether a test command passed less than PASSED_CHECK_TTL seconds ago."""
  passed = _passed_checks.get(command)
  return passed is not None and time.time() - passed < PASSED_CHECK_TTL


def forget_passed_checks():
  """Forget every check done (for tests, or after changing the environment)."""
  _passed_checks.clear()
  _failed_probes.clear()


#: How long a failed probe is trusted (seconds): a page shown again right
#: after does not launch a tool that just failed, a fix is seen soon enough.
FAILED_PROBE_TTL = 60

#: When each probed test command last failed in this process, and why.
_failed_probes = {}

#: One lock per probed command: two pages asking at once launch the tool once.
_probe_locks = {}
_probe_locks_guard = threading.Lock()


def probe(command, timeout=90):
  """
  Launch a test command and say whether the tool starts, without printing
  anything: (True, "") or (False, why: see classify_failure). For the pages
  listing the tools; a run checks with ToolCheck. probe_status tells why a
  tool does not start.

  A check that passed recently is not launched again, nor one that failed a
  moment ago. A tool still starting after `timeout` seconds is stopped, with
  all it spawned, and reported as (None, reason): nothing is known about it.
  """
  status, reason = probe_status(command, timeout)
  return (None if status is None else status == INSTALLED), reason


def probe_status(command, timeout=90):
  """
  Like probe, with the status of the tool instead of a boolean: (INSTALLED,
  "") or (NOT_INSTALLED | NO_LICENSE | FAILED, reason), (None, reason) when
  nothing is known.
  """
  if not command:
    return None, "the tool declares no tool_test_command"
  with _probe_locks_guard:
    lock = _probe_locks.setdefault(command, threading.Lock())
  with lock:
    if recently_passed(command):
      return INSTALLED, ""
    failed = _failed_probes.get(command)
    if failed is not None and time.time() - failed[0] < FAILED_PROBE_TTL:
      return failed[1], failed[2]
    status, reason = _run_probe(command, timeout)
    if status not in (INSTALLED, None):
      _failed_probes[command] = (time.time(), status, reason)
    else:
      _failed_probes.pop(command, None)
    return status, reason


def _run_probe(command, timeout):
  stderr_file = tempfile.TemporaryFile()
  # stdout is kept too: some tools (Synopsys) say there that they got no license
  stdout_file = tempfile.TemporaryFile()
  try:
    kwargs = {"start_new_session": True} if os.name == "posix" else {}
    process = subprocess.Popen(
      command,
      stdin=subprocess.DEVNULL,
      stdout=stdout_file,
      stderr=stderr_file,
      shell=True,
      **kwargs
    )
    try:
      process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
      try:
        if os.name == "posix":
          import signal
          os.killpg(process.pid, signal.SIGKILL)
        else:
          process.kill()
      except OSError:
        pass
      process.wait()
      return None, "still starting after {0} s".format(timeout)
    stderr_file.seek(0)
    stdout_file.seek(0)
    stderr = stderr_file.read().decode("utf-8", errors="replace")
    stdout = stdout_file.read().decode("utf-8", errors="replace")
  finally:
    stderr_file.close()
    stdout_file.close()
  if process.returncode == 0:
    remember_passed(command)
    return INSTALLED, ""
  return classify_failure(process.returncode, stderr, stdout)
