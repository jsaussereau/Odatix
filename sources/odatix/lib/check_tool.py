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
import copy
import time
import subprocess

import odatix.lib.printc as printc
from odatix.lib.utils import *

script_name = os.path.basename(__file__)


def check_tool(tool, script_path, makefile, rule, supported_tools):
  print('checking the selected eda tool "' + tool + '" ..', end="")
  sys.stdout.flush()
  tool_makefile_file = script_path + "/" + tool + "/" + makefile
  test_process = subprocess.Popen(
    ["make", "-f", tool_makefile_file, rule, "--no-print-directory"], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
  )
  while test_process.poll() is None:
    print(".", end="", flush=True)
    time.sleep(0.5)
  if test_process.returncode == 0:
    printc.green(" success!")
  else:
    printc.red(" failed!")
    error_message = test_process.stderr.read().decode()
    printc.error('Could not launch eda tool "' + tool + '"', script_name)
    printc.cyan("error details: ", script_name, end="")
    printc.red(error_message, end="")
    printc.note("Did you add the tool path to your PATH environment variable?", script_name)
    printc.note("Example -> PATH=$PATH:/opt/xilinx/2022/Vivado/2022.2/bin", script_name)
    if tool not in supported_tools:
      printc.note(
        'The selected eda tool "{}" is not one of the supported tool. '.format(tool)
        + "Check out Odatix's documentation to add support for your own eda tool",
        script_name,
      )
      printc.note('Make sure there is a valid rule "' + rule + '" in "' + tool_makefile_file + '"', script_name)
    sys.exit(-1)
  print()
