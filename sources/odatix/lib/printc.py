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

import contextlib
import os
import re
import sys

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
  BOLD_END = "\033[22m"
  BLINK = "\033[5m"
  UNDERLINE = "\033[4m"

_ANSI_ESCAPE = re.compile(r"\033\[[0-9;?]*[A-Za-z]")


class _PlainStream(object):
  """A text stream that drops the terminal color codes written to it."""

  def __init__(self, stream):
    self._stream = stream

  def write(self, text):
    return self._stream.write(_ANSI_ESCAPE.sub("", text) if isinstance(text, str) else text)

  def writelines(self, lines):
    for line in lines:
      self.write(line)

  def isatty(self):
    return False

  def __getattr__(self, name):
    return getattr(self._stream, name)


def wants_color(stream=None):
  """
  Whether `stream` (stdout by default) should receive color codes: only a
  terminal does, and not when the NO_COLOR environment variable is set
  (https://no-color.org).
  """
  stream = sys.stdout if stream is None else stream
  if os.environ.get("NO_COLOR", "") != "":
    return False
  isatty = getattr(stream, "isatty", None)
  try:
    return bool(isatty()) if callable(isatty) else False
  except Exception:
    return False


def plain_unless_terminal():
  """
  Drop the color codes from what goes to stdout and stderr when they are not a
  terminal (a pipe, a file) or when NO_COLOR is set.

  Meant for a command line process, called once before it prints anything:
  the colors are written in many places, and filtering the stream is the one
  place that catches them all. Nothing else (the GUI, the daemon) calls it.
  """
  for name in ("stdout", "stderr"):
    stream = getattr(sys, name, None)
    if stream is None or isinstance(stream, _PlainStream):
      continue
    if not wants_color(stream):
      setattr(sys, name, _PlainStream(stream))


# Sinks registered by collect(). They receive every diagnostic emitted here, so
# a caller (the GUI) can display errors and warnings as structured data instead
# of parsing the printed text back.
_sinks = []

def _emit(level, message, script_name=""):
  for sink in list(_sinks):
    try:
      sink(level, str(message), str(script_name))
    except Exception:
      # A broken sink must never take the run down with it.
      pass

@contextlib.contextmanager
def collect(sink):
  """
  Report every error/warning/note/tip emitted inside the context to `sink`,
  called as sink(level, message, script_name). Printing is unaffected.

  Like the stdout redirection the GUI already relies on, this is process-wide:
  it is meant for one check/prepare phase at a time.
  """
  _sinks.append(sink)
  try:
    yield sink
  finally:
    try:
      _sinks.remove(sink)
    except ValueError:
      pass

# What every message of a command is prefixed with ("odatix fmax"), instead of
# the module that prints it. The module name means nothing to someone typing a
# command; set once, by the command line, before the command runs.
_command = None

def set_command(label):
  """Prefix every message with `label` (e.g. "odatix fmax") from now on; None to go back to module names."""
  global _command
  _command = label

def _prefix(script_name):
  if script_name == "":
    return ""
  return colors.GREY + "[" + (_command or script_name) + "]" + colors.ENDC + " "

def say(message="", script_name="", color=colors.ENDC, end="\n"):
  script_name = _prefix(script_name)
  print(script_name + color + message + colors.ENDC, end=end)

def error(message, script_name="", end="\n"):
  _emit("error", message, script_name)
  script_name = _prefix(script_name)
  print(script_name + colors.BOLD + colors.RED + "error" + colors.ENDC + colors.RED + ": " + message + colors.ENDC, end=end)

def internal_error(message, script_name="", end="\n"):
  _emit("error", message, script_name)
  script_name = _prefix(script_name)
  print(script_name + colors.BOLD + colors.RED + "internal error" + colors.ENDC + colors.RED + ": " + message + colors.ENDC, end=end)

def warning(message, script_name="", end="\n"):
  _emit("warning", message, script_name)
  script_name = _prefix(script_name)
  print(script_name + colors.YELLOW + "warning: " + message + colors.ENDC, end=end)

def note(message, script_name="", end="\n"):
  _emit("note", message, script_name)
  script_name = _prefix(script_name)
  print(script_name + colors.CYAN + "note: " + message + colors.ENDC, end=end)

def tip(message, script_name="", end="\n"):
  _emit("tip", message, script_name)
  script_name = _prefix(script_name)
  print(script_name + colors.MAGENTA + "tip: " + message + colors.ENDC, end=end)

def messages(message_list, script_name=""):
  """
  Print what a part of Odatix that does not print by itself has to say.

  The workspace API reports through message objects (level, text and the hints
  that follow it, see odatix.workspace.selection.Message) rather than printing,
  so that the graphical interface and scripts can do something else with them.
  This is how the command line says them out loud.
  """
  printers = {"error": error, "warning": warning, "note": note, "tip": tip}
  for message in message_list or []:
    printers.get(message.level, note)(message.text, script_name)
    for hint in message.hints:
      tip(hint, script_name)

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