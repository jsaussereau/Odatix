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

class colors:
  GREY = "\033[90m"
  RED = "\033[91m"
  GREEN = "\033[92m"
  YELLOW = "\033[93m"
  BLUE = "\033[94m"
  MAGENTA = "\033[95m"
  CYAN = "\033[96m"
  ENDC = "\033[0m"
  BOLD = "\033[1m"
  BLINK = "\033[5m"
  UNDERLINE = "\033[4m"

def say(message="", script_name="", color=colors.ENDC, end="\n"):
  if script_name != "":
    script_name = colors.GREY + "[" + script_name + "]" + colors.ENDC + " "
  print(script_name + color + message + colors.ENDC, end=end)

def error(message, script_name="", end="\n"):
  if script_name != "":
    script_name = colors.GREY + "[" + script_name + "]" + colors.ENDC + " "
  print(script_name + colors.BOLD + colors.RED + "error" + colors.ENDC + colors.RED + ": " + message + colors.ENDC, end=end)

def internal_error(message, script_name="", end="\n"):
  if script_name != "":
    script_name = colors.GREY + "[" + script_name + "]" + colors.ENDC + " "
  print(script_name + colors.BOLD + colors.RED + "internal error" + colors.ENDC + colors.RED + ": " + message + colors.ENDC, end=end)

def warning(message, script_name="", end="\n"):
  if script_name != "":
    script_name = colors.GREY + "[" + script_name + "]" + colors.ENDC + " "
  print(script_name + colors.YELLOW + "warning: " + message + colors.ENDC, end=end)

def note(message, script_name="", end="\n"):
  if script_name != "":
    script_name = colors.GREY + "[" + script_name + "]" + colors.ENDC + " "
  print(script_name + colors.CYAN + "note: " + message + colors.ENDC, end=end)

def header(message):
  print(colors.BOLD + colors.CYAN + message + colors.ENDC)

def subheader(message):
  print(colors.CYAN + message + colors.ENDC)

def bold(message, color=colors.ENDC, end="\n"):
  print(color + colors.BOLD + message + colors.ENDC, end=end)

def grey(message, script_name="", end="\n"):
  say(message=message, script_name=script_name, color=colors.GREY, end=end)

def red(message, script_name="", end="\n"):
  say(message=message, script_name=script_name, color=colors.RED, end=end)

def green(message, script_name="", end="\n"):
  say(message=message, script_name=script_name, color=colors.GREEN, end=end)

def yellow(message, script_name="", end="\n"):
  say(message=message, script_name=script_name, color=colors.YELLOW, end=end)

def blue(message, script_name="", end="\n"):
  say(message=message, script_name=script_name, color=colors.BLUE, end=end)

def magenta(message, script_name="", end="\n"):
  say(message=message, script_name=script_name, color=colors.MAGENTA, end=end)

def cyan(message, script_name="", end="\n"):
  say(message=message, script_name=script_name, color=colors.CYAN, end=end)

def color(color=colors.ENDC):
  print(color, end="")

def endc(message="", script_name="", end=""):
  say(message=message, script_name=script_name, color=colors.ENDC, end=end)