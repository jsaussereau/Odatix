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

import dash
from dash import dcc, html
from dash.dependencies import Input, Output

import sys
from datetime import datetime
import platform
import traceback

import odatix.components.motd

def generate_error_div(e):
  error_traceback = traceback.format_exc()
  command_line = ' '.join(sys.argv)
  current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
  system_info = {
    "OS": platform.system(),
    "OS Version": platform.version(),
    "Python Version": platform.python_version(),
    "Machine": platform.machine(),
  }

  return html.Div(className="error", children=[
    html.Div("Internal error: " + str(e)),
    html.Div("Please, report this error with the error log bellow"),
    html.Details([
      html.Summary("Error details"),
      html.Pre(
        [
          html.Div("System Information:"),
          *[html.Div("  " + key + ": " + value + "\n") for key, value in system_info.items()],
          html.Div("\nOdatix Version: " + str(odatix.components.motd.read_version())),
          html.Div("\nCommand: " + command_line),
          html.Div("\n" + error_traceback),
        ]
      )
  ])
])
