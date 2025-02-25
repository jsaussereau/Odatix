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

import odatix.lib.printc as printc
from odatix.lib.utils import *

script_name = os.path.basename(__file__)

def check_tool(tool, command, supported_tools, tool_install_path, debug=False):
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
  else:
    printc.red(" failed!")
    error_message = ""
    if test_process.stderr is not None:
      error_message = test_process.stderr.read()
      error_message = error_message.decode("utf-8", errors="replace")
    printc.error('Could not launch eda tool "' + tool + '"', script_name)
    if error_message:
      printc.cyan("error details: ", script_name, end="")
      printc.red(error_message, end="")
    if not debug:
      printc.note("Use '-D' option for more details", script_name)
    printc.note("Did you add the tool path to your PATH environment variable?", script_name)
    printc.note("Example -> PATH=$PATH:/tools/xilinx/Vivado/2024.2/bin", script_name)
    printc.note("or correctly defined your tool_install_path, for tools needing it to be defined?", script_name)
    if tool not in supported_tools:
      printc.note(
        'The selected eda tool "{}" is not one of the supported tool. '.format(tool)
        + "Check out Odatix's documentation to add support for your own eda tool",
        script_name,
      )
      # printc.note('Make sure there is a valid rule "' + rule + '" in "' + tool_makefile_file + '"', script_name)
    sys.exit(-1)
  print()
