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
Running EDA tools and simulators of the Windows Subsystem for Linux, from
Odatix on Windows.

What runs in WSL is the command of a job: the tool or the simulator. Odatix
itself (preparing the jobs, the session, the monitor, exporting the results)
always runs on Windows, and so does what a job does before and after that
command (generating its RTL, marking it done).

Where each tool and each simulator runs is said when a run is checked, and the
workspace chooses it (see odatix.yml):

  - "wsl_tools": run in WSL, whatever else is installed;
  - "windows_tools": run on Windows, never in WSL;
  - otherwise, with "wsl: auto" (the default), Odatix picks: an EDA tool runs in
    WSL when its tool.yml has no "windows" section (only Linux commands), a
    simulator when it is not installed on Windows but is in WSL;
  - "wsl: never": nothing runs in WSL.

An EDA tool runs in WSL with the commands of the "unix" section of its tool.yml,
a simulation with the commands of its tasks for Linux. They are given the paths
of the job as WSL sees them (/mnt/c/...), and run in a login shell of the
distribution ("wsl_distribution", the default one when empty), so that they
find the tools its profile puts in the PATH. Nothing changes anywhere but on
Windows.
"""

import base64
import collections
import re
import shutil
import subprocess
import sys

MODE_AUTO = "auto"
MODE_NEVER = "never"
MODES = (MODE_AUTO, MODE_NEVER)

#: The WSL settings of a workspace (see read_settings)
WslSettings = collections.namedtuple("WslSettings", ["mode", "distribution", "tools", "windows_tools"])
DEFAULTS = WslSettings(MODE_AUTO, "", [], [])

#: Where WSL mounts the drives of Windows, unless /etc/wsl.conf says otherwise
DEFAULT_MOUNT_ROOT = "/mnt/"

#: The Python a helper script of a tool runs with in WSL ($python, ${python})
PYTHON = "python3"

#: What a simulation template run in WSL needs from the Python of the distribution
SIMULATION_PYTHON_CHECK = "import yaml"

_WINDOWS_PATH = re.compile(r"^([A-Za-z]):(?:[\\/]|$)")
# \\wsl$\<distribution>\... and \\wsl.localhost\<distribution>\...: a path of
# the Linux file system itself
_WSL_SHARE_PATH = re.compile(r"^[\\/]{2}wsl(?:\$|\.localhost)[\\/][^\\/]+(.*)$", re.IGNORECASE)
_PROGRAM = re.compile(r"^[\w.+-]+$")

# What WSL was asked once, per distribution
_mount_roots = {}
_distribution_names = {}
_programs = {}
_python_problems = {}


######################################
# Settings
######################################

def settings():
  """The WSL settings of the workspace (see odatix.yml), a WslSettings."""
  from odatix.lib.settings import OdatixSettings

  value = getattr(OdatixSettings, "wsl_settings", None)
  return WslSettings(*value) if value else DEFAULTS


def _names(value):
  if isinstance(value, str):
    value = value.replace(",", " ").split()
  if not isinstance(value, (list, tuple)):
    return []
  return [str(name).strip() for name in value if str(name).strip()]


def read_settings(settings_data):
  """
  The WSL settings of a workspace settings file, as `settings` returns them. A
  value Odatix does not understand falls back to the default.
  """
  data = settings_data if isinstance(settings_data, dict) else {}
  mode = str(data.get("wsl") or MODE_AUTO).strip().lower()
  if mode not in MODES:
    mode = MODE_AUTO
  distribution = str(data.get("wsl_distribution") or "").strip()
  return WslSettings(mode, distribution, _names(data.get("wsl_tools")), _names(data.get("windows_tools")))


def is_windows():
  return sys.platform == "win32"


def is_installed():
  """Whether WSL can be started from here."""
  return is_windows() and shutil.which("wsl") is not None


######################################
# Where each tool runs
######################################

def _chosen(names):
  """
  Where the workspace says to run something known by any of `names`: True for
  WSL, False for Windows, None when it leaves it to Odatix. Never WSL anywhere
  but on Windows.
  """
  if not is_windows():
    return False
  current = settings()
  if current.mode == MODE_NEVER:
    return False
  if any(name in current.windows_tools for name in names):
    return False
  if any(name in current.tools for name in names):
    return True
  return None


def runs_in_wsl(tool, tool_settings=None):
  """
  Whether an EDA tool runs in WSL, with the commands of the "unix" section of
  its tool.yml (`tool_settings`, read when not given).
  """
  chosen = _chosen([tool])
  if chosen is False:
    return False
  if tool_settings is None:
    import odatix.lib.eda_tools as eda_tools

    tool_settings = eda_tools.load_tool_settings(tool)
  if not isinstance(tool_settings, dict) or "unix" not in tool_settings:
    return False
  if chosen:
    return True
  return "windows" not in tool_settings and is_installed()


def simulation_runs_in_wsl(names, program):
  """
  Whether a simulation runs in WSL. `names` are the simulation and the
  templates it starts from (a workspace names either in its settings), and
  `program` what its "test_command" runs: left to Odatix, a simulation runs in
  WSL when its simulator is not installed on Windows but is in WSL.
  """
  chosen = _chosen(names)
  if chosen is not None:
    return chosen
  if not program or shutil.which(program) is not None or not is_installed():
    return False
  return which(program) is not None


######################################
# What WSL says
######################################

def _ask(shell_command, timeout=60):
  """What a shell command run in WSL prints, or None when it fails."""
  try:
    result = subprocess.run(
      command(shell_command), shell=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=timeout,
    )
  except (OSError, subprocess.SubprocessError):
    return None
  if result.returncode != 0:
    return None
  return result.stdout.decode("utf-8", "replace").strip()


def which(program):
  """Where a program is in the PATH of WSL (that of a login shell), or None."""
  key = (settings().distribution, program)
  if key not in _programs:
    found = _ask("command -v " + program) if _PROGRAM.match(str(program)) else None
    _programs[key] = found.splitlines()[-1] if found else None
  return _programs[key]


def python_problem():
  """
  What keeps the Python of WSL from running a simulation template ("python3"
  with PyYAML), or None when nothing does.
  """
  distribution = settings().distribution
  if distribution not in _python_problems:
    if which(PYTHON) is None:
      problem = PYTHON + " is not installed in WSL"
    elif _ask(PYTHON + ' -c "' + SIMULATION_PYTHON_CHECK + '"') is None:
      problem = "the " + PYTHON + " of WSL cannot import PyYAML"
    else:
      problem = None
    _python_problems[distribution] = problem
  return _python_problems[distribution]


def distribution_name():
  """The name of the distribution the tools run in, as `wsl -l` says it."""
  configured = settings().distribution
  if configured:
    return configured
  if configured not in _distribution_names:
    _distribution_names[configured] = _ask("echo $WSL_DISTRO_NAME") or "default distribution"
  return _distribution_names[configured]


def location(in_wsl):
  """Where something runs, as Odatix says it: "in WSL (Ubuntu)" or "on Windows"."""
  return "in WSL (" + distribution_name() + ")" if in_wsl else "on Windows"


######################################
# Paths
######################################

def mount_root():
  """Where WSL mounts the drives of Windows ("/mnt/"), asked once to WSL itself."""
  distribution = settings().distribution
  if distribution not in _mount_roots:
    root = DEFAULT_MOUNT_ROOT
    try:
      output = subprocess.run(
        _wsl_prefix() + ["-e", "wslpath", "-u", "C:\\"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30,
      ).stdout.decode("utf-8", "replace").strip()
      # "/mnt/c/" -> "/mnt/"
      if output.lower().endswith("/c/") or output.lower().endswith("/c"):
        root = output.rstrip("/")[:-1]
    except (OSError, subprocess.SubprocessError):
      pass
    _mount_roots[distribution] = root
  return _mount_roots[distribution]


def linux_path(path):
  """
  A path of Windows as WSL sees it ("C:\\work\\job" -> "/mnt/c/work/job"). A
  path that is not one of Windows (relative, or already of Linux) is left as it
  is.
  """
  if not path:
    return path
  path = str(path)
  share = _WSL_SHARE_PATH.match(path)
  if share:
    return share.group(1).replace("\\", "/") or "/"
  drive = _WINDOWS_PATH.match(path)
  if not drive:
    return path
  rest = path[2:].replace("\\", "/").lstrip("/")
  return mount_root() + drive.group(1).lower() + ("/" + rest if rest else "")


######################################
# Commands
######################################

def _wsl_prefix():
  distribution = settings().distribution
  # wsl.exe reads its own command line: a quoted distribution name is not found
  return ["wsl.exe"] + (["-d", distribution] if distribution else [])


def command(shell_command):
  """
  The command line of Windows running a shell command of Linux in WSL.

  The command goes through cmd.exe, then wsl.exe, then bash: it is handed over
  encoded in base64, which none of them changes, and decoded by bash, so that
  its quotes, "$" and "|" reach bash as they are written. It runs in the
  directory of Windows it is started from, in a login shell (the PATH of the
  user's profile).
  """
  encoded = base64.b64encode(str(shell_command).encode("utf-8")).decode("ascii")
  return " ".join(_wsl_prefix()) + ' -e bash -lc "c=$(echo ' + encoded + ' | base64 -d); eval \\"$c\\""'
