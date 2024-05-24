#**********************************************************************#
#                               Asterism                               #
#**********************************************************************#
#
# Copyright (C) 2022 Jonathan Saussereau
#
# This file is part of Asterism.
# Asterism is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# Asterism is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with Asterism. If not, see <https://www.gnu.org/licenses/>.
#

class colors:
  GREY = '\033[90m'
  RED = '\033[91m'
  GREEN = '\033[92m'
  YELLOW = '\033[93m'
  BLUE = '\033[94m'
  MAGENTA = '\033[95m'
  CYAN = '\033[96m'
  ENDC = '\033[0m'
  BOLD = '\033[1m'
  UNDERLINE = '\033[4m'

def error(message, script_name=""):
  if script_name != "":
    script_name = colors.GREY + "[" + script_name + "] "
  print(script_name + colors.BOLD + colors.RED + "error" +  colors.RED + ": " + message)

def warning(message, script_name=""):
  if script_name != "":
    script_name = colors.GREY + "[" + script_name + "] "
  print(script_name + colors.YELLOW + "warning: " + message)

def note(message, script_name=""):
  if script_name != "":
    script_name = colors.GREY + "[" + script_name + "] "
  print(script_name + colors.CYAN + "note: " + message)
